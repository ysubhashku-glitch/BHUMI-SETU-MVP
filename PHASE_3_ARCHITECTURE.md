# BHUMI SETU — PHASE 3 ARCHITECTURE SPECIFICATION
## Document Ingestion, OCR & Evidence Extraction Pipeline

### 1. Executive Summary & Core Architectural Invariant
The BhumiSetu Phase 3 Document Ingestion, OCR & Evidence Extraction Pipeline enforces the non-negotiable core architectural invariant:
> **"Extraction is not truth."**
> OCR output represents raw visual sensory evidence. AI, pattern recognition, and parser outputs are candidate interpretations. No document upload or OCR extraction may directly create or modify authoritative Land Truth (`Claim` or parcel boundaries) without explicit provenance linkage, confidence thresholds, entity resolution, and human-in-the-loop review.

```
RAW DOCUMENT (PDF/TIFF/JPEG/PNG)
       │
       ▼ (SHA-256 Hashing, Magic-Byte MIME Sniffing, Storage Abstraction)
DOCUMENT VERSION (Immutable, Storage Reference, Multi-tenant Isolation)
       │
       ▼ (Page Segmentation, Rotation Correction, Password Traps)
DOCUMENT PAGES (Dimensions, DPI, Resolution, Page Hash)
       │
       ▼ (OCR Provider Abstraction: Tesseract / Deterministic Demo Provider)
OCR RESULT & EVIDENCE SPANS (Bounding Box [ymin, xmin, ymax, xmax], Confidence, Character Offsets)
       │
       ▼ (Classification & Multi-Category Domain Parsers)
EXTRACTED FIELDS (Structured Key-Values, Confidence, Normalization)
       │
       ▼ (Party & Parcel Entity Resolution)
CANDIDATE CLAIMS (Staging Area, Lineage to Evidence Spans)
       │
       ▼ (Human-in-the-Loop Review: Accept / Reject / Edit)
CANONICAL CLAIMS (Materialized Land Truth)
       │
       ▼ (Consistency Engine & Rule Validation)
FINDINGS & REQUIRED ACTIONS (Discrepancy Alerts, SPT/CNT Violations)
```

---

### 2. Pipeline Components

#### 2.1 Storage Architecture (`app.core.storage`)
- **Abstract Interface:** `DocumentStorage` defining `put`, `get`, `delete`, and `exists`.
- **Implementations:**
  - `LocalDocumentStorage`: Deterministic content-addressed local filesystem storage.
  - `S3DocumentStorage`: S3-compatible cloud storage adapter.
  - `MinioDocumentStorage`: High-performance self-hosted S3-compatible storage.
- **Security & Integrity Safeguards:**
  - True MIME sniffing via file headers / magic bytes (preventing file extension spoofing).
  - SHA-256 digest computation upfront for cryptographic deduplication.
  - Immutable file storage: paths and references cannot be overwritten.

#### 2.2 Document Preprocessing (`app.services.document_preprocessor`)
- **Inspection & Validation:**
  - File size cap enforcement (e.g., 50MB max).
  - Multi-page PDF page limit safeguards (e.g., 100 pages max).
  - Detection of encrypted / password-protected files with graceful descriptive rejection (`PASSWORD_PROTECTED`).
  - Detection of corrupted streams and zero-byte payloads.
  - Automatic page dimension extraction and orientation evaluation.

#### 2.3 OCR Engine Abstraction (`app.services.ocr_engine`)
- **Provider Interface:** `OCRProvider` returning standardized `OCRResult`, `OCRPageResult`, and `OCRSpanResult`.
- **Implementations:**
  - `TesseractOCRProvider`: Wrapper around Tesseract OCR engine with multilingual Hindi (`hin`) and English (`eng`) support.
  - `DemoOCRProvider`: Deterministic, high-fidelity mock OCR engine recognizing authentic Indian land revenue terminology (Khatiyan, Jamabandi, Sale Deeds, Mutation correction slips, Encumbrance certificates).
- **Coordinate System:**
  - Normalized relative bounding boxes `[x_min, y_min, x_max, y_max]` bounded in `[0.0, 1.0]`.
  - Character offsets (`char_start`, `char_end`) linking text back to page-level content.

#### 2.4 Document Classification (`app.services.document_classifier`)
- Classifies incoming land records into 10 standard Indian land record categories:
  1. `REGISTERED_SALE_DEED` (विक्रय विलेख / केवाला)
  2. `RECORD_OF_RIGHTS` / `KHATIYAN` (खतियान)
  3. `JAMABANDI_REGISTER` / `REGISTER_II` (जमाबंदी पंजी)
  4. `MUTATION_RECORD` / `DAKHIL_KHARIJ` (दाखिल खारिज)
  5. `ENCUMBRANCE_CERTIFICATE` (भारमुक्त प्रमाण पत्र)
  6. `LAND_REVENUE_RECEIPT` / `LAGAN_RASHID` (लगान रसीद)
  7. `MAP_TIYAR_SURVEY` (नक्शा / ट्रेस)
  8. `PARTITION_DEED` (बंटवारानामा)
  9. `MORTGAGE_DEED` (बंधक विलेख)
  10. `UNKNOWN` / `OTHER`

#### 2.5 Normalization Engine (`app.services.normalization_service`)
- **Area Normalization:**
  - Converts heterogeneous traditional Indian land units (`Acre`, `Decimal`, `Katha`, `Bigha`, `Sqft`) to canonical standard `Square Meters` (sqm).
  - Preserves original raw value and unit alongside normalized numerical representation.
- **Legal Party Name Normalization:**
  - Parses aliases, father/husband relationships (`S/o`, `W/o`, `D/o`), caste/community tags, and honors original spelling while producing canonical search tokens.

#### 2.6 Domain Parsers (`app.services.parsers`)
Specialized extractors extracting domain keys:
- `SaleDeedParser`: Deed number, registration date, consideration amount, seller, buyer, boundaries (North/South/East/West), Mauza, Khata, Plot, Area.
- `KhatiyanParser`: Khata number, Raiyat name, Father's name, Caste, Plot list with land classifications (`Dhani 1`, `Dhani 2`, `Bari`) and rents.
- `JamabandiParser`: Jamabandi number, Khata, Plot, Raiyat name, Lagan demand, Cess, Mutation case cross-references.
- `MutationParser`: Case number, Order date, Transferor, Transferee, mutated area, approval status.
- `EncumbranceParser`: Search period, property reference, recorded transactions, encumbrance status.

#### 2.7 Entity Resolution & Claim Generation (`app.services.entity_resolution_service`, `app.services.claim_generator_service`)
- **Entity Resolution:**
  - Matches parties from extracted fields against case entities using token similarity and parentage matching.
  - Matches parcels using Khata + Plot + Village/Mauza hierarchy.
- **Candidate Claims Staging:**
  - Generates `CandidateClaim` instances in `PENDING_REVIEW` status.
  - Links candidate claims directly to source `ExtractedField` and `EvidenceSpan` instances.
  - Human review workflow allows reviewers to **Accept**, **Reject**, or **Edit** candidate claims before conversion into authoritative `Claim` objects.

#### 2.8 Consistency Engine Integration (`app.services.consistency_service`)
- Discrepancy checks run on candidate claims and newly approved claims:
  - Area mismatch detection across deeds and Khatiyan/Jamabandi records.
  - Boundary conflict identification.
  - Mutation gaps (unbroken chain of title verification).
  - Statutory restrictions (e.g., Santhal Parganas Tenancy Act Section 20, Chota Nagpur Tenancy Act Section 46 tribal land transfer restrictions).
- Generates `Finding` and `RequiredAction` items for operator resolution.

---

### 3. Tenant Isolation & Security
- Every database model (`Document`, `DocumentVersion`, `DocumentPage`, `EvidenceSpan`, `ExtractedField`, `CandidateClaim`) carries a mandatory `tenant_id` foreign key.
- All repository queries and API endpoints enforce strict tenant scoping derived exclusively from the authenticated JWT session context.
- Cross-tenant access is tested adversarially and rejected with `404 Not Found` (anti-enumeration) or `403 Forbidden`.
