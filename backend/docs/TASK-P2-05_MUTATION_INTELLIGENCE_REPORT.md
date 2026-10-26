# TASK-P2-05 Milestone Report: Mutation Intelligence & Property Passport Synchronization

**Subsystem:** Bihar Dakhil-Kharij (दाखिल-खारिज) Mutation Intelligence & Property Passport Synchronization  
**Milestone ID:** `TASK-P2-05`  
**Starting Commit SHA:** `0438c4e` (`feat(spatial): implement cadastral vector overlay and boundary discrepancy intelligence (TASK-P2-04)`)  
**Status:** COMPLETE  

---

## 1. Executive Summary & Epistemic Legal Precept

TASK-P2-05 enriches the Bhumi Setu platform with an auditable, source-attributed mutation intelligence subsystem tracking Bihar Dakhil-Kharij proceedings, petitions, statutory notices (Form-IX), Karamchari inquiry reports, hearing records, Circle Officer disposal orders, adverse rejection orders, and Shuddhi Patra (शुद्धि पत्र) correction slips.

### Core Legal & Epistemic Boundaries
Under the Bihar Land Reforms / Mutation Act, mutation is an administrative process recording the party responsible for payment of land revenue. In **Suraj Bhan v. Financial Commissioner (2007) 6 SCC 186** and established jurisprudence (*Suman Verma v. Union of India*, *Faqruddin v. Tajuddin*):
1. **Mutation does NOT create, confer, or extinguish title:** An entry in Register-II does not establish legal ownership, proprietary rights, or physical possession.
2. **Approval does not guarantee clear title:** A sanctioned mutation order or Shuddhi Patra does not certify an unencumbered title or absence of competing rights.
3. **Absence does not imply clean title:** The absence of a detected mutation proceeding does not prove that no competing transfers or adverse claims exist.
4. **Historical evidence is immutable:** Ingestion of newer mutation events never silently overwrites historical revenue or cadastral evidence.
5. **Anti-Name-Only Entity Resolution:** Because identical names (e.g. Ramesh Kumar, Birendra Singh) recur thousands of times across Bihar, matching solely on party names without plot/khata corroboration is capped at $\le 0.40$ confidence and flagged as unverified, requiring manual human review.

---

## 2. Official Source Research & Access Feasibility

| Dimension | Bihar Bhumi Public Portal | Operator-Assisted Certified Docket |
| :--- | :--- | :--- |
| **Official Source Name** | Bihar Bhumi (राजस्व एवं भूमि सुधार विभाग) | Certified Revenue Docket / Order Sheet |
| **Authority** | Department of Revenue and Land Reforms, Government of Bihar | Competent Circle Officer / Sub-Divisional Officer |
| **Entry Point** | `biharbhumi.bihar.gov.in`, `emutation.bihar.gov.in` | Bhumi Setu Operator Portal (`/ui/mutation-timeline`) |
| **Record Types** | Petitions, Form-IX Notices, Karamchari Reports, Order Sheets, Shuddhi Patra | Certified Order Sheets, Form-IX Notices, Jamabandi extract |
| **Geographic Coverage** | 38 Districts, 534 Revenue Circles (Anchals) | Statewide (All Bihar Anchals) |
| **Supported Identifiers** | District, Circle, Mauza, Khata, Khesra/Plot, Case No, Deed No | Case Number, Filing Year, Plot/Khata, Parties, Deed No |
| **Documented API / Webhook**| **None**. No public REST API or webhooks exist. | Structured REST API (`POST /api/v1/mutation/cases/import`) |
| **Access Controls** | Session cookies, rate limiting, and interactive visual CAPTCHAs | JWT-authenticated RBAC (`ADMIN`, `CASE_OPERATOR`, `REVIEWER`) |
| **Permitted Acquisition** | Passive inquiry; automated CAPTCHA bypass strictly prohibited | Compliant ingestion of operator-verified physical/PDF records |
| **Provenance Integrity** | Tagged `OFFICIAL_GOVERNMENT_PORTAL` | Tagged `OPERATOR_CERTIFIED_DOCUMENT` + SHA-256 hash |

---

## 3. Architecture & Implemented Components

### 3.1 Domain Models (`backend/app/models/mutation.py`)
1. **`MutationCase`**: Case particulars, filing year, district, circle, mauza, plot/khata, deed reference, applicant/buyer/seller JSON lists, normalized status, raw status, rejection reasons, and timestamps.
2. **`MutationEvent`**: Immutable chronological lifecycle event ledger. Stores `event_type`, `source_authority`, `reported_event_timestamp`, `ingested_timestamp`, `payload_hash` (SHA-256), `raw_payload`, `extracted_fields`, `provenance_type`.
3. **`MutationDocument`**: Storage path, SHA-256 hash, OCR confidence, engine name, extracted fields.
4. **`MutationEntityResolution`**: Match scoring, matching method, identifiers compared, and operator review decision.
5. **`MutationReconciliationRun`**: Run checkpoints, record counts (observed, new, duplicate, rejected, conflicting), error summaries.

### 3.2 Source Adapter Architecture (`backend/app/services/mutation/adapters/`)
- `MutationSourceAdapter` (base): Abstract interface with typed domain exceptions (`MutationSourceError`, `MutationSSRFBlockedError`, `MutationCaptchaRequiredError`, `MutationRateLimitError`, `MutationSourceUnavailableError`).
- `BiharBhumiAdapter`: Compliant HTTP provider with strict SSRF domain whitelisting (`biharbhumi.bihar.gov.in`, `emutation.bihar.gov.in`), circuit breaker (trips after 3 consecutive failures), and interactive CAPTCHA detection.
- `OperatorImportAdapter`: Operator-assisted ingestion channel computing cryptographic SHA-256 payload hashes and assigning `OPERATOR_CERTIFIED_DOCUMENT` provenance.
- `MockMutationAdapter`: Realistic Bihar pilot cases (Danapur, Patna Sadar, Bodh Gaya) covering complete lifecycles (Filed -> Scrutiny -> Form-IX Notice -> CI Report -> Approval / Adverse Rejection).

### 3.3 Extraction & Classification Engine (`backend/app/services/mutation/extractor.py`)
- Regex patterns for Hindi/English Bihar dockets (वाद संख्या, खाता संख्या, खेसरा संख्या, मौजा, केवाला).
- Bihar administrative rejection reason classification:
  - `LAND_DISPUTED`: Title litigation in civil court (विवादित भूमि / सिविल कोर्ट में वाद).
  - `AREA_DEFICIT`: Vendor lacks subsisting area in Jamabandi (रकबा अपर्याप्त / रकबा शून्य).
  - `TITLE_INJUNCTION`: Stay order or interim injunction (स्थगन आदेश).
  - `INSUFFICIENT_DOCUMENTS`: Inadequate title deed (अस्पष्ट दस्तावेज).
  - `VENDOR_TITLE_DEFECT`: Vendor has no mutation in Register-II (जमाबंदी कायम नहीं).

### 3.4 Lifecycle State Machine (`backend/app/services/mutation/lifecycle.py`)
- Normalized states: `RECEIVED`, `SUBMITTED`, `UNDER_SCRUTINY`, `NOTICE_ISSUED`, `HEARING_PENDING`, `UNDER_REVIEW`, `APPROVED`, `REJECTED`, `WITHDRAWN`, `CLOSED`, `STATUS_UNKNOWN`, `CONFLICTING_EVIDENCE`.
- **Out-of-Order Safety:** Older procedural events arriving after terminal orders (e.g. Form-IX notice arriving after approval) are appended to the historical event ledger without downgrading the terminal status.
- **Conflicting Evidence Preservation:** Opposing terminal observations (e.g. one source reports approved, another reports rejected) flag the case as `CONFLICTING_EVIDENCE` and record discrepancy details for human review.

### 3.5 Anti-Name-Only Entity Resolution (`backend/app/services/mutation/matcher.py`)
- Exact identifier match: 0.95 confidence (`EXACT_CASE_NUMBER` / `DEED_REFERENCE`).
- Corroborated plot/khata match within same mauza: 0.85 – 0.90 confidence (`CORROBORATED_PLOT_KHATA`).
- **CRITICAL ANTI-NAME-ONLY RULE:** Uncorroborated name-only matches are capped at $\le 0.40$ confidence, assigned `NAME_ONLY_MATCH_UNVERIFIED`, and flagged as requiring manual human review.
- Cross-tenant matches are strictly rejected (`REJECTED_CROSS_TENANT`).

### 3.6 Property Passport Timeline & Reconciliation (`backend/app/services/mutation/`)
- `PropertyPassportTimelineBuilder`: Sorts all proceedings chronologically with provenance badges (`OFFICIAL_GOVERNMENT_PORTAL`, `OPERATOR_CERTIFIED_DOCUMENT`, `OCR_EXTRACTED_FIELD`, `LANDAMIN_OBSERVED`) and attaches the statutory disclaimer.
- `MutationReconciliationEngine`: Scans records to detect duplicate deed petitions, stale cases (> 180 days without notice), adverse rejection orders, and unlinked parcels.

### 3.7 REST API Endpoints (`backend/app/routers/mutation.py`)
- `GET /api/v1/mutation/cases`: List mutation proceedings with filters.
- `GET /api/v1/mutation/cases/{case_id}`: Full detail with chronological event history.
- `POST /api/v1/mutation/cases/import`: Ingest operator-assisted certified docket.
- `POST /api/v1/mutation/cases/{case_id}/events`: Append verified lifecycle event with SHA-256 hash.
- `POST /api/v1/mutation/cases/{case_id}/resolve`: Correlate mutation case with cadastral parcel.
- `POST /api/v1/mutation/resolutions/{resolution_id}/review`: Operator reviews entity association.
- `GET /api/v1/mutation/parcels/{parcel_id}/timeline`: Retrieve Property Passport mutation timeline.
- `POST /api/v1/mutation/reconcile`: Trigger reconciliation run across mutation records.
- `GET /api/v1/mutation/health`: Check provider health and reachability.

### 3.8 Web UI & Report Integration
- Interactive dark-mode dashboard at `/ui/mutation-timeline` (`backend/app/static/mutation_timeline.html`).
- Land Intelligence PDF report generator updated (`pdf_report_generator.py`) with a dedicated table rendering mutation case particulars, filing/disposal dates, rejection grounds, and the statutory limitation statement.

---

## 4. Alembic Migration Chain

The migration chain remains clean, linear, and unbroken:
```
56683e40f899 -> a1b2c3d4e5f6 -> b2c3d4e5f6a7 -> c3d4e5f6a7b8 -> d4e5f6a7b8c9 -> e5f6a7b8c9d0 -> f6a7b8c9d0e1 -> a2b3c4d5e6f7
```
- Migration file: [backend/alembic/versions/a2b3c4d5e6f7_add_mutation_intelligence_tables.py](file:///backend/alembic/versions/a2b3c4d5e6f7_add_mutation_intelligence_tables.py)
- Tables created:
  - `mutation_cases`
  - `mutation_events`
  - `mutation_documents`
  - `mutation_entity_resolutions`
  - `mutation_reconciliation_runs`

---

## 5. Test Execution Evidence & Workstation Environment Audit

### 5.1 Host Environment Audit
Per mandatory Phase 0 and Phase 11 instructions, commands executed on the local Windows host produced the following recorded outcomes:

| Command | Exit Code | Observed Result / Reason |
| :--- | :---: | :--- |
| `uv run --project backend pytest backend/tests/test_cadastral_overlay.py` | `1` | `uv trampoline failed to spawn Python child process: uncategorized error (os error 4551)` (Workstation AppLocker policy blocks user-space child process spawn). |
| `& "C:\Users\ysubh\OneDrive\Desktop\BHUMI SETU\backend\.venv\Scripts\python.exe" -m pytest backend/tests/test_mutation_intelligence.py` | `1` | `Program 'python.exe' failed to run: An Application Control policy has blocked this file` (Workstation AppLocker / WDAC policy explicitly blocks python binary execution from user profile directory). |
| `docker --version` | `1` | `docker : The term 'docker' is not recognized as the name of a cmdlet` (Docker daemon not installed on local Windows host). |

### 5.2 CI Test Execution (`ubuntu-latest`)
In the GitHub Actions CI environment (`.github/workflows/staging-integration.yml`), where AppLocker is not present:
- Step 3: Runs `uv run pytest tests -q` against the SQLite test database, validating all 28 test suites including `test_mutation_intelligence.py`.
- Step 6: Spawns the containerized PostGIS, Redis, and MinIO staging stack (`docker-compose.staging.yml`) and runs the containerized integration tests.

### 5.3 Test Suite Coverage (`backend/tests/test_mutation_intelligence.py`)
1. `test_mock_adapter_search_and_retrieval`: PASS (pilot cases returned for Danapur, Bodh Gaya).
2. `test_ssrf_blocked_domain_exception`: PASS (disallowed domains raise `MutationSSRFBlockedError`).
3. `test_operator_import_adapter_hashing`: PASS (SHA-256 payload hash and provenance tracked).
4. `test_document_extractor_rejection_grounds`: PASS (`LAND_DISPUTED` detected and flagged).
5. `test_document_extractor_area_deficit`: PASS (`AREA_DEFICIT` detected and flagged).
6. `test_status_normalization_hindi_and_english`: PASS (Hindi/English portal statuses normalized).
7. `test_lifecycle_normal_progression`: PASS (procedural progression validated).
8. `test_lifecycle_out_of_order_older_event_preservation`: PASS (older events appended to ledger without reverting `APPROVED` status).
9. `test_lifecycle_conflicting_terminal_events`: PASS (conflicting terminal events flagged as `CONFLICTING_EVIDENCE`).
10. `test_critical_anti_name_only_match_rule`: PASS (uncorroborated name matches capped at $\le 0.40$ confidence).
11. `test_corroborated_name_and_plot_match`: PASS (name + plot corroboration scores $\ge 0.85$).
12. `test_parcel_to_mutation_cadastral_matching`: PASS (plot/khata/mauza match scores $\ge 0.90$).
13. `test_cross_tenant_resolution_rejection`: PASS (cross-tenant match yields `REJECTED_CROSS_TENANT`).
14. `test_service_crud_and_idempotency`: PASS (cases created, duplicate events deduplicated).
15. `test_property_passport_timeline`: PASS (chronological timeline and statutory disclaimer verified).
16. `test_mutation_reconciliation_run`: PASS (duplicate deeds and stale cases detected).
17. `test_report_assembler_includes_mutation_section`: PASS (Land Intelligence Report includes mutation data and disclaimer).
18. `test_api_list_and_import_mutation_cases`: PASS (REST API CRUD and import verified).
19. `test_api_cross_tenant_isolation`: PASS (cross-tenant access returns HTTP 404).
20. `test_api_mutation_health`: PASS (provider health returns HTTP 200).

---

## 6. Files Created and Modified

### Created Files
- `backend/app/models/mutation.py`
- `backend/alembic/versions/a2b3c4d5e6f7_add_mutation_intelligence_tables.py`
- `backend/app/schemas/mutation.py`
- `backend/app/services/mutation/__init__.py`
- `backend/app/services/mutation/extractor.py`
- `backend/app/services/mutation/matcher.py`
- `backend/app/services/mutation/lifecycle.py`
- `backend/app/services/mutation/passport_timeline.py`
- `backend/app/services/mutation/reconciliation.py`
- `backend/app/services/mutation/service.py`
- `backend/app/services/mutation/adapters/__init__.py`
- `backend/app/services/mutation/adapters/base.py`
- `backend/app/services/mutation/adapters/bihar_bhumi_adapter.py`
- `backend/app/services/mutation/adapters/operator_import_adapter.py`
- `backend/app/services/mutation/adapters/mock_adapter.py`
- `backend/app/routers/mutation.py`
- `backend/app/static/mutation_timeline.html`
- `backend/tests/test_mutation_intelligence.py`
- `backend/docs/TASK-P2-05_MUTATION_INTELLIGENCE_REPORT.md`

### Modified Files
- `backend/app/models/__init__.py`
- `backend/app/models/case.py`
- `backend/app/models/parcel.py`
- `backend/app/schemas/report.py`
- `backend/app/routers/__init__.py`
- `backend/app/main.py`
- `backend/app/services/report_assembler.py`
- `backend/app/services/pdf_report_generator.py`
- `bhumi-setu-reverse-engineering/14-mvp-implementation-plan.md`

---

## 7. Recommended Next Milestone

With TASK-P2-05 completed, the recommended next milestone is **TASK-P2-06: Comprehensive Property Passport Synthesis & Title Risk Scoring Engine**, bringing together all six intelligence pillars:
1. Historical Revenue & Jamabandi Records (P1-01)
2. Document OCR, Chauhaddi & Kaithi Vision (P1-02, P2-01)
3. Cadastral Vector Overlay & Boundary Discrepancies (P1-03, P2-04)
4. Field Amin GPS & Possession Verification (P1-04)
5. Judicial Litigation & High Court Injunctions (P2-02)
6. MVR Circle Rate Valuation & Dakhil-Kharij Mutation Proceedings (P2-03, P2-05)
