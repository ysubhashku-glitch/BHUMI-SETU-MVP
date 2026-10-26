# BHUMI SETU — CANONICAL TECHNICAL ARCHITECTURE (v1.1)
**Canonical Hardened Reference:** [BHUMISETU_ARCHITECTURE_BLUEPRINT_V1.1.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/05_Research_and_Technical_Specs/BHUMISETU_ARCHITECTURE_BLUEPRINT_V1.1.md)  
**Implementation Status:** PHASE 2.1 COMPLETE (Hardened Backend Foundation & Infrastructure Compliance Audit)  
**Latest Audit:** [PHASE_2_1_IMPLEMENTATION_REPORT.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_2_1_IMPLEMENTATION_REPORT.md)  

---

## 1. Implementation Status Overview (Phase 2.1 Hardened)

| Layer | Component | Status | Implementation Details |
| :--- | :--- | :--- | :--- |
| **Database Engine** | PostgreSQL 16 + PostGIS 3.4 | **HARDENED** | Target dialect configured to `postgresql+psycopg` (v3). `docker-compose.yml` defining `postgis/postgis:16-3.4` created. Live runtime requires Docker daemon or external connection. |
| **Schema & Migrations**| Alembic + PostGIS Ext | **HARDENED** | 23 tables defined via SQLAlchemy 2.0. Alembic `env.py` hooks automatically create `postgis` and `uuid-ossp` extensions on upgrade. |
| **Multi-Tenancy** | Backend Tenant Isolation | **HARDENED** | Enforced at data-access layer via `org_id`. 6 adversarial tests prove cross-tenant access rejection (`CROSS_TENANT_ACCESS_DENIED`, HTTP 403). |
| **Storage Boundary** | Object Storage Abstraction | **HARDENED** | `BaseStorageAdapter` with `LocalStorageAdapter` and `S3StorageAdapter` (`NOT_CONNECTED`). No fake S3 representation. |
| **Document Boundary** | Phase 3 Interface Definition| **HARDENED** | Clean abstract interfaces in `app/core/document_boundary.py` (`DocumentProcessor`, `DocumentParser`, `EvidenceExtractor`, `ClaimCandidateGenerator`). Zero premature dependencies. |
| **Data Minimization** | Sensitive Party Data | **HARDENED** | Generic caste profiling removed. Retained only statutory tribal markers (`is_tribal`) strictly required by SPT Act Sec 20 / CNT Act Sec 46. |
| **Test Suite** | Pytest Automation | **PASSED (21/21)**| 21 tests passing (100% pass rate) covering DB constraints, API, domain rules, state machines, adversarial security, and vertical slice. |

---

## 2. Canonical Phase 2.1 Deliverables

1. **Forensic Audit:** [PHASE_2_1_FORENSIC_AUDIT.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_2_1_FORENSIC_AUDIT.md)
2. **Database Compliance:** [PHASE_2_1_DATABASE_COMPLIANCE.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_2_1_DATABASE_COMPLIANCE.md)
3. **Security Audit:** [PHASE_2_1_SECURITY_AUDIT.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_2_1_SECURITY_AUDIT.md)
4. **Test Report:** [PHASE_2_1_TEST_REPORT.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_2_1_TEST_REPORT.md)
5. **Implementation Report:** [PHASE_2_1_IMPLEMENTATION_REPORT.md](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/PHASE_2_1_IMPLEMENTATION_REPORT.md)

---

## 3. Core Architectural Invariants (v1.1 Canonical)

1. **Decoupled Domain Objects**:
   - `Parcel`, `Case`, and `Transaction` are independent entities with explicit M:N cardinalities.
   - A case can investigate multiple parcels; a parcel accumulates cases over decades.

2. **Decoupled Evidence Ownership**:
   - Evidence belongs to the Evidence Vault, not a single case (`Evidence` $\longleftrightarrow$ `CaseEvidence` $\longleftrightarrow$ `Case`).
   - The same registered deed or survey can support multiple historical cases.

3. **First-Class Party Model**:
   - `Party` (Person, Organization, Trust, HUF) exists as an independent master domain object with ownership shares, family relations, and caste/community attributes essential for statutory tenancy audits.

4. **Temporal Claims & Competing Truth**:
   - Claims feature explicit temporality (`observed_at`, `recorded_at`, `effective_from`, `effective_to`).
   - Conflicting claims from deeds and revenue records coexist concurrently without destructive overwrites.

5. **Relational Parcel Lineage**:
   - `ParcelVersion` and `ParcelRelationship` model historical subdivisions, partitions, consolidations, and renumberings relationally.

6. **Legal Boundary vs Measured Boundary**:
   - Field GNSS/RTK observations represent physical boundary evidence, **not** statutory legal title.
   - Clear area taxonomy: `RECORDED_AREA`, `MEASURED_AREA`, `AUTHORITATIVE_AREA`, and `LEGAL_AREA`.

7. **Finding ──► Action ──► Resolution Workflow**:
   - Findings automatically generate operational `RequiredAction` tasks assigned to certified Amins or Title Advocates with managed resolution states.

8. **Versioned Legal Rules & Statutory Tenancy Engine**:
   - Santhal Parganas Tenancy (SPT) Act Section 20 tribal protection is modeled as a versioned, auditable rule distinguishing source law, executable code, and human advocate review.

9. **Grounded AI Land Expert**:
   - Read-only RAG assistant bound by a strict 6-point grounding contract (`ANSWER`, `EVIDENCE`, `SOURCE`, `CONFIDENCE`, `UNCERTAINTY`, `NEXT ACTION`). Prohibited from modifying canonical data.

10. **Digital Land Passport & Integrity QR**:
    - PDF deliverable sealed with SHA-256 hash. QR code verifies document integrity against the BhumiSetu ledger (explicitly distinguished from government statutory authentication).
