# TASK-P2-07.2 — Production Provenance Enforcement & Pilot Acceptance Report

**Project:** Bhumi Setu MVP  
**Component:** Backend Valuation Intelligence, Upstream Trust Boundaries, Property Passport Reconciliation & Staging Infrastructure  
**Author:** Antigravity Agentic Assistant  
**Date:** October 27, 2026  
**Final Release Verdict:** **`ENGINEERING VERIFIED — OPERATIONAL GATES OPEN`**  

---

## 1. Executive Summary & Audit Lineage

This audit report delivers the definitive evidence-based qualification for **TASK-P2-07.2 (Production Provenance Enforcement and Pilot Acceptance Verification)** on the Bhumi Setu MVP codebase.

Building upon the prior audits (TASK-P2-07 and TASK-P2-07.1), this milestone enforces unyielding trust boundaries across the Minimum Valuation Register (MVR) circle rate calculation subsystem, upstream Property Passport evidence synthesis, and Land Intelligence Report generation. It eliminates all synthetic data leakage, mandates cryptographically verifiable provenance on government schedules, prevents privilege escalation on schedule verification, and establishes that software verification alone cannot be conflated with operational legal sign-off or physical field calibration.

### 1.1 Repository State & Audit Lineage

| Parameter | Authoritative Value / Reference |
| :--- | :--- |
| **Repository URL** | [https://github.com/ysubhashku-glitch/BHUMI-SETU-MVP.git](https://github.com/ysubhashku-glitch/BHUMI-SETU-MVP.git) |
| **Target Branch** | `main` |
| **Audit Baseline Commit SHA** | [`394ffc3e22789b4007bbc75bcb14797aa65fc287`](https://github.com/ysubhashku-glitch/BHUMI-SETU-MVP/commit/394ffc3) (`docs(pilot): complete TASK-P2-07.1 pilot gate closure and domain acceptance audit`) |
| **Full Regression Suite Execution** | **327 PASSED**, **9 SKIPPED**, **0 FAILED**, **0 ERRORS** (111.34s) |
| **Adversarial Provenance Suite** | **12 PASSED**, **0 FAILED** (7.49s in `test_valuation_provenance_adversarial.py`) |
| **Core MVR & Valuation Suite** | **19 PASSED**, **0 FAILED** (4.95s in `test_valuation_mvr.py`) |
| **Property Passport Synthesis Suite** | **25 PASSED**, **0 FAILED** (9.78s in `test_property_passport_synthesis.py`) |
| **Persistence Lifecycle Suite** | **2 PASSED**, **0 FAILED** (1.56s in `test_verify_persistence.py`) |
| **Staging Integration Container Tests** | **9 SKIPPED** (Preserved for live container environment execution) |
| **Alembic Database Head** | Single linear head [`c4d5e6f7a8b9`](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/backend/alembic/versions/c4d5e6f7a8b9_add_mutation_case_fields.py) on PostGIS 16 |
| **Executive Release Verdict** | **`ENGINEERING VERIFIED — OPERATIONAL GATES OPEN`** |

---

## 2. Summary of Engineering Changes and Architectural Rationale

### 2.1 MVR Model and Schema Trust Boundary Hardening
- **File:** [`backend/app/models/valuation.py`](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/backend/app/models/valuation.py)
  - Defined explicit provider classification constants:
    - `AUTHORIZED_OFFICIAL_VALUATION_PROVIDERS = ("OPERATOR_ASSISTED_IMPORT", "ENIBANDHAN_PORTAL", "BIHAR_REVENUE_DEPT")`
    - `SYNTHETIC_MOCK_VALUATION_PROVIDERS = ("MOCK_PROVIDER", "SYNTHETIC_MOCK", "SYNTHETIC_FIXTURE", "TEST_FIXTURE")`
  - Hardened `MVRSchedule.verification_status` column default to `ScheduleVerificationStatus.PROVISIONAL` (formerly defaulted to `UNVERIFIED`). Newly created or imported schedules cannot be initialized as verified.
- **File:** [`backend/app/schemas/valuation.py`](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/backend/app/schemas/valuation.py)
  - Synchronized Pydantic models `MVRScheduleRecord`, `MVRScheduleImportPayload`, and `MVRScheduleResponse` to default `verification_status` to `PROVISIONAL`.

### 2.2 Valuation Service & Operator Ingestion Protection
- **File:** [`backend/app/services/valuation/service.py`](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/backend/app/services/valuation/service.py)
  - **Strict Role Enforcement:** In `verify_schedule`, verified that `user_role` is strictly `ADMIN` or `SUPERVISOR`. Ordinary users (`FIELD_AMINT`, `OPERATOR`, `CLIENT_BUYER`) are rejected with `HTTP 403 / ValueError`.
  - **Prohibition of Synthetic Promotion:** If `schedule.source_provider` belongs to `SYNTHETIC_MOCK_VALUATION_PROVIDERS` or contains `"MOCK"` / `"SYNTH"`, promotion to `VERIFIED_OFFICIAL` is prohibited by raising `ValueError("Cannot verify synthetic or mock rate schedule as official government record.")`.
  - **Gazette Citation Integrity:** Verified that `source_gazette_reference` has at least 5 characters and does not match placeholder values (`NONE`, `N/A`, `NULL`, `TEST`).
  - **Schedule Road Frontage Matching:** Separated exact road category matching from fallback matching in `calculate_and_assess_property`. Exact road category matches (`MAIN_ROAD_NH_SH` vs `VILLAGE_ROAD`) are selected over fallback matches regardless of verification status.
  - **Comprehensive Audit Logging:** Emitted structured `AuditLog` events for:
    - `MVR_SCHEDULE_IMPORTED`: Record of import with user ID, SHA-256 payload digest, and provisional status.
    - `MVR_SCHEDULE_VERIFIED`: Record of supervisor approval with gazette notification citation.
    - `MVR_SCHEDULE_VERIFY_UNAUTHORIZED`: Record of unauthorized verification attempts.
- **File:** [`backend/app/services/valuation/providers/operator_import.py`](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/backend/app/services/valuation/providers/operator_import.py)
  - Mandated that `source_gazette_reference` is provided and non-empty on imported rows.
  - Stripped any client-supplied `verification_status` label (e.g., `VERIFIED_OFFICIAL`) and forced newly imported records into `ScheduleVerificationStatus.PROVISIONAL`.

### 2.3 Upstream Evidence Reconciliation Engine Gate Hardening
- **File:** [`backend/app/services/passport/reconciliation_engine.py`](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/backend/app/services/passport/reconciliation_engine.py)
  - Implemented 7 deterministic gate checks for valuation records:
    - **Gate A (`GAP-VAL-SYNTHETIC-DATA-EXCLUDED`):** Synthetic/mock schedules are excluded from production assessments with `is_blocking: True`.
    - **Gate B (`GAP-VAL-UNTRUSTED-PROVIDER`):** Schedules from unapproved third-party or unknown providers trigger a blocking gap.
    - **Gate C (`GAP-VAL-MISSING-GAZETTE-REFERENCE`):** Schedules lacking published District Collectorate gazette references trigger a blocking gap.
    - **Gate D (`GAP-VAL-SUPERSEDED-SCHEDULE`):** Deactivated or superseded schedules trigger a blocking gap requiring recalculation.
    - **Gate E (`GAP-VAL-EXPIRED-SCHEDULE`):** Schedules past their statutory validity period trigger a blocking gap.
    - **Gate F (`GAP-VAL-UNVERIFIED-SCHEDULE`):** Schedules in `PROVISIONAL` or `UNVERIFIED` status are blocked from authoritative valuation facts.
    - **Gate G (`GAP-VAL-JURISDICTION-MISMATCH`):** Administrative mismatch between schedule district/mauza and parcel district/mauza triggers a blocking gap.
  - In explicit test fixture mode (`include_synthetic_fixtures=True`), Gates B through G are skipped for identified synthetic fixtures, allowing end-to-end testing of downstream scoring without live gazettes.

### 2.4 PDF Report Generation Graceful Degradation
- **File:** [`backend/app/services/pdf_report_generator.py`](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/backend/app/services/pdf_report_generator.py)
  - Prevented report generation crashes when valuation facts are absent or blocked.
  - Rendered a high-visibility amber statutory warning box:
    > *"NO OFFICIAL VALUATION ADMITTED: Official published Collectorate schedule not verified or synthetic data excluded."*

---

## 3. Adversarial Provenance Regression Test Results

A dedicated adversarial regression test suite was constructed in [`backend/tests/test_valuation_provenance_adversarial.py`](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/backend/tests/test_valuation_provenance_adversarial.py). All 12 test cases passed cleanly:

| # | Test Case Identifier | Adversarial Attack / Boundary Tested | Expected Defense Behavior | Result |
| :-: | :--- | :--- | :--- | :-: |
| **01** | `test_01_mock_schedule_marked_verified_official_rejected` | Injection of `MOCK_PROVIDER` schedule flagged as `VERIFIED_OFFICIAL` with official gazette string. | `reconciliation_engine` detects mock provider, rejects admission, emits `GAP-VAL-SYNTHETIC-DATA-EXCLUDED` (`is_blocking: True`). | **PASSED** |
| **02** | `test_02_synthetic_schedule_with_official_looking_code_rejected` | Synthetic schedule with disguised code (`MVR-OFFICIAL-2026-PAT-001`) and legitimate-looking rates. | Engine identifies `SYNTHETIC_MOCK` source provider; strictly excludes and emits blocking gap. | **PASSED** |
| **03** | `test_03_unknown_untrusted_provider_blocked` | Schedule ingested with unknown source provider (`EXTERNAL_SCRAPER_UNOFFICIAL`). | Engine blocks admission, surfaces `GAP-VAL-UNTRUSTED-PROVIDER` (`is_blocking: True`). | **PASSED** |
| **04** | `test_04_missing_or_invalid_gazette_reference_blocked` | Schedule with missing, short (`"ABC"`), or placeholder (`"NONE"`, `"TEST"`) gazette reference. | Blocked from facts, surfaces `GAP-VAL-MISSING-GAZETTE-REFERENCE` (`is_blocking: True`). | **PASSED** |
| **05** | `test_05_expired_and_superseded_schedules_blocked` | Schedules with expired `effective_to` dates or marked `SUPERSEDED` / `is_active=False`. | Blocked from facts; surfaces `GAP-VAL-EXPIRED-SCHEDULE` and `GAP-VAL-SUPERSEDED-SCHEDULE`. | **PASSED** |
| **06** | `test_06_jurisdiction_mismatch_blocked` | Valuation calculated using Gaya Town schedule applied to a Patna Danapur parcel. | Engine verifies jurisdiction mismatch, surfaces `GAP-VAL-JURISDICTION-MISMATCH` (`is_blocking: True`). | **PASSED** |
| **07** | `test_07_unauthorized_verification_attempts_blocked_and_logged` | Field Amin or unprivileged Operator attempting to call `verify_schedule`. | Service rejects attempt with `ValueError / 403` and records `MVR_SCHEDULE_VERIFY_UNAUTHORIZED` audit log. | **PASSED** |
| **08** | `test_08_client_verification_labels_stripped_on_import` | Operator import payload attempting to inject `"verification_status": "VERIFIED_OFFICIAL"`. | Import provider overrides label and forces schedule to `PROVISIONAL`. | **PASSED** |
| **09** | `test_09_property_passport_mixed_trusted_and_untrusted_evidence` | Assessment with verified land records, verified court dockets, but provisional unverified valuation. | Passport synthesizes valid subsystems but retains blocking valuation gap, forcing tier to `INSUFFICIENT_EVIDENCE`. | **PASSED** |
| **10** | `test_10_pdf_generation_when_valuation_blocked` | PDF report generation for a parcel where valuation is completely blocked or excluded. | Report compiles successfully; replaces valuation table with statutory non-admission disclaimer. | **PASSED** |
| **11** | `test_11_recalculation_after_schedule_supersession` | Deactivating old schedule and verifying new official schedule for same mauza. | Recalculation attaches new verified schedule, resolves blocking gap, and admits valuation fact. | **PASSED** |
| **12** | `test_12_audit_log_preservation_for_verification_and_imports` | Verification workflow audit log persistence. | Audit log records `MVR_SCHEDULE_IMPORTED` and `MVR_SCHEDULE_VERIFIED` with actor IDs and timestamps. | **PASSED** |

---

## 4. Full Regression Verification Evidence

Execution of the entire test suite on the unified environment:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\ysubh\OneDrive\Desktop\BHUMI SETU\backend
configfile: pyproject.toml
plugins: anyio-4.15.1, asyncio-1.4.0
collected 336 items

tests\test_api.py .....                                                  [  1%]
tests\test_bhunaksha_adapter.py ....................                     [  7%]
tests\test_bihar_bhumi_adapter.py ..............                         [ 11%]
tests\test_cadastral_overlay.py .....................                    [ 17%]
tests\test_celery_worker.py ......                                       [ 19%]
tests\test_containerized_staging_integration.py sssssssss                [ 22%]
tests\test_database.py ....                                              [ 23%]
tests\test_document_intelligence.py .................                    [ 28%]
tests\test_document_pipeline.py .......                                  [ 30%]
tests\test_domain.py .....                                               [ 32%]
tests\test_geospatial_and_migration_audit.py ...........                 [ 35%]
tests\test_health_and_observability.py .........                         [ 38%]
tests\test_judicial_risk.py ..............                               [ 42%]
tests\test_kaithi_vision.py ..............                               [ 46%]
tests\test_landamin_dispatcher.py .................                      [ 51%]
tests\test_mcp_server.py .................                               [ 56%]
tests\test_mutation_intelligence.py ....................                 [ 62%]
tests\test_p1_end_to_end_audit.py .                                      [ 62%]
tests\test_property_passport_synthesis.py .........................      [ 70%]
tests\test_report_generator.py ............                              [ 73%]
tests\test_security.py ......                                            [ 75%]
tests\test_security_audit.py ...................                         [ 81%]
tests\test_staging_configuration.py ......................               [ 87%]
tests\test_staging_smoke.py .                                            [ 88%]
tests\test_storage_s3_minio.py ......                                    [ 89%]
tests\test_valuation_mvr.py ...................                          [ 95%]
tests\test_valuation_provenance_adversarial.py ............              [ 99%]
tests\test_verify_persistence.py ..                                      [ 99%]
tests\test_vertical_slice.py .                                           [100%]

=========== 327 passed, 9 skipped, 6 warnings in 111.34s (0:01:51) ============
```

---

## 5. Controlled Pilot Operational Acceptance Matrix

The operational gate matrix separates verification into three distinct categories:
1. **Software Correctness (Code & Logic):** Deterministic execution of mathematical, architectural, and dataflow rules.
2. **Source-Data Acceptance:** Authenticity and statutory admissibility of real-world administrative records.
3. **External Operational Acceptance:** Professional sign-offs, legal opinions, and physical field calibrations.

| Gate # | Operational Dimension | Gate Requirement | Status | Concrete Evidence / Reason |
| :-: | :--- | :--- | :---: | :--- |
| **G-01** | **Software Provenance Controls** | Synthetic and mock data blocked from production synthesis; role-based verification enforced. | **`PASSED`** | Tested via 12 adversarial test cases in `test_valuation_provenance_adversarial.py`. |
| **G-02** | **Multi-Tenant Isolation** | Strict `org_id` segregation across all database queries, uploads, and calculations. | **`PASSED`** | Verified across API routes and synthesis service; tenant cross-access raises 404/403. |
| **G-03** | **Statutory Fee Logic (Software)** | Section 47-A base, gender concessions (5.6% / 5.8%), PMC surcharge (2%), and registration fee (2%). | **`PASSED`** | Deterministically implemented and verified in `StampDutyEngine` (19 tests in `test_valuation_mvr.py`). |
| **G-04** | **Spatial Overlay Metrology** | ICP errors separated from GCP residuals; regional CRSs recognized; EPSG:32645 computation. | **`PASSED`** | Verified in `test_cadastral_overlay.py` with affine solver and independent check-point validation. |
| **G-05** | **Anti-Name-Only Entity Resolution** | Uncorroborated name matches capped at $\le 0.40$ confidence; human review required. | **`PASSED`** | Verified in judicial and mutation matchers; name-only records never auto-confirm title. |
| **G-06** | **PDF Disclaimers & Disclosures** | Mandatory non-title certification disclosure, SHA-256 digest, and statutory valuation caveat. | **`PASSED`** | Verified in `test_report_generator.py` and `test_09` adversarial test. |
| **G-07** | **Official Gazette Schedule Ingestion** | Ingestion of published District Collectorate MVR notifications for pilot mauzas. | **`OPEN`** | **Pending Operator Action:** Verified Collectorate gazette PDFs for target pilot mauzas must be ingested via `/api/v1/valuation/schedules/import`. |
| **G-08** | **Qualified Legal Review** | Formal legal review of statutory fee rules and deed exceptions by a qualified Bihar revenue advocate. | **`OPEN`** | **Pending External Action:** Formal advocate memorandum must be executed and filed in `docs/legal/`. |
| **G-09** | **Physical GNSS RTK Calibration** | DGPS/RTK ground base station calibration against Survey of India GCPs for pilot village. | **`OPEN`** | **Pending Field Action:** Licensed surveyor ground control survey must confirm independent check point RMSE $< 2.50\text{m}$. |
| **G-10** | **Live e-Nibandhan API Ingestion** | Autonomous connectivity or certified operator ingestion pipeline for e-Nibandhan portal. | **`OPEN`** | Portal CAPTCHA defenses require operator-assisted ingestion channel with supervisor verification. |

---

## 6. Explicit Production and Pilot Restrictions

Until all open operational gates (G-07, G-08, G-09, G-10) are formally evidenced and signed off, the following operational constraints are binding:

1. **No Authoritative Financial Sanctions:** Bhumi Setu Property Passports and Valuation Assessments must **not** be used as the sole basis for loan disbursements, stamp duty payments, or statutory registration without manual collectorate schedule verification.
2. **Supervised Pilot Scope Only:** Live usage is strictly restricted to controlled pilot mauzas (e.g., Mustafapur, Kotwa in Danapur Anchal) under supervisor review.
3. **No Automatic Title Certification:** The system must never issue a certification of clear legal title. Every generated document must retain the statutory caveat:
   > *"Bhumi Setu is a technical diligence and risk synthesis decision-support tool. It does NOT certify legal title, cadastral boundaries, or statutory ownership."*
4. **Mock Provider Exclusion in Production:** Deployments with `ENVIRONMENT=production` must strictly maintain `include_synthetic_fixtures=False`.

---

## 7. Next Operator Actions

To transition from **`ENGINEERING VERIFIED — OPERATIONAL GATES OPEN`** to **`PILOT ACCEPTANCE APPROVED`**, the operating team must complete the following steps:

1. **Operator Ingestion of Pilot Gazette (Gate G-07):**
   - Obtain official Patna District Collectorate Minimum Valuation Register notification for Danapur Anchal (Mauza Mustafapur and Mauza Kotwa).
   - Ingest schedules using the administrative endpoint `POST /api/v1/valuation/schedules/import` with official notification reference (e.g., `"Patna District Gazette Notification No. 412/Reg-2025"`).
   - Have an authorized `SUPERVISOR` or `ADMIN` approve the imported schedules via `POST /api/v1/valuation/schedules/{id}/verify`.
2. **Qualified Revenue Advocate Memorandum (Gate G-08):**
   - Provide the statutory fee rules table (Section 3 of TASK-P2-07.1) to retained Bihar revenue counsel.
   - Obtain written verification of applicability for the specific pilot land categories.
3. **Field Amin Ground Control Demarcation (Gate G-09):**
   - Depute LandAmin equipped with calibrated DGPS/RTK rover to establish village tri-junction (sehadana) ground control points for the target pilot sheets.
   - Record independent check point coordinates to confirm RMSE $< 2.50\text{m}$.
