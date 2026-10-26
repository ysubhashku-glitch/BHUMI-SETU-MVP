# BHUMI SETU — PHASE 3 DOCUMENT PIPELINE SPECIFICATION

## Overview
The Document Ingestion, OCR & Evidence Extraction Pipeline coordinates the transition of raw files into structured, verifiable land intelligence.

---

## Pipeline Lifecycle & State Machine

```
                        +----------------------+
                        |   Document Upload    |
                        +----------+-----------+
                                   |
                                   v
                        +----------------------+
                        |     PREPROCESSING    |
                        | (Sniffing, Geometry) |
                        +----------+-----------+
                                   |
                      +------------+------------+
                      |                         |
                      v (Pass)                  v (Fail)
            +-------------------+     +-------------------+
            |    OCR_QUEUED     |     |      FAILED       |
            +---------+---------+     | (Corrupt/PW/Size) |
                      |               +-------------------+
                      v
            +-------------------+
            |   OCR_PROCESSING  |
            +---------+---------+
                      |
                      v
            +-------------------+
            |   CLASSIFYING     |
            +---------+---------+
                      |
                      v
            +-------------------+
            |    EXTRACTING     |
            +---------+---------+
                      |
                      v
            +-------------------+
            | RESOLVING_ENTITIES|
            +---------+---------+
                      |
                      v
            +-------------------+
            | GENERATING_CLAIMS |
            +---------+---------+
                      |
                      v
            +-------------------+
            |     COMPLETED     |
            +-------------------+
```

---

## Pipeline Stages Detail

### 1. Document Upload & Storage Ingestion
- Client submits a multipart form upload targeting `POST /api/v1/cases/{case_id}/documents`.
- The storage system validates MIME type via magic bytes, computes SHA-256 hash, and stores the file into the active `DocumentStorage` backend (`file://` or S3/MinIO URI).
- A `Document` parent record and initial `DocumentVersion` (version 1) are created with `DocumentProcessingStatus.UPLOADED`.

### 2. Preprocessing
- Preprocessor verifies file integrity:
  - Header inspection (PDF `%PDF-`, PNG `\x89PNG`, JPEG `\xFF\xD8\xFF`, TIFF `II*\x00` or `MM\x00*`).
  - Size check against tenant maximum allowed upload limit (50MB).
  - Password protection trap: Rejects password-encrypted files with `failure_reason = "Document is password protected"`.
  - Determines page count and geometry (dimensions, resolution, rotation).

### 3. OCR & Span Generation
- For each page, an OCR worker (Tesseract or Deterministic Demo Engine) scans the visual layer.
- Produces:
  - `DocumentPage`: Persisted in DB with resolution, dimensions, rotation, full raw text, and page hash.
  - `EvidenceSpan`: Persisted for every detected sentence/line/token with normalized bounding box `[x_min, y_min, x_max, y_max]`, confidence score, character offsets, and language tag.

### 4. Classification
- The `DocumentClassifier` analyses the page text and filename against lexical signatures and revenue regex sets.
- Emits detected `DocumentCategory` with a confidence score and classification explanation.
- Updates `DocumentVersion.document_category`.

### 5. Multi-Category Parsing & Normalization
- Selects the domain parser matching the classified category:
  - `SaleDeedParser`
  - `KhatiyanParser`
  - `JamabandiParser`
  - `MutationParser`
  - `EncumbranceParser`
- Parser extracts key attributes, linking each `ExtractedField` to its corresponding `EvidenceSpan`.
- Normalizer executes conversions (e.g. Acre/Katha/Decimal to square meters) and canonicalizes legal entity names.

### 6. Entity & Parcel Resolution
- Matches extracted parties against existing `Party` records in the case:
  - Evaluates name equality, token overlap, and father/husband name correlation.
- Matches land parcels against existing `Parcel` records:
  - Matches district, circle, village/mauza, khata, and plot/khesra numbers.
  - Computes resolution confidence score (0.0 to 1.0).

### 7. Candidate Claim Generation & Staging
- For every verified extraction, generates a `CandidateClaim`:
  - `predicate`: `OWNERSHIP`, `ENCUMBRANCE`, `BOUNDARY`, `AREA`, `RESTRICTION`, etc.
  - `subject_entity_id`: Resolved parcel or party ID.
  - `confidence_score`: Weighted product of OCR confidence, parser confidence, and resolution match score.
  - `status`: `PENDING_REVIEW`.
  - Lineage: Pointing to `extracted_field_id` and `evidence_span_id`.

### 8. Human-in-the-Loop Review & Materialization
- Authoritative claims are never produced automatically by OCR.
- The human reviewer accesses `/ui/document-viewer` or invokes:
  - `POST /api/v1/candidate-claims/{id}/accept`: Transitions candidate claim to `ACCEPTED`, and materializes an authoritative, immutable `Claim` record with direct provenance to the document evidence span.
  - `POST /api/v1/candidate-claims/{id}/reject`: Transitions candidate claim to `REJECTED` with audit notes.
