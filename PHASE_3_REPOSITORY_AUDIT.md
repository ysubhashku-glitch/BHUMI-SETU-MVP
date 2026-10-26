# BHUMISETU — PHASE 3 REPOSITORY AUDIT

**Document Code:** BS-AUDIT-PHASE3-2026-V1  
**Date:** September 2026  
**Auditor:** Principal Systems Architect & Engineering Lead  
**Scope:** Pre-Implementation Forensic Audit of the Document Ingestion, OCR & Evidence Architecture  

---

## 1. Executive Summary

This repository audit was conducted in strict adherence to **Phase 3, Task 3** specifications prior to implementing the document ingestion, OCR, and evidence extraction pipeline.

Phase 2.1 successfully established the hardened PostgreSQL 16 + PostGIS 3.4 database foundation, Alembic migration framework, tenant isolation mechanisms (`org_id` scoped data access), immutable audit logs, deterministic consistency checks, and an end-to-end vertical slice passing 21 automated tests.

Phase 3 introduces the intelligence layer that turns heterogeneous, unstructured Indian land documents (Sale Deeds, Khatiyans, Jamabandi Panji II extracts, Mutation slips, Encumbrance Certificates) into structured, traceable evidence artifacts.

The paramount invariant governing this audit and the upcoming implementation is:

> **Extraction is not truth.**  
> OCR output is raw visual evidence. AI extraction is a candidate interpretation. Canonical property truth requires verifiable provenance, validation, and human-in-the-loop review.

---

## 2. Forensic Itemized Inspection & Classification

In accordance with Section 3, all 16 architectural components have been forensically audited and classified into:
`IMPLEMENTED`, `PARTIAL`, `MOCK`, `BROKEN`, or `UNKNOWN`.

| # | Architectural Dimension | Current Workspace Status | Classification | Detailed Findings & Phase 3 Gap Analysis |
| :- | :--- | :--- | :--- | :--- |
| **1** | **Current Document Model** | `backend/app/models/evidence.py` | `PARTIAL` | `Document` table exists with fields (`document_id`, `original_filename`, `mime_type`, `file_size_bytes`, `storage_uri`, `sha256_hash`, `uploader_party_id`, `processing_status`, `created_at`). It lacks explicit document categories (e.g. `SALE_DEED`, `KHATIYAN`), tenant `org_id` scoping, and parent-child linkage to versions. |
| **2** | **Document Version Model** | Absent | `BROKEN` | No `DocumentVersion` entity exists. The current schema treats each file upload as a flat single-state record. Must introduce `Document` $\rightarrow$ `DocumentVersion` $\rightarrow$ `DocumentPage` hierarchy to guarantee immutable historical versions. |
| **3** | **Document Page Model** | `backend/app/models/evidence.py` | `PARTIAL` | `DocumentPage` table exists (`page_id`, `document_id`, `page_number`, `page_image_uri`, `ocr_text`). It lacks FK to `DocumentVersion`, image dimensions (`width_px`, `height_px`), page rotation, resolution/DPI, OCR confidence scores, and individual page-level content hashes. |
| **4** | **Evidence Model** | `backend/app/models/evidence.py` | `IMPLEMENTED` | `Evidence` table is fully modeled with `authority_tier`, `evidence_type`, `sha256_hash`, `storage_uri`, and M:N `CaseEvidence` associations. Reusable across multiple cases without duplicate physical storage. |
| **5** | **Evidence Span Support** | `backend/app/core/document_boundary.py` | `MOCK` | Mentioned conceptually in boundary docstrings, but no database table or schema exists for storing granular coordinate bounding boxes (`x_min`, `y_min`, `x_max`, `y_max`) or text character spans (`char_start`, `char_end`). Must be implemented as a first-class model. |
| **6** | **Existing Storage Abstraction** | `backend/app/core/storage.py` | `PARTIAL` | `BaseStorageAdapter` exists with `store_file()`, `retrieve_file()`, and `generate_access_url()`. Needs expansion to the canonical interface `DocumentStorage` supporting `put()`, `get()`, `delete()`, `exists()`, `get_metadata()`, and `generate_download_reference()`. |
| **7** | **Current File Upload Flow** | `backend/app/routers/documents.py` | `PARTIAL` | Endpoint `POST /cases/{case_id}/documents` accepts multipart files and persists them locally via `LocalStorageAdapter`. It executes synchronously without MIME magic-byte verification, file size limits, page decomposition, or async queue dispatch. |
| **8** | **Current Object-Storage Implementation** | `backend/app/core/storage.py` | `PARTIAL` | `LocalStorageAdapter` writes hashed files into disk directory. `S3StorageAdapter` exists as a configured boundary stub marked `NOT_CONNECTED`. Production-grade `LocalDocumentStorage`, `S3DocumentStorage`, and `MinioDocumentStorage` must be formalized. |
| **9** | **Existing Background-Job Infrastructure** | Absent / Boundary Only | `MOCK` | `app/core/document_boundary.py` defines `DocumentProcessor` as an abstract stub. No active Celery/ARQ/Redis worker is installed. Phase 3 must establish an in-process modular-monolith background task orchestrator without external infrastructure bloat. |
| **10** | **Existing API Contracts** | `backend/app/routers/` | `IMPLEMENTED` (Phase 2) / `PARTIAL` (Phase 3) | Phase 2 REST endpoints for `/auth`, `/cases`, `/parcels`, `/evidence`, `/claims`, and `/findings` are active and validated. Endpoints for page viewing, field extractions, evidence spans, extraction review, and candidate claims must be added. |
| **11** | **Existing Tenant Isolation** | `backend/app/core/dependencies.py` | `IMPLEMENTED` | Cross-tenant isolation is enforced at the data layer via `org_id`. Validated by 6 adversarial security tests returning `CROSS_TENANT_ACCESS_DENIED` (HTTP 403). Must be strictly maintained across all document endpoints. |
| **12** | **Existing Audit Mechanism** | `backend/app/models/audit.py` | `IMPLEMENTED` | `AuditLog` table and `X-Request-ID` middleware track entity mutations and request tracing. Reviewer actions on extractions will append immutable audit records. |
| **13** | **Current Claim Architecture** | `backend/app/models/claim.py` | `PARTIAL` | `Claim` model supports epistemic dimensions (`authority_tier`, `confidence_score`) and temporal windows (`observed_at`, `recorded_at`, `effective_from`, `effective_to`). However, staging `CandidateClaim` and `ExtractedField` models do not yet exist. |
| **14** | **Current OCR Dependencies** | Absent | `MOCK` | No external OCR binaries or Python libraries (`pytesseract`, `pdf2image`, `pypdf`) are bundled in `pyproject.toml`. OCR provider interface must support pluggable engines with a high-fidelity `DemoOCRProvider` fallback. |
| **15** | **Current AI Dependencies** | `backend/app/services/mock_ai.py` | `MOCK` | `MockAILandExpert` adheres strictly to the 6-point grounding contract (`ANSWER`, `EVIDENCE`, `SOURCE`, `CONFIDENCE`, `UNCERTAINTY`, `NEXT_ACTION`). Confirmed: zero hallucinated or unconfigured cloud LLM calls exist. |
| **16** | **Existing Test Infrastructure** | `backend/tests/` | `IMPLEMENTED` | Pytest suite running on isolated SQLite engine (`test_bhumisetu.db`) with 21 passing tests covering DB constraints, domain rules, security, and vertical slice. |

---

## 3. Detailed Component Analysis

### 3.1 Document & Page Hierarchy Gap
The existing database schema connects `DocumentPage` directly to `Document`:
```text
[Document] ──< [DocumentPage]
```
This violates the immutability invariant when documents are re-uploaded, scanned with a higher resolution, or re-processed with a newer OCR parser version. The canonical target architecture requires:
```text
[Document] ──< [DocumentVersion] ──< [DocumentPage] ──< [EvidenceSpan]
```
Where `DocumentVersion` stores the cryptographic SHA-256, page count, OCR engine version, parser version, and processing status.

### 3.2 Epistemic Provenance Gap
In the current Phase 2 implementation, claims are created directly through `POST /claims` with an `evidence_id`. However, there is no intermediate model representing:
1. `EvidenceSpan`: Visual anchor (bounding box coordinates or character offsets on a specific page).
2. `ExtractedField`: Raw extracted string vs normalized value with extraction confidence.
3. `CandidateClaim`: Staging assertion awaiting human-in-the-loop review.

Without this chain, OCR or AI extraction would silently become canonical truth, violating Core Invariant #1.

### 3.3 Storage Interface Gap
The current `BaseStorageAdapter` in `app/core/storage.py` implements:
- `store_file()`
- `retrieve_file()`
- `generate_access_url()`

To satisfy Phase 3, Section 4 specifications, the adapter must be standardized to:
- `put(content, path, mime_type, metadata)`
- `get(path)`
- `delete(path)`
- `exists(path)`
- `get_metadata(path)`
- `generate_download_reference(path, expiry_seconds)`

And must support `LocalDocumentStorage`, `S3DocumentStorage`, and `MinioDocumentStorage`.

---

## 4. Preservation & Non-Regression Directive

The following components from Phase 2/2.1 are complete, tested, and must **NOT** be broken or redesigned:
1. **Multi-Tenancy Isolation**: `org_id` scoping in every query.
2. **Case State Machine**: `DRAFT` $\rightarrow$ `INTAKE_REVIEW` $\rightarrow$ `ACTIVE_INVESTIGATION` $\rightarrow$ `CONSISTENCY_EVALUATION` $\rightarrow$ `ADVOCATE_REVIEW` $\rightarrow$ `COMPLETED`.
3. **Consistency Engine**: `check_area_delta`, `check_mutation_gap`, `check_chauhadri_boundaries` in `app/services/consistency_service.py`.
4. **SPT Act Section 20 Rule Engine**: In `app/services/legal_rule_service.py`.
5. **Existing 21 Pytest Scenarios**: Must continue to pass with 100% success rate.

---

## 5. Audit Conclusion & Phase 3 Roadmap

The repository is structurally ready for Phase 3. The foundational domain models and security infrastructure provide a solid scaffold. 

**Execution Priorities:**
1. Upgrade storage abstraction with standardized operations and cryptographic immutability.
2. Extend domain models (`DocumentVersion`, `EvidenceSpan`, `ExtractedField`, `CandidateClaim`).
3. Build document preprocessor and pluggable multi-engine OCR adapter (English, Hindi, revenue terms).
4. Implement specialized template parsers for Sale Deeds, Khatiyans, Jamabandis, Mutations, and Encumbrance Certificates.
5. Implement candidate matching (parties and parcels) and candidate claim generation.
6. Connect candidate claims to human review and the consistency engine.
7. Build asynchronous background processing pipeline and validation UI.
8. Deliver 10+ comprehensive automated tests and full architectural documentation.
