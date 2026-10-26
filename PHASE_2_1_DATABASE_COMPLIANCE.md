# BHUMISETU — PHASE 2.1 DATABASE COMPLIANCE REPORT
**Document Code:** BS-COMPLIANCE-DB-V1.1  
**Target Engine:** PostgreSQL 16 + PostGIS 3.4  
**Dialect:** `postgresql+psycopg` (psycopg v3)  
**Authoritative Reference:** `BHUMISETU_ARCHITECTURE_BLUEPRINT_V1.1.md`  

---

## 1. Schema Compliance Matrix Against Architecture V1.1

| V1.1 Entity Requirement | Actual Table Name | Implemented? | Key Constraints | Key Indexes | Architectural Notes & MVP Justification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tenant** | `organizations` | **YES** | PK: `org_id` (UUID), `name` NOT NULL, `slug` UNIQUE NOT NULL | `ix_organizations_slug` (UNIQUE) | Fundamental multi-tenant partition root. |
| **User** | `users` | **YES** | PK: `user_id` (UUID), FK: `org_id` (CASCADE), `email` UNIQUE NOT NULL | `ix_users_email` (UNIQUE), `ix_users_org_id` | Certified Amins, Title Advocates, and Operators with RBAC roles. |
| **Party** | `parties` | **YES** | PK: `party_id` (UUID), FK: `org_id` (CASCADE), `primary_name` NOT NULL | `ix_parties_canonical_transliterated_name`, `ix_parties_father_or_husband_name`, `ix_parties_org_id` | First-class object for buyers, sellers, raiyats, and legal entities. |
| **Parcel** | `parcels` | **YES** | PK: `parcel_id` (UUID), FK: `org_id` (CASCADE), `bhumi_id` UNIQUE NOT NULL | `ix_parcels_bhumi_id` (UNIQUE), `ix_parcels_census_village_code`, `ix_parcels_org_id` | Enduring land object. **Zero `current_owner` field**. Ownership flows through claims. |
| **ParcelVersion** | `parcel_versions` | **YES** | PK: `version_id` (UUID), FK: `parcel_id` (CASCADE), `version_number` NOT NULL | `ix_parcel_versions_parcel_id` | Historical extent and cadastral boundary evolution. |
| **ParcelRelationship**| `parcel_relationships`| **YES** | PK: `relationship_id` (UUID), FKs: `parent_parcel_id`, `child_parcel_id` | `ix_parcel_relationships_parent_parcel_id`, `ix_parcel_relationships_child_parcel_id` | Relational tree modeling subdivisions, partitions, and consolidations. |
| **Transaction** | `transactions` | **YES** | PK: `transaction_id` (UUID), FK: `org_id` (CASCADE), `transaction_type` NOT NULL | `ix_transactions_org_id` | Decoupled from Case. Supports independent real estate transactions. |
| **TransactionParty** | `transaction_parties` | **YES** | Composite PK: `(transaction_id, party_id)`, FKs with CASCADE | Index on FKs | Junction mapping multiple parties and transaction roles (Buyer, Seller). |
| **TransactionParcel**| `transaction_parcels`| **YES** | Composite PK: `(transaction_id, parcel_id)`, FKs with CASCADE | Index on FKs | Junction mapping multi-parcel land deals. |
| **Case** | `cases` | **YES** | PK: `case_id` (UUID), FKs: `org_id`, `primary_client_party_id`, `case_number` UNIQUE | `ix_cases_case_number` (UNIQUE), `ix_cases_org_id`, `ix_cases_status` | Verification workflow lifecycle state machine (`DRAFT` to `FINAL`). |
| **CaseParcel** | `case_parcels` | **YES** | Composite PK: `(case_id, parcel_id)`, FKs with CASCADE | Index on FKs | Junction associating parcels with verification cases. |
| **Document** | `documents` | **YES** | PK: `document_id` (UUID), `sha256_hash` NOT NULL, `file_size_bytes` NOT NULL | `ix_documents_sha256_hash` | Immutable raw physical upload files. |
| **DocumentPage** | `document_pages` | **YES** | PK: `page_id` (UUID), FK: `document_id` (CASCADE), `page_number` NOT NULL | `ix_document_pages_document_id` | Multi-page deed and khatiyan page decomposition. |
| **Evidence** | `evidence` | **YES** | PK: `evidence_id` (UUID), `sha256_hash` NOT NULL, `evidence_type` NOT NULL | `ix_evidence_sha256_hash` | Reusable epistemic vault object decoupled from case lifecycles. |
| **CaseEvidence** | `case_evidence` | **YES** | Composite PK: `(case_id, evidence_id)`, FKs with CASCADE | Index on FKs | Junction cross-referencing evidence across multiple historical cases. |
| **Claim** | `claims` | **YES** | PK: `claim_id` (UUID), FKs: `case_id`, `parcel_id`, `evidence_id` | `ix_claims_case_id`, `ix_claims_parcel_id`, `ix_claims_predicate`, `ix_claims_status` | Atomic Subject-Predicate-Object assertions with temporal validity dates. |
| **PropertyEvent** | `property_events` | **YES** | PK: `event_id` (UUID), FKs: `parcel_id`, `evidence_id` | `ix_property_events_parcel_id`, `ix_property_events_event_type` | Append-only chronological timeline of deed registrations, mutations, and liens. |
| **Finding** | `findings` | **YES** | PK: `finding_id` (UUID), FKs: `case_id`, `parcel_id`, `rule_id` NOT NULL | `ix_findings_case_id`, `ix_findings_parcel_id`, `ix_findings_rule_id`, `ix_findings_status`| Deterministic title defects and statutory restrictions. |
| **RequiredAction** | `required_actions` | **YES** | PK: `action_id` (UUID), FKs: `finding_id`, `case_id`, `action_type` NOT NULL | `ix_required_actions_finding_id`, `ix_required_actions_case_id`, `ix_required_actions_status` | Operational remediation tasks assigned to certified professionals. |
| **Resolution** | `resolutions` | **YES** | PK: `resolution_id` (UUID), FKs: `finding_id`, `action_id`, `resolving_evidence_id` | `ix_resolutions_finding_id`, `ix_resolutions_action_id` | Evidentiary proof sign-off required to resolve any finding. |
| **FieldSurvey** | `field_surveys` | **YES** | PK: `survey_id` (UUID), FKs: `case_id`, `parcel_id`, `amin_user_id` | `ix_field_surveys_case_id`, `ix_field_surveys_parcel_id` | Field Amin boundary observations and ETS/DGPS survey reports. |
| **LandPassport** | `land_passports` | **YES** | PK: `passport_id` (UUID), FK: `case_id` (CASCADE, UNIQUE), `passport_number` UNIQUE| `ix_land_passports_case_id` (UNIQUE), `ix_land_passports_passport_number` (UNIQUE) | Final digital due-diligence report certificate. |
| **AuditLog** | `audit_logs` | **YES** | PK: `log_id` (UUID), FK: `org_id` (CASCADE), `action`, `entity_name`, `entity_id` | `ix_audit_logs_org_id`, `ix_audit_logs_action`, `ix_audit_logs_entity_id`, `ix_audit_logs_created_at` | Append-only tamper-resistant system audit trail. |

---

## 2. Justification for Additional MVP Tables Beyond Base 17

The initial schema includes 23 tables (6 additional junction/supporting entities). All 6 directly serve core V1.1 requirements:
1. `transaction_parties`: **Why it exists:** Transactions involve multiple buyers, sellers, and consenting witnesses. Serves V1.1 Section 6 (M:N Party-Transaction cardinality).
2. `transaction_parcels`: **Why it exists:** Real estate transactions frequently bundle multiple plots/khesras. Serves V1.1 Section 6 (Multi-parcel transaction modeling).
3. `case_parcels`: **Why it exists:** Due-diligence cases frequently investigate family partitions or multi-plot holdings. Serves V1.1 Section 7 (M:N Case-Parcel cardinality).
4. `document_pages`: **Why it exists:** Multi-page sale deeds and cadastral survey registers must be decomposed for page-level OCR grounding. Serves V1.1 Section 10 (Page-level citation contract).
5. `field_surveys`: **Why it exists:** Separates physical boundary observations and ETS coordinate observations from legal boundaries. Serves V1.1 Section 14 (Field verification boundary).
6. `land_passports`: **Why it exists:** Stores the issued due-diligence report certificate, QR verification hash, and readiness sign-off. Serves V1.1 Section 16 (Digital Land Passport issuance).

---

## 3. Parcel Model Audit: Decoupled Ownership

- **Canonical Rule:** `parcels` table must NOT contain `current_owner`.
- **Compliance Status:** **VERIFIED COMPLIANT**.
- **Proof:** The `parcels` table contains only administrative geographic identifiers:
  - `state_code`
  - `district_name`
  - `subdistrict_anchal_name`
  - `halka_number`
  - `mauza_village_name`
  - `census_village_code`
  - `khata_number`
  - `plot_khesra_number`
  - `subdivision_hissa_number`
  - `recorded_area_acres`
  - `land_nature`
  - `centroid_point`
  - `authoritative_boundary`
- **Ownership Invariant:** Ownership is never an absolute attribute of a piece of dirt. It is an assertion (`Claim` with `predicate = 'RECORDED_OWNER'`) backed by `Evidence` (`Khatiyan`, `Registered Deed`, or `Panji II Jamabandi`) observed at a specific point in time.

---

## 4. Geospatial Foundation & PostGIS Audit

1. **SRID Enforcement:** All spatial geometries are explicitly tagged with `SRID=4326` (WGS 84).
2. **Authoritative vs Field Measured Boundary:**
   - `parcels.authoritative_boundary`: Cadastral map geometry sourced from government surveys.
   - `field_surveys.measured_boundary`: Field Amin GNSS/ETS demarcation boundary.
   - Field observations are explicitly treated as observational evidence, never as self-authenticating legal title.
3. **Spatial Indexing:** Configured with `spatial_index=True`, instructing GeoAlchemy2 to create PostgreSQL GIST indexes (`CREATE INDEX idx_parcels_centroid_point ON parcels USING GIST (centroid_point)`).
4. **Area Calculation:** Documented in square meters and acres. Measured area calculations are treated as physical telemetry and evaluated against recorded deed area via the deterministic consistency engine (`check_area_delta`).

---

## 5. Epistemic Claim Engine & Temporal Validity

1. **Atomic Structure:** Every claim contains `subject_id`, `subject_entity_type`, `predicate`, and `object_value`.
2. **Competing Claims Coexistence:**
   - Validated in `tests/test_domain.py::test_competing_claims_coexistence`.
   - Khatiyan claim (`Party A` recorded owner) and Registered Deed claim (`Party B` transferee) coexist simultaneously without clobbering.
3. **Source Authority vs Extraction Confidence:**
   - Stored in distinct, decoupled columns:
     - `authority_tier`: `STATUTORY_REGISTRY` (High), `REVENUE_RECORD` (High), `USER_SUBMISSION` (Low).
     - `confidence_score`: Extraction accuracy (e.g. 0.98 for certified digital extract, 0.65 for degraded scanned deed).
4. **Temporal History:**
   - `observed_at`: Date when record was ingested/verified.
   - `recorded_at`: Date when government ledger entry was executed.
   - `effective_from` & `effective_to`: Temporal validity window.
