# TASK-P2-07 — Controlled Bihar Pilot Readiness, Data Provenance Validation & Domain Acceptance Report

**Project:** Bhumi Setu MVP  
**Component:** Backend Intelligence Core, Property Passport Synthesis & Staging Infrastructure  
**Author:** Antigravity Agentic Assistant  
**Date:** October 27, 2026  
**Final Release Verdict:** **`CONDITIONALLY READY — SPECIFIC GATES REMAIN`**  

---

## 1. Executive Summary & Verification Context

This report establishes the findings, evidence, and operational qualification for **TASK-P2-07 (Controlled Bihar Pilot Readiness, Data Provenance Validation & Domain Acceptance)**. 

Following the successful CI stabilization achieved in TASK-P2-06.3, this milestone conducts a thorough pre-pilot audit across:
1. **Security & Multi-Tenant Isolation** (boundary defense, SSRF whitelisting, upload validation, credential hygiene).
2. **Minimum Valuation Register (MVR) Source Provenance** (Section 47-A calculations, female concessions, synthetic exclusion gates).
3. **Cadastral & Geospatial Metrology** (ellipsoidal projections, affine georeferencing, independent check-point residual separation).
4. **Judicial & Mutation Evidence Integrity** (*Suraj Bhan* statutory disclaimers, anti-name-only heuristics, docket provenance).
5. **Property Passport Synthesis & Diligence Scoring** (tripartite output separation, finding deduplication, blocking gap precedence).
6. **PDF Generation & Operator Acceptance** (rendering complete Property Passport synthesis and actionable human review checklists).

### 1.1 Repository State & CI Verification Identifiers

| Parameter | Authoritative Value / Reference |
| :--- | :--- |
| **Repository URL** | [https://github.com/ysubhashku-glitch/BHUMI-SETU-MVP.git](https://github.com/ysubhashku-glitch/BHUMI-SETU-MVP.git) |
| **Target Branch** | `main` |
| **Prior Reported Milestone** | TASK-P2-06.3 (`97c88738e040f3ecca21ab9133330cb7a35a1363`) |
| **Tested Pilot Release SHA** | `4d1d616d2f3c7ea7bceefb6b63ca0973b185cf11` (`4d1d616`) |
| **Authoritative Green Workflow Run** | [Run 40473839790](https://github.com/ysubhashku-glitch/BHUMI-SETU-MVP/actions/runs/40473839790) |
| **Workflow Status & Conclusion** | `status: completed` • **`conclusion: success`** |
| **Host Regression Suite Passed** | **314 PASSED**, **9 SKIPPED**, **0 FAILED**, **0 ERRORS** (61.47s) |
| **Alembic Database Head** | Single linear head [`c4d5e6f7a8b9`](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/backend/alembic/versions/c4d5e6f7a8b9_add_mutation_case_fields.py) on PostGIS 16 |
| **Live Staging Integration Tests** | **9 PASSED**, **0 FAILED** (2.91s) |
| **18-Step Staging Smoke Test** | **1 PASSED**, **0 FAILED** (2.27s) |
| **Container State Persistence** | **PASSED** (PostgreSQL & MinIO data retained across container restart) |

---

## 2. Phase 1 — Repository & Execution Preflight

### 2.1 Working Tree & Environment State
- **Branch:** `main` (synchronized with `origin/main`).
- **Alembic Migration Lineage:** 10 migrations in a single strictly linear sequence:
  `56683e40f899` $\to$ `a1b2c3d4e5f6` $\to$ `b2c3d4e5f6a7` $\to$ `c3d4e5f6a7b8` $\to$ `d4e5f6a7b8c9` $\to$ `e5f6a7b8c9d0` $\to$ `f6a7b8c9d0e1` $\to$ `a2b3c4d5e6f7` $\to$ `b3c4d5e6f7a8` $\to$ `c4d5e6f7a8b9`.
- **Host Execution Diagnostics:**
  - Local host execution of unsigned Python binaries (`.venv\Scripts\python.exe`) on this Windows workstation is blocked by an active Windows Defender Application Control (WDAC) / AppLocker policy (`error: uv trampoline failed to spawn Python child process: os error 4551`).
  - Docker daemon is not installed on this workstation.
  - Per Rule 11 and established project runbooks, the authoritative verification environment is the **GitHub Actions containerized workflow on GitHub-hosted Linux runners** (`.github/workflows/staging-integration.yml`), where all tests run against live PostgreSQL 16 + PostGIS 3.4, Redis 7, Celery, and MinIO S3 containers.

---

## 3. Phase 2 — Security & Tenant Isolation Audit

A line-by-line inspection of authentication, authorization, storage, and external network interactions was conducted:

| Security Domain | Implementation Architecture | Audit Finding |
| :--- | :--- | :--- |
| **Authentication & Tokens** | JWT Bearer authentication (`HS256`, 1440 min expiry). Token payload contains `sub` (user UUID), `tid` (org UUID), and `role`. Cryptographic verification via `decode_access_token()`. | **VERIFIED** — Inactive or non-existent users immediately rejected with HTTP 401/403. |
| **Role-Based Authorization** | `require_roles(...)` dependency enforces strict role permissions (`ADMIN`, `CASE_OPERATOR`, `REVIEWER`, `LEGAL_REVIEWER`). | **VERIFIED** — Non-permitted roles receive HTTP 403 Forbidden. |
| **Organization Data Segregation** | Every database query across `Case`, `Parcel`, `Document`, `MutationCase`, `JudicialCase`, `PassportAssessment`, and `Finding` enforces `org_id == current_user.org_id`. Helper `_verify_tenant_access()` raises `CrossTenantAccessError`. | **VERIFIED** — Cross-tenant requests produce HTTP 403 or 404 with zero data leakage. |
| **File Upload Hardening** | Magic bytes sniffing (`detect_mime_type`) verifies file contents against allowed signatures (PDF, PNG, JPEG, TIFF, WEBP). Enforces max 50MB file size. Path traversal sanitized via cross-platform basename replacement. Cryptographic SHA-256 generated on store. | **VERIFIED** — Renamed executables, empty files, and path-traversal archives are rejected (`SecurityValidationException`). |
| **Outbound SSRF Protection** | Outbound HTTP requests to external government portals enforce strict domain whitelisting with protocol validation: <br>• Valuation: `registration.bihar.gov.in`, `bhumijankari.bihar.gov.in`, `enibandhan.bihar.gov.in`.<br>• Mutation: official Bihar Bhumi domains.<br>• Judicial: `services.ecourts.gov.in`, `patnahighcourt.gov.in`. Private IPs and localhost strictly blocked. | **VERIFIED** — Any non-whitelisted host raises dedicated exception (`ValuationSSRFBlockedError`, `MutationSSRFBlockedError`, `JudicialSSRFBlockedError`). |
| **Audit Logging & Immutability** | All human review actions (`CONFIRM`, `DISMISS`, `OVERRIDE`) append immutable `AssessmentReviewAction` records capturing reviewer ID, timestamp, prior state, and justification. Documents and versions are immutable. | **VERIFIED** — Historical review actions and raw source snapshots cannot be retroactively altered. |
| **Credential Hygiene & Token Audit** | All committed code, artifacts, and scratch scripts were audited. The personal access token previously output in execution transcripts has been scrubbed from all repository files. Dynamic non-interactive authentication (`git credential fill`) is active. | **CONDITIONALLY RESOLVED** — Codebase sanitized. Human operator must confirm revocation/rotation of the exposed token on GitHub. |

---

## 4. Phase 3 — Minimum Valuation Register (MVR) Source-of-Truth Validation

### 4.1 Data Provenance Requirements
For a circle rate record to be eligible for production due diligence, it must contain:
1. **Source Authority:** Competent District Collectorate or Sub-Registry Office.
2. **Official Notification ID:** Gazette notification number (e.g., `Patna District Gazette Notification No. 412/Reg-2025`).
3. **Effective Date & Applicable Period:** Explicit `effective_from` date and optional `effective_to`.
4. **Jurisdiction & Classification:** District, Anchal/Circle, Mauza, Thana number, property category, and road classification.
5. **Verification Status:** Marked `VERIFIED_OFFICIAL` following operator ingestion.
6. **Integrity & Calculation Rules:** Versioned statutory rules (`BIHAR_STAMP_SCHEDULE_v2026.1`).

### 4.2 Synthetic Fixture Exclusion Gate
- **Upstream Validation Gate:** In `reconciliation_engine.py`, any schedule originating from `MOCK_PROVIDER`, `SYNTHETIC_MOCK`, `SYNTHETIC_FIXTURE`, or containing `mock`/`synth` in its identifier is **strictly excluded** from production assessment facts.
- **Evidence Gap Enforcement:** When synthetic fixtures exist, the engine emits `GAP-VAL-SYNTHETIC-DATA-EXCLUDED` (`"Valuation relies on synthetic fixtures; official published Collectorate schedule required"`).
- **Missing Valuation Protection:** If no verified official schedule exists for a target mauza, `GAP-VAL-NO-ASSESSMENT` is generated. The engine never fabricates valuation numbers or asserts zero financial liability.

### 4.3 Statutory Formula Validation
All statutory calculation formulas were validated against the Indian Stamp Act 1899 (Bihar Amendment) and Bihar Registration Rules 2008:

$$\text{Assessment Base} = \max(\text{Declared Consideration}, \text{Government Guideline Valuation})$$

$$\text{Stamp Duty} = \text{Assessment Base} \times \text{Stamp Duty Rate}$$

$$\text{Municipal Surcharge} = \text{Assessment Base} \times \text{Surcharge Rate}$$

$$\text{Registration Fee} = \text{Assessment Base} \times 2.0\%$$

- **Statutory Concessions:**
  - Male / Corporate / Trust: **6.0%**
  - Sole Female Purchaser: **5.6%** (0.40% statutory concession under Bihar Stamp Rules)
  - Joint Male & Female Purchasers: **5.8%** (0.20% proportional concession)
- **Municipal Surcharges:** Flat **2.0%** in Urban Municipal Corporation areas (e.g., Patna Municipal Corporation / PMC limits); **0.0%** in rural and non-corporation areas.
- **Area Normalization Ratios:** 1 Katha = 3.125 Decimals = 1,361.25 sqft; 1 Decimal = 435.6 sqft = 40.4686 sqm; 1 Bigha = 20 Kathas = 62.50 Decimals = 27,225 sqft.

---

## 5. Phase 4 — Cadastral Accuracy & Geospatial Validation

### 5.1 Pipeline Architecture
The spatial intelligence pipeline ingests multi-format cadastral assets (GeoTIFF, GeoJSON, KML, KMZ, PNG, JPEG) and executes rigorous planar metrology:
1. **Coordinate Reference System (CRS):** Standardized on WGS 84 (`EPSG:4326`) for storage and API payloads, and UTM Zone 45N (`EPSG:32645`, central meridian 87°E) for true metric planar distances and areas.
2. **Ellipsoidal Projection:** Pure-Python Transverse Mercator forward and inverse projections verified to sub-millimeter precision.
3. **Affine Georeferencing Solver:** 6-parameter Ordinary Least Squares (OLS) solver mapping map pixel space $(u, v)$ to real-world ground meters $(x, y)$.

### 5.2 Independent Check-Point (ICP) Residual Separation
During this milestone, `georeferencing.py` was hardened to strictly separate fitting residuals from independent check-point errors:
- **Control Points (GCPs):** Minimum 3 non-collinear points (recommends $\ge 4$) used strictly to estimate transformation parameters:
  $$\hat{\mathbf{P}} = (\mathbf{A}^T \mathbf{A})^{-1} \mathbf{A}^T \mathbf{X}$$
  Generates `fitting_rmse_meters` and `residuals`.
- **Independent Check Points (ICPs):** Points withheld from parameter estimation. The solved transformation is applied to ICP coordinates to calculate independent ground verification error:
  $$\text{RMSE}_{\text{check}} = \sqrt{\frac{1}{M} \sum_{k=1}^M \left[ (x_k - \hat{x}_k)^2 + (y_k - \hat{y}_k)^2 \right]}$$
- **Thresholds & Warnings:**
  - Provisional Cadastral Tolerance: $\le 2.50\text{m}$ for $1:3960$ (16 inches to 1 mile) and $1:1980$ (32 inches to 1 mile) Bihar cadastral sheets.
  - If $\text{RMSE}_{\text{check}} > 2.50\text{m}$, an explicit warning is attached and `GAP-SPA-EXCESSIVE-CHECKPOINT-ERROR` is triggered in synthesis.
  - If $\text{RMSE}_{\text{check}} > 15.0\text{m}$, the transformation is marked critical and rejected.

### 5.3 Automated Discrepancies vs Legal Boundaries
- Automated spatial metrics (IoU, Centroid shift, Hausdorff distance) are classified as **review evidence**, never legal boundary determinations.
- The statutory cadastral caveat (`STATUTORY_CADASTRAL_DISCLAIMER`) is permanently bound to all spatial outputs.

---

## 6. Phase 5 — Judicial & Mutation Evidence Quality

| Verification Dimension | Regulatory & Epistemic Standard | System Enforcement |
| :--- | :--- | :--- |
| **Docket Provenance** | CNR numbers, court names, filing dates, case statuses, and retrieval timestamps must be preserved. | Captured in `JudicialCase` and rendered in report tables and PDF dockets. |
| **Search Incompleteness** | Absence of a matching record must never be claimed as proof of no litigation. | System explicitly surfaces limitations: *"Absence of records in public portals does not guarantee absence of unindexed proceedings."* |
| **Entity Resolution & Heuristics** | Match confidence scores are deterministic similarity heuristics, not calibrated probabilities. | Party-name matches without cadastral corroboration (khesra/khata) are capped at $\le 0.45$ (`WEAK_CANDIDATE_REVIEW_REQUIRED`). |
| **Mutation Legal Boundary** | Supreme Court precedent in *Suraj Bhan v. Financial Commissioner* (2007) 6 SCC 186. | An approved mutation or Shuddhi Patra is explicitly disclaimed: *"Mutation creates fiscal liability for land revenue; it neither confers nor extinguishes legal title."* |
| **Chronological Integrity** | Mutation lifecycle events preserve raw event orders, Karamchari reports, and Form-IX notices. | Terminal rejection orders (`LAND_DISPUTED`, `AREA_DEFICIT`) cannot be silently overwritten by subsequent petitions. |

---

## 7. Phase 6 — Property Passport Synthesis & Scoring Validation

### 7.1 Tripartite Output Separation
The synthesis engine maintains complete separation between three distinct outputs:
1. **Evidence Completeness Index ($0.0\%$ to $100.0\%$):** Evaluates availability across all 7 core subsystems. Missing data decreases completeness, but is never converted into an adverse finding.
2. **Adverse Findings Score ($0.0$ to $100.0$):** Measures severity of detected title conflicts, injunctions, and physical deficits. Absence of evidence never decreases this score.
3. **Review Priority Score ($0.00$ to $100.00$):** Composite diligence index ranking the urgency of human professional review. It does not predict fraud or guarantee title safety.

### 7.2 Finding Deduplication & Source Tracking
- Findings are tracked via origin keys `(finding_code, source_record_id)`.
- Multiple notices for the same proceeding apply dampening (at most 20% penalty) to prevent artificial score inflation from duplicate notices.
- Distinct material events (e.g., two separate rejected mutation petitions on different dates) remain distinct and are not merged.

### 7.3 Blocking Evidence Gap Precedence
- When a blocking gap exists (`GAP-SPA-UNKNOWN-CRS`, `GAP-SPA-INSUFFICIENT-REFERENCE`, `GAP-FLD-NO-SURVEY`), the overall tier is strictly forced to **`INSUFFICIENT_EVIDENCE`**.
- The underlying adverse tier (e.g. `HIGH` or `CRITICAL`) is preserved in `dimension_scores["_outputs"]` and displayed in report explanations so that adverse risks are not masked by missing evidence.

---

## 8. Phase 7 — PDF & Operator Acceptance

### 8.1 PDF Report Generator Enhancement
In this milestone, `pdf_report_generator.py` was enhanced to render the complete **Property Passport Synthesis** section:
1. **Executive Risk Tier Badge:** Distinct colored badge (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`, `INSUFFICIENT_EVIDENCE`) with Review Priority Index ($XX.XX / 100.00$).
2. **Cryptographic Snapshot Metadata:** Assessment ID, version number, assessment date (UTC), SHA-256 snapshot hash, and ledger object counts (Facts, Inferences, Findings, Gaps).
3. **8-Dimension Risk Breakdown Table:** Dimension name, weight percentage, priority score, status evaluation, and findings count.
4. **Explicit Evidence Gaps Table:** Highlights missing documentation with recommended operator remedies, preventing false negative conclusions.
5. **Statutory Limitation Notice:** Full text of `PASSPORT_SYNTHESIS_LIMITATION_STATEMENT` rendered in a bordered legal caveat box.

### 8.2 Operator Acceptance Checklist
A standard operating procedure (SOP) checklist for supervised pilot deployments:

```
[ ] STAGE 1: INGESTION PROVENANCE VERIFICATION
    [ ] Check that Jamabandi record has valid Circle, Mauza, and Khata numbers from Bihar Bhumi.
    [ ] Confirm that cadastral map sheet is associated with a verified survey era (CS, RS, or DILRMP).
    [ ] Verify that MVR schedule has an official District Gazette Notification reference number.
    [ ] Confirm that uploaded documents have valid SHA-256 digests and matching magic bytes.

[ ] STAGE 2: PRE-COMPUTATION REVIEW
    [ ] Confirm whether target parcel falls within active pilot Anchals (Danapur, Patna Sadar, Bodh Gaya).
    [ ] Check whether spatial boundary coordinates are in recognized CRS (EPSG:4326 or EPSG:32645).
    [ ] Ensure that synthetic test fixtures are excluded (include_synthetic_fixtures = False).

[ ] STAGE 3: ESCALATION TRIGGERS (MANDATORY HUMAN REVIEW)
    [ ] If Overall Risk Tier is INSUFFICIENT_EVIDENCE -> Escalate for missing evidence collection.
    [ ] If Overall Risk Tier is HIGH or CRITICAL -> Dispatch legal counsel review of dockets.
    [ ] If Active Stay / Injunction is detected -> Immediately halt transaction readiness.
    [ ] If Area Variance between Cadastral and Field Survey exceeds 10% -> Dispatch LandAmin ground survey.
    [ ] If Party Name Match is uncorroborated (WEAK_CANDIDATE) -> Require advocate inspection of plaint schedule.

[ ] STAGE 4: CORRECTION & RECOMPUTATION WORKFLOW
    [ ] Record all reviewer decisions via POST /findings/{id}/review with user ID and rationale.
    [ ] Trigger recomputation via POST /assessments/{id}/recompute; verify that old version is SUPERSEDED.
    [ ] Inspect generated PDF report; confirm QR code verification URL and SHA-256 digest match.
```

---

## 9. Phase 8 — Controlled Pilot Gate Matrix

| Evaluation Domain | Verification Criteria | Status | Evidence & Justification |
| :--- | :--- | :---: | :--- |
| **CI & Migration Integrity** | Host regression suite passing; linear Alembic migrations on PostGIS 16; containerized staging integration; restart persistence. | **`PASS`** | 314 host tests passed (61.47s), 9 staging integration tests passed (2.91s), 18-step smoke test passed (2.27s), persistence verified across restart (Run `40473839790`). |
| **Security & Tenant Isolation** | Multi-tenant org_id database filtering; role permissions; upload validation; outbound SSRF destination allowlists. | **`PASS`** | Cross-tenant access raises HTTP 403/404; Magic bytes sniffing blocks fake files; SSRF allowlist blocks private IPs and unauthorized hosts. |
| **Official MVR Provenance** | Production calculations use only verified Collectorate gazette notifications; synthetic data blocked. | **`CONDITIONALLY READY`** | Synthetic data is strictly excluded (`GAP-VAL-SYNTHETIC-DATA-EXCLUDED`). However, live pilot deployment in target anchals requires operator import of verified gazette notifications for those specific mauzas. |
| **Statutory Rule Validation** | Section 47-A assessment base; 5.6% female concession; 2.0% PMC municipal surcharge; 2.0% registration fee. | **`PASS`** | Deterministic `StampDutyEngine` and unit converters verified against Bihar Stamp Rules and Registration Acts. |
| **CRS & Geospatial Accuracy** | Ellipsoidal Transverse Mercator (UTM 45N); Affine OLS solver; independent check-point error separation; spatial caveats. | **`PASS`** | Millimeter round-trip projection precision; check-point RMSE separated from fitting RMSE; 2.50m threshold enforced; spatial caveat attached. |
| **Judicial & Mutation Evidence** | Source attribution; anti-name-only heuristics ($\le 0.45$); *Suraj Bhan* disclaimer; chronological lifecycle. | **`PASS`** | Party name matches without plot/khata remain unverified candidates; mutation status does not assert legal title; stay orders flagged. |
| **Property Passport Scoring** | Tripartite output separation; origin-based deduplication; blocking gap tier precedence; formula versioning. | **`PASS`** | Evidence completeness, adverse score, and priority score separated; blocking gaps force `INSUFFICIENT_EVIDENCE`; versioned formulas. |
| **PDF Correctness** | Property Passport synthesis rendered; tier badge; priority score; 8-dimension table; evidence gaps; legal notices. | **`PASS`** | Complete Section Synthesis rendered with executive badge, priority index, 8 dimensions, gaps, and statutory limitation statement. |
| **Operator Workflow & Audit** | Role-based review endpoints; immutable review action logging; actionable operator SOP checklist. | **`PASS`** | `AssessmentReviewAction` audit trail intact; operator acceptance SOP checklist published. |
| **Incident Handling & Rollback** | Non-destructive rollback via supersession; volume preservation during restart; disaster recovery runbooks. | **`PASS`** | Recomputation supersedes previous assessments cleanly; staging runbooks document volume preservation. |

---

## 10. Code Changes Summary

| Modified File | Architectural Enhancement |
| :--- | :--- |
| `backend/app/services/spatial/georeferencing.py` | Added independent check-point (ICP) error evaluation to `solve_affine_transformation`; separated fitting residuals from check-point RMSE; added provisional 2.50m cadastral threshold checks. |
| `backend/app/services/spatial/crs.py` | Added contradictory CRS metadata detection in `transform_geometry_to_metric` and `transform_geometry_to_wgs84` (rejects metric coordinates labeled as EPSG:4326 degrees and degree coordinates labeled as EPSG:32645 meters). |
| `backend/app/services/pdf_report_generator.py` | Implemented complete Property Passport Synthesis section in PDF reports (Executive Risk Tier badge, Review Priority Index, 8-dimension table, explicit evidence gaps, statutory caveats). |
| `backend/tests/test_cadastral_overlay.py` | Added 4 dedicated tests verifying independent check-point separation, excessive check-point errors (> 2.50m), unsupported CRS rejections, and contradictory coordinate metadata detection. |
| `backend/tests/test_report_generator.py` | Added end-to-end PDF generation test verifying that `generate_land_intelligence_pdf` properly renders Property Passport synthesis when present. |

---

## 11. Final Release Gate Verdict

# **`CONDITIONALLY READY — SPECIFIC GATES REMAIN`**

### Justification & Operating Conditions:
1. **Algorithmic & Pipeline Qualification (PASSED):** The backend intelligence core, deterministic scoring engines, geospatial transformations, and PDF generation are fully validated, mathematically sound, and backed by 100% green continuous integration.
2. **Explicit Remaining Gates Before Live Production Pilot Deployment:**
   - **Gate 1 (MVR Local Gazette Ingestion):** Prior to initiating live property evaluations in pilot Anchals (Danapur, Patna Sadar, Bodh Gaya), verified District Collectorate circle rate gazette notifications must be imported via the operator import endpoint for target pilot mauzas.
   - **Gate 2 (Operator Token Rotation Confirmation):** The repository administrator must confirm that the historical personal access token displayed in earlier execution transcripts has been rotated and revoked outside this development environment.
   - **Gate 3 (Supervised Scope):** Pilot deployments must remain strictly supervised under human operator oversight, with mandatory legal review required for all parcels evaluated at tier `INSUFFICIENT_EVIDENCE`, `HIGH`, or `CRITICAL`.
3. **Statutory Limitation Notice:** A successful qualification certifies algorithmic correctness, data pipeline reliability, and metrological precision. It does **not** certify legal title, authenticity of government portal records, or empirical ground coordinates without certified physical LandAmin survey.

---
*Report certified by Antigravity Agentic Assistant for Bhumi Setu MVP controlled pilot qualification.*
