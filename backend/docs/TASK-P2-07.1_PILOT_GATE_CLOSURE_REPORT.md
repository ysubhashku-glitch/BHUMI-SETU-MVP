# TASK-P2-07.1 — Pilot Gate Closure & Evidence-Based Acceptance Audit Report

**Project:** Bhumi Setu MVP  
**Component:** Backend Intelligence Core, Property Passport Synthesis & Staging Infrastructure  
**Author:** Antigravity Agentic Assistant  
**Date:** October 27, 2026  
**Final Release Verdict:** **`CONDITIONALLY READY — SPECIFIC GATES REMAIN`**  

---

## 1. Executive Summary & Audit Context

This audit report delivers the final evidence-based qualification for **TASK-P2-07.1 (Pilot Gate Closure and Evidence-Based Acceptance Audit)**, completing the controlled Bihar pilot readiness assessment for Bhumi Setu.

Building upon the code-hardening and spatial metrology delivered in TASK-P2-07, this milestone resolves technical discrepancies, corrects misleading assumptions regarding legal title and verification tokens, hardens synthetic valuation exclusion gates, reconciles coordinate reference system policies, and establishes an unyielding, defensible go/no-go matrix based strictly on verified evidence.

### 1.1 Repository State & Tested CI Workflow Lineage

| Parameter | Authoritative Value / Reference |
| :--- | :--- |
| **Repository URL** | [https://github.com/ysubhashku-glitch/BHUMI-SETU-MVP.git](https://github.com/ysubhashku-glitch/BHUMI-SETU-MVP.git) |
| **Target Branch** | `main` |
| **Prior Reported Milestone** | TASK-P2-07 (`1e3388b` / `4d1d616`) |
| **Final Validated Release SHA** | Commit [`798381c`](https://github.com/ysubhashku-glitch/BHUMI-SETU-MVP/commit/798381c) (`feat(audit): complete TASK-P2-07.1 pilot gate closure`) |
| **Final Validated Workflow Run** | [Run 40482137233](https://github.com/ysubhashku-glitch/BHUMI-SETU-MVP/actions/runs/40482137233) (`status: completed` • **`conclusion: success`**) |
| **Prior Green Workflow Runs** | [Run 40473839790](https://github.com/ysubhashku-glitch/BHUMI-SETU-MVP/actions/runs/40473839790) (Code `4d1d616`) & [Run 40474545829](https://github.com/ysubhashku-glitch/BHUMI-SETU-MVP/actions/runs/40474545829) (Docs `1e3388b`) |
| **Host Regression Suite Passed** | **315 PASSED**, **9 SKIPPED**, **0 FAILED**, **0 ERRORS** (63.87s) |
| **Alembic Database Head** | Single linear head [`c4d5e6f7a8b9`](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/backend/alembic/versions/c4d5e6f7a8b9_add_mutation_case_fields.py) on PostGIS 16 |
| **Live Staging Integration Tests** | **9 PASSED**, **0 FAILED** (3.05s) |
| **18-Step Staging Smoke Test** | **1 PASSED**, **0 FAILED** (2.40s) |
| **Container State Persistence** | **PASSED** (PostgreSQL & MinIO data retained across container restart) |

### 1.2 Verification of Lineage and Code Changes
- **Commit `1e3388b`:** Audited via `git diff 4d1d616..1e3388b`. Modified solely `TASK-P2-07_CONTROLLED_PILOT_READINESS_REPORT.md` (6 insertions, 6 deletions), synchronizing reported CI run ID and test count to match actual CI execution. No code, configuration, migration, or Dockerfile changes were included. Workflow Run `40474545829` confirmed 100% green status.
- **Commit `798381c`:** Implemented synthetic fixture exclusion hardening in `reconciliation_engine.py` (covering `MOCK_PROVIDER` and setting `is_blocking: True` on `GAP-VAL-SYNTHETIC-DATA-EXCLUDED`), added regression test `test_reconciliation_mock_provider_exclusion` in `test_property_passport_synthesis.py` (expanding suite to 315 passed tests), and created this acceptance report. Workflow Run `40482137233` confirmed 100% green status across all 17 stages.

---

## 2. MVR Source-of-Truth & Synthetic Fixture Controls

### 2.1 Audit of Valuation Providers
Three distinct valuation providers exist within `backend/app/services/valuation/providers/`:
1. **`EnibandhanValuationProvider`:** Live scraper for Bihar e-Nibandhan portal (`registration.bihar.gov.in`). Features domain whitelisting, circuit breaking, and CAPTCHA detection. In staging and air-gapped environments, portal CAPTCHA and session timeouts prevent autonomous live harvesting.
2. **`MockValuationProvider`:** Seeded offline provider containing 24 canonical rate schedules across Patna (Danapur, Patna Sadar, Bakhtiyarpur), Gaya (Bodh Gaya, Gaya Town), and Saran (Chapra). These schedules carry `"source_provider": "MOCK_PROVIDER"`.
3. **`OperatorImportValuationProvider`:** Administrative ingestion pipeline for verified District Collectorate gazettes, assigning `"source_provider": "OPERATOR_ASSISTED_IMPORT"` and `ScheduleVerificationStatus.VERIFIED_OFFICIAL`.

### 2.2 Critical Vulnerability Identified & Remediated
Prior to this audit, `reconciliation_engine.py` checked:
```python
is_synthetic = (
    (sched_ver in ("SYNTHETIC", "SYNTHETIC_MOCK", "SYNTHETIC_FIXTURE"))
    or (sched and getattr(sched, "source_provider", "") in ("SYNTHETIC_MOCK", "SYNTHETIC_FIXTURE"))
    or ("mock" in (sched.schedule_code.lower() if sched else ""))
    or ("synth" in (sched.schedule_code.lower() if sched else ""))
)
```
In `MockValuationProvider`, seeded schedules have codes such as `MVR-BR-PAT-DAN-KOT-AGR-NH` (no "mock" or "synth" substring) and are marked `"verification_status": "VERIFIED_OFFICIAL"` with `"source_provider": "MOCK_PROVIDER"`. Because `"MOCK_PROVIDER"` was omitted from the tuple, these seeded schedules could bypass synthetic exclusion and be treated as production data!

**Remediation Applied:**
1. Hardened `reconciliation_engine.py` to inspect `source_prov in ("MOCK_PROVIDER", "SYNTHETIC_MOCK", "SYNTHETIC_FIXTURE")` and test for substring `"MOCK"` or `"SYNTH"` in `source_provider`.
2. Changed `GAP-VAL-SYNTHETIC-DATA-EXCLUDED` to **`is_blocking: True`**. When an assessment relies on synthetic fixtures in production mode, the synthetic rate is excluded and a blocking gap is retained, forcing overall risk to `INSUFFICIENT_EVIDENCE`.
3. Added automated regression test `test_reconciliation_mock_provider_exclusion` in `backend/tests/test_property_passport_synthesis.py`.

### 2.3 Production MVR Gate Status: `BLOCKED`
While the exclusion gate is now mathematically and architecturally airtight, **no official District Collectorate gazette PDFs or verified government rate schedules have been imported by operators into the database for the pilot mauzas**. Therefore, this gate is classified as **`BLOCKED`** pending operator ingestion of official gazettes.

---

## 3. Statutory Rule Evidence & Legal Correctness

### 3.1 Implemented Statutory Rules Audit

| Statutory Component | Legal Authority & Citation | Implemented Formula / Rate | Software Verified? | Qualified Legal Review? |
| :--- | :--- | :--- | :---: | :---: |
| **Assessment Base** | Indian Stamp Act 1899, Section 47-A (Bihar Amendment) | $\max(\text{Declared Consideration}, \text{Govt Guideline Valuation})$ | **YES** | **NO** (Pending) |
| **Base Stamp Duty (Male / Entity)** | Bihar Stamp (Amendment) Rules | $\text{Assessment Base} \times 6.0\%$ | **YES** | **NO** (Pending) |
| **Female Purchaser Concession** | Bihar Government Notification (Concession for Women) | $\text{Assessment Base} \times 5.6\%$ (0.40% concession) | **YES** | **NO** (Pending) |
| **Joint Purchaser Concession** | Bihar Administrative Practice | $\text{Assessment Base} \times 5.8\%$ (0.20% concession) | **YES** | **NO** (Pending) |
| **Municipal Surcharge** | Bihar Municipal Act & PMC Regulations | Flat 2.0% within Urban Municipal Corporation limits; 0.0% elsewhere | **YES** | **NO** (Pending) |
| **Registration Fee** | Bihar Registration Rules 2008 | Flat 2.0% of Assessment Base | **YES** | **NO** (Pending) |

### 3.2 Separation of Software vs Legal Correctness
- **Software Correctness (PASSED):** `StampDutyEngine` in `stamp_duty_engine.py` deterministically implements the arithmetic formulas with rounding to 2 decimal places, and unit conversions (`unit_converter.py`) are mathematically exact (1 Katha = 3.125 Decimals = 1,361.25 sqft).
- **Legal Correctness (`BLOCKED — PENDING QUALIFIED LEGAL REVIEW`):** No formal legal opinion letter or qualified Bihar revenue advocate memorandum exists in the repository. Statutory exceptions (e.g., gift deeds between blood relatives, partition deeds, agricultural lease rates, industrial corridor exemptions) have not been formally evaluated for the pilot.

---

## 4. CRS and Independent Geospatial Accuracy Validation

### 4.1 Policy Reconciliation: Computational vs Regional CRSs
A critical audit finding was reconciled regarding the Coordinate Reference System (CRS) policy:
- **Active Computational Projections (`EPSG:4326`, `EPSG:32645`):** The mathematical projection engine (`crs.py`) implements ellipsoidal Transverse Mercator formulas specifically for WGS 84 geographic degrees (`EPSG:4326`) and UTM Zone 45N meters (`EPSG:32645`, central meridian 87°E). All automated planar metrology (IoU, Hausdorff distance, centroid shift, area delta) executes exclusively in `EPSG:32645`.
- **Recognized Regional Grids (`EPSG:32644`, `EPSG:32646`, `EPSG:7755`, `EPSG:7760`, `EPSG:7761`, `EPSG:24378`, `EPSG:24379`):** The reconciliation engine acknowledges these codes as valid historical and regional Indian survey reference systems to avoid misclassifying them as completely unknown CRSs.
- **Reconciled Policy:** Accepting an EPSG code in metadata does **not** imply automated planar projection. If an asset is provided in `EPSG:32644` (Western Bihar) or `EPSG:7755` (Survey of India LCC), it must be reprojected into `EPSG:32645` prior to overlay computation; otherwise, `GAP-SPA-UNSUPPORTED-TRANSFORMATION` is raised.

### 4.2 Separation of Fitting Residuals from Independent Check Points (ICPs)
- **Fitting Residuals:** Residuals computed on control points (GCPs) used during parameter estimation measure the degree of mathematical fit ($\hat{\mathbf{P}} = (\mathbf{A}^T\mathbf{A})^{-1}\mathbf{A}^T\mathbf{X}$). With low degrees of freedom ($N=3$ or $N=4$), fitting RMSE can be deceptively small ($< 0.001\text{m}$) even when ground distortion is severe.
- **Independent Check Points (ICPs):** Check points withheld from parameter estimation provide the only genuine empirical measurement of real-world ground displacement. `georeferencing.py` strictly computes `checkpoint_residuals`, `checkpoint_rmse_meters`, and `max_checkpoint_residual_meters` exclusively on ICPs.

### 4.3 Provisional Cadastral Accuracy Threshold
- The $2.50\text{m}$ cadastral tolerance is explicitly classified as **provisional**.
- At revenue survey scale $1:3960$ (16 inches to 1 mile), a 0.5 mm drawing line width on paper represents $1.98\text{m}$ on the ground; at $1:1980$ (32 inches to 1 mile), it represents $0.99\text{m}$.
- While $2.50\text{m}$ aligns with historical map plottability, it has not been calibrated against live differential GNSS (RTK-GNSS) field surveys in the target mauzas.
- Numerical precision (floating-point decimals) is never presented as proof of real-world ground accuracy. Automated boundary overlay outputs remain classified as **review evidence**, never legal boundary adjudications.

---

## 5. Security & Credential Gate Status

| Security Control | Implementation Architecture | Audit Finding | Status |
| :--- | :--- | :--- | :---: |
| **Authentication & RBAC** | JWT Bearer (`HS256`, 1440 min expiry). `require_roles(...)` enforces role isolation. | Verified in unit and staging integration tests. | **`PASS`** |
| **Tenant Data Segregation** | All ORM queries enforce `org_id == current_user.org_id`. Helper `_verify_tenant_access()` blocks cross-tenant access. | Verified via `test_cross_tenant_access_rejection`. | **`PASS`** |
| **File Upload Hardening** | Magic bytes sniffing, 50MB file limit, basename sanitization, Zip Slip path-traversal rejection. | Verified via `test_kmz_path_traversal_zip_slip_rejection`. | **`PASS`** |
| **Outbound SSRF Allowlist** | Domain whitelists restrict valuation, mutation, and judicial HTTP clients. Private IPs blocked. | Verified via provider exception handling tests. | **`PASS`** |
| **Exposed Credential Remediation** | Repository history and scratch scripts sanitized. Local execution uses dynamic credentials. | **BLOCKED:** External revocation/rotation of the historical GitHub token has not been independently confirmed by the operator. | **`BLOCKED`** |

---

## 6. Property Passport & PDF Integrity

1. **Evidence Categorization:** The Land Intelligence Report PDF distinctly renders Observed Facts, Deterministic Inferences, Review Findings, and Explicit Evidence Gaps across dedicated styled blocks.
2. **Epistemic Invariant:** A low or high Risk Diligence Priority Score ($0.00$ to $100.00$) does not predict fraud or establish title safety. It is an internal diligence triage metric ranking the urgency of professional human review.
3. **Absence of Evidence:** Missing judicial records or absence of mutation rejection orders is explicitly surfaced as an evidence limitation, never as proof of unencumbered title or absence of litigation.
4. **QR Verification Token vs Legal Authenticity:**
   - The QR code URL (`/api/v1/reports/verify/{token}`) points to `verify_report_by_token` in `report_service.py`.
   - The endpoint retrieves the stored PDF from MinIO/S3, calculates `hashlib.sha256(content).hexdigest()`, and compares it to `report.sha256_hash`.
   - **Verification Reality:** The QR code confirms the **tamper-evidence and integrity of the PDF artifact** against the server's record. It does **not** certify the legal authenticity of government department records. The report disclaimer clearly states this distinction.
5. **Synthesis Section Rendering:** Validated for both complete assessments and assessments with blocking evidence gaps (`INSUFFICIENT_EVIDENCE`), correctly rendering dimension tables, gap remedy actions, and statutory disclaimers.

---

## 7. Evidence-Based Pilot Gate Matrix

| Evaluation Domain | Verification Criteria | Status | Authoritative Evidence & Justification |
| :--- | :--- | :---: | :--- |
| **1. CI & Migration Integrity** | Host regression suite passing; linear Alembic migrations on PostGIS 16; containerized integration; restart persistence. | **`PASS`** | 315 host tests passed (63.87s), 10 migrations applied cleanly to head `c4d5e6f7a8b9`, 9 staging integration tests passed (3.05s), 18-step smoke test passed (2.40s), persistence verified across restart (Run `40482137233`). |
| **2. Security & Tenant Isolation** | Multi-tenant org isolation; role-based access; upload magic-byte verification; SSRF outbound allowlists. | **`PASS`** | Verified by unit and integration tests. Cross-tenant queries rejected with HTTP 403/404; Zip Slip archives blocked. |
| **3. External Credential Remediation** | Exposed GitHub credential revoked/rotated via authorized provider. | **`BLOCKED`** | Repository code and scripts sanitized, but operator confirmation of external token revocation is outstanding. |
| **4. Official MVR Provenance** | Production calculations use only verified Collectorate gazette notifications; synthetic data blocked. | **`BLOCKED`** | Synthetic data is strictly blocked with `is_blocking: True` (`GAP-VAL-SYNTHETIC-DATA-EXCLUDED`). However, verified Collectorate gazettes for pilot mauzas have not yet been ingested by operators. |
| **5. Statutory Rule Validation** | Section 47-A assessment base; 5.6% female concession; 2.0% PMC municipal surcharge; 2.0% registration fee. | **`BLOCKED`** | Software algorithms and conversions are verified, but formal qualified legal review by a certified revenue advocate has not occurred. |
| **6. CRS & Spatial Accuracy** | Ellipsoidal Transverse Mercator (UTM 45N); Affine OLS solver; independent check-point error separation; spatial caveats. | **`PASS`** | ICP RMSE is strictly separated from fitting RMSE; contradictory CRS bounds rejected; spatial caveats bound to outputs. 2.50m threshold documented as provisional. |
| **7. Judicial & Mutation Evidence** | Source attribution; anti-name-only heuristics ($\le 0.45$); *Suraj Bhan* disclaimer; chronological lifecycle. | **`PASS`** | Uncorroborated party matches capped at 0.45 and routed to review; mutation status explicitly disclaimed (*Suraj Bhan v. Financial Commissioner*). |
| **8. Property Passport Scoring** | Tripartite output separation; origin-based deduplication; blocking gap tier precedence; formula versioning. | **`PASS`** | Evidence completeness, adverse score, and review priority score separated; blocking gaps force `INSUFFICIENT_EVIDENCE`; versioned formulas. |
| **9. PDF Correctness** | Property Passport synthesis rendered; tier badge; priority score; 8-dimension table; evidence gaps; legal notices. | **`PASS`** | Section Synthesis rendered with executive badge, priority index, 8 dimensions, gaps, and statutory limitation statement. Verified in `test_report_generator.py`. |
| **10. Operator Workflow & Audit** | Role-based review endpoints; immutable review action logging; actionable operator SOP checklist. | **`PASS`** | `AssessmentReviewAction` audit trail intact; 4-stage operator acceptance checklist published. |
| **11. Incident Handling & Rollback** | Non-destructive rollback via supersession; volume preservation during restart; disaster recovery runbooks. | **`PASS`** | Recomputation cleanly supersedes previous assessments; staging runbooks document volume-preserving maintenance. |

---

## 8. Corrective Changes Made in this Milestone

1. **`backend/app/services/passport/reconciliation_engine.py`:**
   - Expanded `is_synthetic` schedule detection to check `source_prov in ("MOCK_PROVIDER", "SYNTHETIC_MOCK", "SYNTHETIC_FIXTURE")` and test for `"MOCK"` / `"SYNTH"` substrings in `source_provider`.
   - Upgraded `GAP-VAL-SYNTHETIC-DATA-EXCLUDED` to **`is_blocking: True`**, ensuring synthetic fixtures strictly block production assessments and force the overall tier to `INSUFFICIENT_EVIDENCE`.
2. **`backend/tests/test_property_passport_synthesis.py`:**
   - Added assertion `assert val_gaps[0]["is_blocking"] is True` in `test_reconciliation_synthetic_schedule_exclusion`.
   - Added dedicated test `test_reconciliation_mock_provider_exclusion` verifying that `MockValuationProvider` schedules are excluded from production assessments even when marked `VERIFIED_OFFICIAL`.

---

## 9. Outstanding Operator Prerequisites Before Live Pilot Activation

Before initiating live property assessments with external pilot users in Bihar:

```markdown
[ ] PREREQUISITE 1: OPERATOR TOKEN REVOCATION
    [ ] Log into GitHub -> Settings -> Developer Settings -> Personal Access Tokens.
    [ ] Locate and revoke the personal access token previously exposed in execution transcripts.
    [ ] Record revocation timestamp and operator identity in project security log.

[ ] PREREQUISITE 2: OFFICIAL MVR GAZETTE INGESTION
    [ ] Obtain official District Collectorate Gazette Notifications for pilot mauzas:
        - Danapur Anchal (e.g. Kotwa, Mustafapur)
        - Patna Sadar Anchal
        - Bodh Gaya Anchal
    [ ] Ingest schedules via POST /api/v1/valuation/schedules/import with source gazette reference and operator ID.
    [ ] Verify schedules via POST /api/v1/valuation/schedules/{id}/verify.

[ ] PREREQUISITE 3: QUALIFIED LEGAL REVIEW
    [ ] Commission certified Bihar revenue advocate to review implemented stamp duty and registration fee logic.
    [ ] Confirm local municipal surcharge boundaries (e.g., Patna Municipal Corporation vs Danapur Nagar Parishad).
    [ ] Sign off and archive formal Legal Review Memorandum in backend/docs/.

[ ] PREREQUISITE 4: EMPIRICAL GNSS GROUND CALIBRATION
    [ ] Dispatch LandAmin surveyor with RTK-GNSS equipment to establish true ground control points in pilot mauzas.
    [ ] Verify whether cadastral transformation checkpoint RMSE remains within provisional 2.50m threshold.
```

---

## 10. Final Pilot Gate Verdict

# **`CONDITIONALLY READY — SPECIFIC GATES REMAIN`**

### Summary Justification:
The Bhumi Setu MVP backend intelligence core, deterministic scoring engines, geospatial transformation solvers, and PDF reporting subsystems are fully implemented, defensively hardened, and validated by 100% green continuous integration. However, live pilot deployment with external stakeholders is **conditioned** on the completion of four non-code operational prerequisites: (1) operator confirmation of external token revocation, (2) ingestion of authoritative District Collectorate circle rate gazettes for pilot mauzas, (3) qualified revenue advocate sign-off on statutory transfer fee interpretations, and (4) empirical GNSS field calibration of the provisional 2.50m cadastral threshold.

---
*Report certified by Antigravity Agentic Assistant for Bhumi Setu MVP controlled pilot qualification.*
