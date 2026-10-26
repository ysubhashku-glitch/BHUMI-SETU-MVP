# Technical Implementation Note: TASK-P1-03 Document Intelligence & OCR Extraction Pipeline

**Component:** Multilingual Document Intelligence & Land Record Extraction Pipeline  
**Target Services:**  
- `backend/app/services/document_pipeline.py`  
- `backend/app/services/ocr_engine.py`  
- `backend/app/services/document_classifier.py`  
- `backend/app/services/normalization_service.py`  
- `backend/app/services/parsers/chauhaddi_extractor.py`  
- `backend/app/services/parsers/sale_deed_parser.py`  
- `backend/app/services/parsers/khatiyan_parser.py`  
- `backend/app/services/document_cross_reference_service.py`  
**Router Path:** `backend/app/routers/documents.py`  
**Test Suite:** `backend/tests/test_document_intelligence.py`  
**Date:** October 24, 2026  
**Status:** Completed & Verified (17/17 new tests passing, 79/79 total regression tests passing in 13.55s)

---

## 1. Existing Architecture Inspected & Baseline Establishment

Before modifying code or creating new components, an exhaustive repository audit was performed across:
* **Models:** `app/models/evidence.py` (`Document`, `DocumentVersion`, `DocumentPage`, `EvidenceSpan`, `ExtractedField`), `app/models/claim.py` (`Claim`, `CandidateClaim`), `app/models/parcel.py` (`Parcel`, `ParcelVersion`), and `app/models/case.py` (`Case`, `CaseEvidence`, `CaseParcel`).
* **Services:** `DocumentPipelineService`, `DocumentClassifier`, `DocumentPreprocessor`, `DemoOCRProvider`, `TesseractOCRProvider`, `NormalizationService`, and existing parsers in `app/services/parsers/`.
* **Consistency Engine:** `app/services/consistency_service.py` (`check_area_delta`, `ConsistencyCheckResult`, `FindingSeverity`).
* **Adapters from P1-01 and P1-02:** `BiharBhumiJamabandiAdapter` (`bihar_bhumi.py`) and `BiharBhuNakshaAdapter` (`bhunaksha.py`).
* **Baseline Health:** All 62 pre-existing tests passed without failures prior to modification.

---

## 2. Components Reused

No redundant abstractions, parallel models, or duplicate services were created:
* **Storage & Evidence Anchoring:** Reused `get_document_storage()` and SHA-256 content hashing in `app/core/storage.py` and `DocumentVersion`.
* **State Machine Pipeline:** Preserved `DocumentPipelineService` state machine (`STORED` → `VALIDATING` → `PROCESSING` → `OCR_COMPLETE` → `EXTRACTION_COMPLETE` → `READY` / `VALIDATION_REQUIRED`).
* **Evidence Provenance & Spans:** Maintained `EvidenceSpan` with normalized bounding boxes `[x_min, y_min, x_max, y_max]` and character offsets.
* **Consistency Engine:** Reused `check_area_delta` for area tolerance and discrepancy classification.
* **Domain Models:** Direct integration with `Parcel`, `DocumentPage`, `ExtractedField`, and `CandidateClaim`.

---

## 3. Files Created and Modified

### Files Created:
1. `backend/app/services/parsers/chauhaddi_extractor.py`: Dedicated 4-sided directional boundary extractor for Hindi Devanagari and English Chauhaddi recitals with neighbor identity, road frontage, and adjoining plot detection.
2. `backend/app/services/document_cross_reference_service.py`: Cross-references extracted document fields against tenant database parcels and Bihar Jamabandi Register-II records with deterministic outcome scoring.
3. `backend/tests/test_document_intelligence.py`: Comprehensive 17-test verification suite covering OCR ingestion, classification, parsing, boundary extraction, cross-referencing, human review audit trails, and tenant isolation.
4. `backend/docs/TASK-P1-03_DOCUMENT_INTELLIGENCE_NOTE.md`: This technical implementation note.

### Files Modified:
1. `backend/app/services/ocr_engine.py`: Enhanced `DemoOCRProvider` with multi-page splitting, direct UTF-8 content decoding, empty document safeguards, and per-span Devanagari (`hin`) vs Latin (`eng`) script detection.
2. `backend/app/services/document_classifier.py`: Added `doc-classifier-v1.2` supporting bilingual signals, alternative classification ranking, `review_required` flagging, and Cadastral Map signals.
3. `backend/app/services/normalization_service.py`: Extended with Hindi unit recognition (`एकड़`, `डिसमिल`, `कट्ठा`, `बीघा`, `हेक्टेयर`), composite expressions (e.g., `1 एकड़ 25 डिसमिल`), and explicit missing-unit uncertainty.
4. `backend/app/services/parsers/sale_deed_parser.py`: Upgraded to bilingual regex, negative lookbehinds on buyer (`(?<!वि)क्रेता`), digit enforcement on plot numbers, page provenance tracing, and Chauhaddi extraction.
5. `backend/app/services/parsers/khatiyan_parser.py`: Upgraded with bilingual field patterns, Thana numbers, land nature, page provenance, and digit-enforced plot number parsing.
6. `backend/app/services/document_pipeline.py`: Connected extracted fields directly to source page instances (`DocumentPage`) for granular page-level provenance.
7. `backend/app/schemas/document_pipeline.py`: Added `DocumentClassificationResponse`, `CrossReferenceRequest`, `CrossReferenceMatchCandidate`, and `DocumentCrossReferenceResponse`.
8. `backend/app/routers/documents.py`: Added `GET /api/v1/documents/{id}/classification` and `POST /api/v1/documents/{id}/cross-reference`.

---

## 4. OCR Engine and Configuration Requirements

* **Local Deterministic Engine (`DemoOCRProvider`):** Used across test suites, headless environments, and local evaluation. Operates deterministically without external network calls, parses selectable UTF-8 text from uploaded files, generates normalized bounding box coordinates `[x_min, y_min, x_max, y_max]`, and assigns Devanagari (`hin`) or Latin (`eng`) tags.
* **Tesseract Engine (`TesseractOCRProvider`):** Discovers `tesseract` on system PATH via `shutil.which`. If unavailable, raises `RuntimeError("Tesseract binary is not installed on system PATH.")` with clear configuration instructions rather than faking success.
* **Supported Languages:**
  - Hindi in Devanagari script (`hin`).
  - English (`eng`).
  - Mixed Indic-Latin land records (`eng+hin`).

---

## 5. Supported Document Types

| Document Category | Key Indic / English Vocabulary Signals | Handled Parser |
| :--- | :--- | :--- |
| **Sale Deed / Kewala** | बैनामा, विक्रय पत्र, kewala, केवाला, consideration, seller, purchaser, क्रेता, विक्रेता | `SaleDeedParser` |
| **Khatiyan / Survey Record** | खतियान, khatiyan, CS Khatiyan, RS Khatiyan, raiyat, रैयतदार, thana no, किस्म जमीन, lagan | `KhatiyanParser` |
| **Jamabandi / Register-II** | जमाबंदी, पंजी II, Register II, halka, demand register, volume no, page no | `JamabandiParser` |
| **Mutation Slip / Shuddhi Patra** | दाखिल-खारिज, dakhil kharij, mutation order, शुद्धि पत्र, circle officer | `MutationParser` |
| **Cadastral Map / LPM** | नक्शा, cadastral map, bhu-naksha, भू-नक्शा, LPM certificate, plot boundary | `DocumentClassifier` |
| **Encumbrance Certificate** | निरीक्षण प्रमाण पत्र, encumbrance certificate, non-encumbrance, nil encumbrance | `EncumbranceParser` |
| **Unknown / Unsupported** | Text lacking recognizable revenue terminology (< 0.60 confidence) | Stored as `UNKNOWN`, flags `review_required=True` |

---

## 6. Field Extraction & Provenance Model

Extracted fields are persisted as immutable `ExtractedField` rows linked to their exact origin:
* `field_name`: Canonical attribute name (e.g. `khata_number`, `plot_number`, `boundary_north`, `recorded_area`).
* `raw_value`: Exact verbatim text detected in the document.
* `normalized_value`: Standardized dictionary, string, or decimal value.
* `page_id`: Direct foreign key to `DocumentPage`, tracing the exact source page.
* `confidence`: Heuristic and OCR confidence score [0.0–1.0].
* `status`: `CANDIDATE` (>= 0.70), `UNKNOWN` (< 0.70), `VALIDATED` (after human review), `REJECTED`, or `CONFLICTING`.

---

## 7. Area Normalization Rules

Area measurements are normalized using strict metrological ratios:
* $1\text{ Acre} = 4046.8564\text{ m}^2 = 100\text{ Decimals}$
* $1\text{ Decimal} = 40.468564\text{ m}^2 = 0.01\text{ Acre}$
* $1\text{ Standard Bihar Bigha} = 2529.285\text{ m}^2 = 0.625\text{ Acre}$
* $1\text{ Katha} = \frac{1}{20}\text{ Bigha} = 126.46\text{ m}^2$
* $1\text{ Hectare} = 10000.0\text{ m}^2 = 2.47105\text{ Acres}$

### Epistemic Safeguards on Area:
1. **Raw Preserved:** `raw_string`, `raw_numeric`, and `raw_unit` are never overwritten.
2. **Missing Unit Rejection:** A bare number (e.g. `"150"`) is explicitly marked `is_uncertain=True`, `normalized_acres=None`, and rule `"MISSING_UNIT"`. The system **never guesses** a missing unit.
3. **Composite Units:** Safely interprets `"1 एकड़ 25 डिसमिल"` and `"2 बीघा 10 कट्ठा"` into total acres and square meters.

---

## 8. Chauhaddi (Boundary) Extraction Logic & Limitations

The `ChauhaddiExtractor` parses 4-sided directional descriptions (`North`, `South`, `East`, `West` / `उत्तर`, `दक्षिण`, `पूरब`, `पश्चिम`):
* Detects road frontage and width in feet (e.g., `20 फीट चौड़ा पीडब्ल्यूडी सड़क` → `road_width_feet=20.0`, `is_road_or_path=True`).
* Detects waterway and pathway easements (`नाला`, `डहर`, `पगडंडी`, `सड़क`, `मार्ग`, `गली`).
* Extracts adjoining plot identifiers (e.g., `प्लॉट संख्या 512` → `adjoining_plot_number="512"`).
* Extracts adjoining neighbor identities (e.g., `मदन लाल का खेत` → `adjoining_neighbor_name="मदन लाल"`).

### Legal Limitations:
* Textual boundaries reflect historical recitals in the source deed.
* They **do not certify** current ground possession, adverse possession, or encroachment.
* They **do not replace** an official Electronic Total Station (ETS) / DGPS field Amin survey.

---

## 9. Cross-Referencing Logic & Epistemic Outcomes

The `DocumentCrossReferenceService` matches extracted document fields against tenant database parcels and Bihar Jamabandi Register-II records:

| Outcome Status | Condition | Action Required |
| :--- | :--- | :--- |
| **`EXACT_MATCH`** | Khata, Plot, and Mauza match; area delta $\le 5\%$. | Review optional; candidate match confirmed. |
| **`AREA_DISCREPANCY`** | Identifiers match, but area delta $> 5\%$ (via `check_area_delta`). | Review required; field demarcation recommended. |
| **`IDENTIFIER_CONFLICT`** | Plot matches, but Khata number is contradictory. | Review required; potential adverse mutation or wrong title trace. |
| **`MULTIPLE_CANDIDATE_MATCHES`** | Multiple parcels share the plot number (e.g. unrecorded sub-divisions). | Review required; manual parcel selection needed. |
| **`PROBABLE_MATCH`** | Plot matches, but Raiyat / tenant name exhibits variance. | Review required; verify legal devolution/inheritance. |
| **`NO_MATCH`** | No matching registered parcel in tenant organization repository. | Review required; parcel must be registered or ingested. |
| **`INSUFFICIENT_DATA`** | Document lacks both Khata and Plot numbers. | Review required; un-indexed deed or illegible scan. |

### Core Epistemic Safety Guarantees:
* **No Automatic Overwrite:** Extracted OCR data **never** overwrites authoritative government records or existing database parcels.
* **No Automatic Parcel Merging:** Discrepancies generate review findings; parcels are never merged without human adjudication.
* **Notice Displayed:** All cross-reference outputs return the standard legal disclaimer: *"Automated cross-reference results are derived heuristics and do NOT constitute verified legal title, judicial adjudication, or field survey confirmation."*

---

## 10. Human Review Workflow & Audit Trail

Reviewers interact via `POST /api/v1/extractions/{field_id}/review`:
* **Actions:** `ACCEPT`, `EDIT`, `REJECT`, `MARK_UNKNOWN`, `MARK_CONFLICTING`.
* **Value Preservation:** If edited, `normalized_value` updates to the reviewer's value, while `raw_value` **remains completely unchanged**.
* **Audit Trail:** Captures `reviewed_by_user_id`, `reviewed_at` timestamp, and mandatory `review_notes`.
* **Tenant Isolation:** Enforces `document.org_id == current_user.org_id`. Cross-tenant review requests are rejected with HTTP 403.

---

## 11. API Additions

1. `GET /api/v1/documents/{document_id}/classification`:
   - Returns structured classification breakdown, confidence, matched signals, alternative categories, and review status.
2. `POST /api/v1/documents/{document_id}/cross-reference`:
   - Compares extracted fields against tenant parcels and Jamabandi records, returning matching status, candidate parcels, area deltas, and discrepancy findings.

---

## 12. Security Considerations

* **Safe File Validation:** Enforces MIME-type inspection, magic byte verification, safe filename sanitization, and 25 MB file size limit via `validate_upload_security()`.
* **Path Traversal Protection:** Filenames are stripped of path components (`../`, `..\\`) and stored outside web-accessible roots.
* **OCR Text as Untrusted Input:** Extracted text is strictly treated as untrusted data. It is never evaluated dynamically or used in unsanitized SQL.
* **Tenant Isolation:** Every document, version, extraction, and cross-reference query is scoped to `current_user.org_id`.

---

## 13. Test Commands & Actual Results

### Test Execution:
```bash
.\.venv\Scripts\python -m pytest tests/test_document_intelligence.py
```
**Result:** `17 passed, 13 warnings in 2.44s`

### Full Regression Suite:
```bash
.\.venv\Scripts\python -m pytest
```
**Result:** `79 passed, 15 warnings in 13.55s`

Breakdown:
* `tests\test_api.py`: 5 passed
* `tests\test_bhunaksha_adapter.py`: 20 passed (TASK-P1-02)
* `tests\test_bihar_bhumi_adapter.py`: 14 passed (TASK-P1-01)
* `tests\test_database.py`: 4 passed
* `tests\test_document_intelligence.py`: 17 passed (TASK-P1-03)
* `tests\test_document_pipeline.py`: 7 passed
* `tests\test_domain.py`: 5 passed
* `tests\test_security.py`: 6 passed
* `tests\test_vertical_slice.py`: 1 passed

---

## 14. Known Limitations & Future Improvements

1. **Handwritten Kaithi Script:** Historical Bihar land documents (CS Khatiyans and pre-1950 deeds) frequently feature Kaithi script. Current engines support standard Devanagari; specialized Kaithi vision models can be plugged in via the modular `OCRProvider` interface in a future phase.
2. **Complex Family Batwara (Partition Deeds):** Unregistered family partition recitals (Khangi Batwara) with complex conditional schedules require custom NLP graph modeling.
3. **Live Vision Cloud Fallback:** When Google Cloud Vision or AWS Textract credentials are provided, cloud OCR adapters can be registered dynamically in `get_ocr_provider()`.
