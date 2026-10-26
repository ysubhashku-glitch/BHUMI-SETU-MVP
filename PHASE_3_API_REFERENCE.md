# BHUMI SETU — PHASE 3 API REFERENCE

## Document Ingestion, OCR & Evidence Extraction Endpoints

### 1. Document Upload
- **Endpoint:** `POST /api/v1/cases/{case_id}/documents`
- **Authentication:** Bearer JWT (Role: Operator / Admin)
- **Content-Type:** `multipart/form-data`
- **Parameters:**
  - `file`: Raw binary document file (PDF, TIFF, PNG, JPEG).
  - `document_type`: Optional category hint (`REGISTERED_SALE_DEED`, `KHATIYAN`, etc.).
  - `auto_process`: Boolean (default `false`). If `true`, synchronously triggers the document extraction pipeline immediately upon storage.
- **Response `201 Created`:**
```json
{
  "document_id": "72afd074-3b87-4259-a39c-9734a0913882",
  "original_filename": "registered_sale_deed.pdf",
  "mime_type": "application/pdf",
  "file_size_bytes": 1048576,
  "storage_uri": "file://C:/storage/documents/d64e081b...pdf",
  "sha256_hash": "d64e081bf9f510cfcfe4d62d0e7059d18c2b1cbba5f237267160a08db9d08c46",
  "processing_status": "COMPLETED"
}
```

---

### 2. Trigger Pipeline Processing
- **Endpoint:** `POST /api/v1/documents/{document_id}/process`
- **Authentication:** Bearer JWT
- **Parameters (Query):**
  - `force_reprocess`: Boolean (optional, default `false`).
- **Response `200 OK`:**
```json
{
  "document_id": "72afd074-3b87-4259-a39c-9734a0913882",
  "processing_status": "COMPLETED",
  "document_category": "REGISTERED_SALE_DEED",
  "pages_processed": 1,
  "spans_extracted": 14,
  "fields_extracted": 8,
  "candidate_claims_generated": 4,
  "failure_reason": null
}
```

---

### 3. Retrieve Document Processing Status
- **Endpoint:** `GET /api/v1/documents/{document_id}/processing-status`
- **Authentication:** Bearer JWT
- **Response `200 OK`:**
```json
{
  "document_id": "72afd074-3b87-4259-a39c-9734a0913882",
  "version_number": 1,
  "status": "COMPLETED",
  "category": "REGISTERED_SALE_DEED",
  "pipeline_version": "1.0.0",
  "page_count": 1,
  "failure_reason": null,
  "created_at": "2026-09-23T05:00:00Z",
  "updated_at": "2026-09-23T05:00:05Z"
}
```

---

### 4. List Document Pages & Geometry
- **Endpoint:** `GET /api/v1/documents/{document_id}/pages`
- **Authentication:** Bearer JWT
- **Response `200 OK`:**
```json
[
  {
    "id": "18f9e2ab-8c90-410a-b102-6012c8b72450",
    "page_number": 1,
    "width": 1240,
    "height": 1754,
    "dpi": 150,
    "rotation_degrees": 0,
    "ocr_confidence": 0.95,
    "full_text": "DEED OF SALE (विक्रय विलेख)...",
    "has_spans": true
  }
]
```

---

### 5. List OCR Evidence Spans
- **Endpoint:** `GET /api/v1/documents/{document_id}/evidence-spans`
- **Authentication:** Bearer JWT
- **Parameters (Query):**
  - `page_number`: Integer (optional filter)
- **Response `200 OK`:**
```json
[
  {
    "id": "291ab49c-a110-4822-b9e7-49d71c261ef0",
    "page_number": 1,
    "text": "Vendor: Ram Kumar Verma, S/o Late Harihar Verma",
    "bounding_box": {
      "x_min": 0.05,
      "y_min": 0.20,
      "x_max": 0.95,
      "y_max": 0.25
    },
    "confidence_score": 0.96,
    "char_start": 120,
    "char_end": 167,
    "language": "eng"
  }
]
```

---

### 6. List Extracted Key-Value Fields
- **Endpoint:** `GET /api/v1/documents/{document_id}/extractions`
- **Authentication:** Bearer JWT
- **Response `200 OK`:**
```json
[
  {
    "id": "893c5d6e-9271-477d-bb91-729ab5109f3e",
    "field_name": "seller_name",
    "field_value": "Ram Kumar Verma",
    "normalized_value": "{\"first_name\": \"Ram\", \"last_name\": \"Verma\", \"canonical_name\": \"Ram Kumar Verma\"}",
    "confidence_score": 0.95,
    "is_verified": false,
    "evidence_span_id": "291ab49c-a110-4822-b9e7-49d71c261ef0"
  }
]
```

---

### 7. Review Extracted Field
- **Endpoint:** `POST /api/v1/extractions/{extracted_field_id}/review`
- **Authentication:** Bearer JWT
- **Request Body:**
```json
{
  "is_verified": true,
  "corrected_value": "Ram Kumar Verma",
  "review_notes": "Verified against Sub-Registrar seal"
}
```
- **Response `200 OK`:** Returns updated `ExtractedFieldResponse`.

---

### 8. Accept / Reject Candidate Claims
- **Accept Endpoint:** `POST /api/v1/candidate-claims/{candidate_claim_id}/accept`
  - Materializes authoritative `Claim` entity.
  - Links claim back to `evidence_span_id`.
  - Returns `{"candidate_claim_id": "...", "status": "ACCEPTED", "materialized_claim_id": "..."}`.
- **Reject Endpoint:** `POST /api/v1/candidate-claims/{candidate_claim_id}/reject`
  - Rejects candidate claim with audit reason.
  - Returns `{"candidate_claim_id": "...", "status": "REJECTED"}`.

---

### 9. Interactive Document Viewer UI
- **Endpoint:** `GET /ui/document-viewer`
- **Authentication:** Web browser session / Token Header
- **Description:** Interactive single-page interface rendering uploaded document canvas, OCR bounding box overlay, extracted fields sidebar, candidate claim review controls, and discrepancy inspector.
