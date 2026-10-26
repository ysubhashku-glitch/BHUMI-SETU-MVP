# BHUMI SETU — CANONICAL TECHNICAL ARCHITECTURE (v1.1)
**Canonical Hardened Reference:** [BHUMISETU_ARCHITECTURE_BLUEPRINT_V1.1.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/05_Research_and_Technical_Specs/BHUMISETU_ARCHITECTURE_BLUEPRINT_V1.1.md)  
**Implementation Status:** PHASE 3 COMPLETE (Document Ingestion, OCR & Evidence Extraction Pipeline)  
**Latest Audit:** [PHASE_3_IMPLEMENTATION_REPORT.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_3_IMPLEMENTATION_REPORT.md)  

---

## 1. Implementation Status Overview (Phase 3 Complete)

| Layer | Component | Status | Implementation Details |
| :--- | :--- | :--- | :--- |
| **Database Engine** | PostgreSQL 16 + PostGIS 3.4 | **HARDENED** | Target dialect configured to `postgresql+psycopg` (v3). `docker-compose.yml` defining `postgis/postgis:16-3.4` created. |
| **Schema & Migrations**| Alembic + PostGIS Ext | **HARDENED** | 23+ tables defined via SQLAlchemy 2.0. Domain models for `DocumentVersion`, `DocumentPage`, `EvidenceSpan`, `ExtractedField`, and `CandidateClaim` fully active. |
| **Multi-Tenancy** | Backend Tenant Isolation | **HARDENED** | Enforced at data-access layer via `tenant_id`. Adversarial tests prove cross-tenant access rejection (`CROSS_TENANT_ACCESS_DENIED`, HTTP 403 / 404). |
| **Storage Architecture** | Object Storage Abstraction | **HARDENED** | Pluggable `DocumentStorage` ABC with `LocalDocumentStorage`, `S3DocumentStorage`, and `MinioDocumentStorage`. SHA-256 deduplication and true magic-byte MIME sniffing. |
| **Document Pipeline** | Preprocessing & OCR Engine | **HARDENED** | Detection of corrupted/oversized/password-protected files. Pluggable `OCRProvider` (`TesseractOCRProvider`, `DemoOCRProvider`) generating normalized coordinate bounding boxes `[x_min, y_min, x_max, y_max]`. |
| **Intelligence Extraction**| Parsers & Normalization | **HARDENED** | Multi-category classifiers and domain parsers (`SaleDeed`, `Khatiyan`, `Jamabandi`, `Mutation`, `Encumbrance`). Unit converter (Acre/Decimal/Katha/Sqft -> Sqm) and name parser. |
| **Truth Staging & Invariant**| Candidate Claims | **HARDENED** | *"Extraction is not truth."* Extracts feed `CandidateClaim` in `PENDING_REVIEW`. Materializes to authoritative `Claim` only upon explicit human review (`/accept`). |
| **Consistency Engine** | Anomaly Detection | **HARDENED** | Automated identification of area deltas, mutation gaps, boundary conflicts, and SPT Act Section 20 statutory violations. |
| **Test Suite** | Pytest Automation | **PASSED (28/28)**| 28 tests passing (100% pass rate) covering DB constraints, API, domain rules, state machines, adversarial security, document storage, OCR, extraction, and end-to-end vertical slice. |

---

## 2. Canonical Deliverables Matrix

### Phase 3 Deliverables
1. **Repository Audit:** [PHASE_3_REPOSITORY_AUDIT.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_3_REPOSITORY_AUDIT.md)
2. **Architecture Specification:** [PHASE_3_ARCHITECTURE.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_3_ARCHITECTURE.md)
3. **Pipeline Lifecycle:** [PHASE_3_DOCUMENT_PIPELINE.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_3_DOCUMENT_PIPELINE.md)
4. **Extraction Schemas:** [PHASE_3_EXTRACTION_SCHEMA.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_3_EXTRACTION_SCHEMA.md)
5. **API Reference:** [PHASE_3_API_REFERENCE.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_3_API_REFERENCE.md)
6. **Test Report:** [PHASE_3_TEST_REPORT.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_3_TEST_REPORT.md)
7. **Implementation Report:** [PHASE_3_IMPLEMENTATION_REPORT.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_3_IMPLEMENTATION_REPORT.md)

### Phase 2.1 Deliverables
1. **Forensic Audit:** [PHASE_2_1_FORENSIC_AUDIT.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_2_1_FORENSIC_AUDIT.md)
2. **Database Compliance:** [PHASE_2_1_DATABASE_COMPLIANCE.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_2_1_DATABASE_COMPLIANCE.md)
3. **Security Audit:** [PHASE_2_1_SECURITY_AUDIT.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_2_1_SECURITY_AUDIT.md)
4. **Test Report:** [PHASE_2_1_TEST_REPORT.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_2_1_TEST_REPORT.md)
5. **Implementation Report:** [PHASE_2_1_IMPLEMENTATION_REPORT.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_2_1_IMPLEMENTATION_REPORT.md)

---

## 3. Core Architectural Invariants (v1.1 Canonical)

1. **Extraction Is Not Truth**:
   - OCR output is visual evidence; AI/pattern extraction is candidate interpretation. No automated extraction creates authoritative Land Truth without human verification.
2. **Decoupled Domain Objects**:
   - `Parcel`, `Case`, and `Transaction` are independent entities with explicit M:N cardinalities.
3. **Decoupled Evidence Ownership**:
   - Evidence belongs to the Evidence Vault, not a single case (`Evidence` $\longleftrightarrow$ `CaseEvidence` $\longleftrightarrow$ `Case`).
4. **First-Class Party Model**:
   - `Party` (Person, Organization, Trust, HUF) exists as an independent master domain object with ownership shares and statutory tenancy audit attributes.
5. **Temporal Claims & Competing Truth**:
   - Claims feature explicit temporality (`observed_at`, `recorded_at`, `effective_from`, `effective_to`). Conflicting claims coexist concurrently.
6. **Relational Parcel Lineage**:
   - Historical subdivisions and consolidations are modeled relationally.
7. **Finding ──► Action ──► Resolution Workflow**:
   - Discrepancies generate operational `RequiredAction` tasks assigned to certified Amins or Title Advocates.
8. **Versioned Legal Rules & Statutory Tenancy Engine**:
   - SPT Act Section 20 / CNT Act Section 46 tribal land protection is evaluated deterministically.
