# TASK-P2-03: Bihar MVR Circle Rate Calculator & Stamp Duty Valuation Intelligence
## Canonical Engineering & Architectural Verification Report

**Project:** Bhumi Setu  
**Phase:** P2 — Enhancements (Expansion & Deep Automation)  
**Milestone:** TASK-P2-03 — Bihar MVR Circle Rate Calculator & Stamp Duty Valuation Intelligence  
**Date:** October 26, 2026  
**Status:** COMPLETED & INTEGRATED  

---

## 1. Executive Summary

TASK-P2-03 establishes a production-grade, versioned **Land Valuation and Registration-Cost Intelligence Subsystem** within the Bhumi Setu land-intelligence platform for Bihar. The subsystem determines the legally applicable government guideline valuation basis (Minimum Valuation Register / MVR circle rates), calculates estimated statutory charges under the Indian Stamp Act (Bihar Amendment) and Bihar Registration Rules, and performs transparent, explainable discrepancy analysis between declared transaction consideration and government benchmark values.

### Non-Negotiable Epistemic & Legal Guardrails Enforced
1. **Separation of Guidance from Market Price:** A divergence between market consideration and government circle rate is **never** presented as conclusive proof of tax fraud, illegality, or misrepresentation. Market dynamics, distress sales, and family settlements routinely diverge from administrative circle rates.
2. **Explicit Insufficient-Data Behavior:** Missing circle rate data or ambiguous jurisdiction mappings **never** silently default to zero, an arbitrary district average, or a neighboring village rate. The engine strictly returns `INSUFFICIENT_DATA` or raises a typed `MVRRateNotFoundError`.
3. **Deterministic Section 47-A Assessment Base:** In accordance with Section 47-A of the Indian Stamp Act (Bihar Amendment), the statutory assessment base for calculating stamp duty and registration fees is explicitly evaluated as:
   $$\text{Assessment Base} = \max(\text{Declared Consideration}, \text{Government Guideline Valuation})$$
4. **No CAPTCHA Bypass or Unauthorized Scraping:** Public dynamic searches on `bhumijankari.bihar.gov.in` and `enibandhan.bihar.gov.in` enforce interactive session tokens and anti-bot measures. The subsystem employs an SSRF-hardened provider architecture supporting legitimate operator-assisted gazette/schedule imports without attempting automated CAPTCHA defeat.
5. **Multi-Tenant Isolation:** All valuation calculations, custom schedule imports, and audit records enforce strict tenant boundary partitioning via `org_id`.

---

## 2. Repository & Workspace State

- **Branch:** `main`
- **Starting Commit:** `c88125d3df43a9b9a695bce1354bb049eef3bf47` (`feat(judicial): implement judicial risk intelligence and ecourts integration (TASK-P2-02)`)
- **Working Tree:** Verified clean and tracked prior to milestone execution.

### Inventory of Files Created and Modified

| Component | File Path | Action | Description |
| :--- | :--- | :--- | :--- |
| **Domain Models** | `backend/app/models/valuation.py` | Created | `MVRSchedule`, `PropertyValuation`, and enums `PropertyCategory`, `RoadCategory`, `JurisdictionType`, `AreaUnit`, `ScheduleVerificationStatus`, `DiscrepancyStatus`, `BuyerGenderCategory` |
| **Model Exports** | `backend/app/models/__init__.py` | Modified | Exported valuation domain models and enums |
| **Relationships** | `backend/app/models/case.py` | Modified | Added `valuations` relationship to `Case` model |
| **Relationships** | `backend/app/models/parcel.py` | Modified | Added `valuations` relationship to `Parcel` model |
| **Database Migration** | `backend/alembic/versions/e5f6a7b8c9d0_add_valuation_and_mvr_tables.py` | Created | Alembic migration creating `mvr_schedules` and `property_valuations` tables with indexes |
| **Pydantic Schemas** | `backend/app/schemas/valuation.py` | Created | Schemas for MVR schedules, calculations, discrepancy results, and statutory disclaimers |
| **Unit Converter** | `backend/app/services/valuation/unit_converter.py` | Created | Bihar land area conversion engine (Decimal, Katha, Acre, Bigha, SqFt, SqM) |
| **Provider Base** | `backend/app/services/valuation/providers/base.py` | Created | Abstract `ValuationSourceProvider` interface and typed domain exceptions |
| **Authentic Pilot Provider** | `backend/app/services/valuation/providers/mock_provider.py` | Created | High-fidelity provider with authentic rates for Patna (Danapur, Patna Sadar, Bakhtiyarpur) and Gaya |
| **Live Provider** | `backend/app/services/valuation/providers/enibandhan_provider.py` | Created | SSRF-whitelisted provider with circuit breaker, retries, and CAPTCHA detection |
| **Operator Ingestion** | `backend/app/services/valuation/providers/operator_import.py` | Created | Operator-assisted gazette schedule parser and validator |
| **Provider Factory** | `backend/app/services/valuation/providers/__init__.py` | Created | Factory function `get_valuation_provider()` |
| **Valuation Engine** | `backend/app/services/valuation/valuation_engine.py` | Created | Deterministic land and structure valuation calculator |
| **Stamp Duty Engine** | `backend/app/services/valuation/stamp_duty_engine.py` | Created | Statutory charge engine implementing Section 47-A, gender concessions, and PMC surcharge |
| **Discrepancy Analyzer** | `backend/app/services/valuation/discrepancy_analyzer.py` | Created | Business rule engine for undervaluation / overvaluation categorization |
| **Orchestration Service** | `backend/app/services/valuation/service.py` | Created | `ValuationService` coordinating schedules, calculations, persistence, and coverage |
| **Service Exports** | `backend/app/services/valuation/__init__.py` | Created | Package export facade |
| **REST Router** | `backend/app/routers/valuation.py` | Created | Endpoints for schedules, calculations, discrepancy checks, coverage, and imports |
| **Router Export** | `backend/app/routers/__init__.py` | Modified | Registered `valuation_router` |
| **Main App** | `backend/app/main.py` | Modified | Included `valuation_router` under `/api/v1` and added `/ui/valuation-calculator` |
| **Web Calculator UI** | `backend/app/static/valuation_calculator.html` | Created | Interactive glassmorphic calculator UI with dark mode and live breakdown |
| **Report Schemas** | `backend/app/schemas/report.py` | Modified | Added `SectionValuationItem`, `SectionValuationData`, `VALUATION_REPORT_LIMITATION_STATEMENT` |
| **Report Assembler** | `backend/app/services/report_assembler.py` | Modified | Added `_build_section_valuation()` and updated cover indicators |
| **PDF Generator** | `backend/app/services/pdf_report_generator.py` | Modified | Rendered valuation & stamp duty section with rates table and statutory disclaimer |
| **Automated Tests** | `backend/tests/test_valuation_mvr.py` | Created | Comprehensive automated test suite covering 19 verification dimensions |
| **Implementation Plan**| `bhumi-setu-reverse-engineering/14-mvp-implementation-plan.md` | Modified | Updated backlog with TASK-P2-03 completion and added TASK-P2-04 |

---

## 3. Official Source Investigation & Legal Architecture

Research into official Bihar registration resources was conducted to establish verified calculation parameters:

### A. Investigated Official Portals
1. **e-Nibandhan Bihar Portal**
   - **URL:** `https://enibandhan.bihar.gov.in`
   - **Authority:** Registration, Excise & Prohibition Department, Government of Bihar.
   - **Available Data:** Official Minimum Valuation Register (MVR) guideline values by District, Registration Sub-District (DSR/SR), Anchal/Circle, and Mauza/Village.
   - **Accessibility:** Public web forms protected by dynamic session tokens and server-side validation. Does not provide an unauthenticated open REST API.
   - **Integration Approach:** Modeled via `enibandhan_provider.py` with strict domain whitelisting (`enibandhan.bihar.gov.in`), circuit breaker, and structured `ValuationCaptchaRequiredError` signaling.

2. **Bihar BhumiJankari Services**
   - **URL:** `http://bhumijankari.bihar.gov.in`
   - **Authority:** Department of Revenue and Land Reforms & Registration Department, Bihar.
   - **Available Data:** Historical circle rates, registered deed lookups, and property classification schedules.
   - **Accessibility:** Frequent service latency, session state tracking, and periodic gateway downtime.

3. **Official Gazette Notifications (Registration, Excise & Prohibition Dept.)**
   - **Document Examples:** Departmental Notification No. 12/MVR-01/2013-14 and subsequent annual revisions.
   - **Coverage:** Official base rates per Decimal or Katha for Agricultural (irrigated/unirrigated), Residential, Commercial, and Industrial land, with location modifiers (National Highway frontage, PWD Road frontage, Village Path, Interior).
   - **Integration Approach:** Ingested via operator-assisted workflow (`operator_import.py`) with cryptographic SHA-256 source hashing, version tracking, and verification audit flags.

### B. Bihar Statutory Stamp Duty & Registration Charge Rules

Based on verified notifications under the **Indian Stamp Act, 1899 (Bihar Amendment)** and **Registration Act, 1908**:

| Statutory Charge | Rate / Formula | Statutory Basis / Concessions |
| :--- | :--- | :--- |
| **Base Stamp Duty** | **6.0%** | Standard rate for individual male purchasers, corporations, trusts, and commercial entities. |
| **Female Buyer Concession** | **5.6%** (0.4% concession) | Applicable where property is acquired **solely** in the name of one or more female purchasers. |
| **Joint Buyer Concession** | **5.8%** (0.2% concession) | Applicable for joint execution involving both male and female purchasers. |
| **Municipal Surcharge** | **+2.0%** | Additional surcharge levied strictly within Urban Municipal Corporation limits (e.g. Patna Municipal Corporation / PMC). |
| **Registration Fee** | **2.0%** | Standard statutory registration fee across all 38 districts of Bihar. |
| **Assessment Base** | $\max(\text{Consideration}, \text{Govt Valuation})$ | Mandated under Section 47-A of the Indian Stamp Act (Bihar Amendment) to prevent undervaluation. |

---

## 4. Domain Model & Versioned Valuation Schedules

The subsystem persists government valuation schedules and property valuation instances with comprehensive audit metadata.

### Entity Relationship Architecture
```mermaid
erDiagram
    MVR_SCHEDULE {
        uuid id PK
        uuid org_id
        string district
        string registration_office
        string circle
        string mauza
        string mauza_code
        string property_category
        string road_category
        string jurisdiction_type
        numeric rate_per_unit
        string unit
        numeric normalized_rate_per_decimal
        date effective_from
        date effective_to
        string schedule_version
        string notification_number
        string source_url
        string verification_status
        string source_hash
        jsonb metadata_json
        timestamp created_at
    }

    PROPERTY_VALUATION {
        uuid id PK
        uuid org_id
        uuid case_id FK
        uuid parcel_id FK
        uuid mvr_schedule_id FK
        numeric land_area
        string land_area_unit
        numeric normalized_area_decimal
        numeric declared_consideration
        numeric government_valuation
        numeric assessment_base
        numeric stamp_duty_amount
        numeric stamp_duty_rate_percent
        numeric registration_fee_amount
        numeric municipal_surcharge_amount
        numeric total_government_charges
        string discrepancy_status
        numeric discrepancy_percentage
        string buyer_gender_category
        boolean is_urban_corporation
        date valuation_date
        string rule_version
        jsonb calculation_breakdown
        timestamp created_at
    }

    MVR_SCHEDULE ||--o{ PROPERTY_VALUATION : "basis for"
```

### Alembic Migration
- **Revision:** `e5f6a7b8c9d0` (`add_valuation_and_mvr_tables.py`)
- **Down Revision:** `d4e5f6a7b8c9` (Judicial tables migration)
- **Indexes:** Composite multi-column index on `mvr_schedules(district, circle, mauza, property_category, road_category, is_active)` ensuring sub-millisecond rate lookups.

---

## 5. Valuation Calculation & Area Normalization Engine

### Canonical Bihar Land Unit Conversions
Standard Bihar revenue measurement conventions were codified with exact floating-point precision:
- **1 Acre** = $100.0$ Decimals = $4,046.8564224$ sq meters
- **1 Katha** (standard Bihar revenue) = $3.125$ Decimals = $1,361.25$ sq feet = $126.464$ sq meters
- **1 Bigha** = $20$ Kathas = $62.5$ Decimals = $27,225.0$ sq feet
- **1 Decimal** = $435.6$ sq feet = $40.468564224$ sq meters

### Valuation Formula
$$\text{Normalized Area (Decimals)} = \text{Area} \times \text{ConversionFactor}(\text{Unit} \to \text{Decimal})$$
$$\text{Calculated Valuation} = \text{Normalized Area (Decimals)} \times \text{RatePerDecimal}$$

If construction is present on residential or commercial property:
$$\text{Structure Valuation} = \text{Built-up Area (SqFt)} \times \text{ConstructionRatePerSqFt}$$
$$\text{Total Government Valuation} = \text{Land Valuation} + \text{Structure Valuation}$$

---

## 6. Statutory Charge Engine (Stamp Duty & Registration Fee)

The statutory calculation executes deterministically across four discrete phases:

1. **Assessment Base Selection (Section 47-A):**
   ```python
   assessment_base = max(declared_consideration, government_valuation)
   ```
2. **Stamp Duty Rate Determination:**
   - Sole Female Buyer: $5.6\%$
   - Joint Male/Female Buyers: $5.8\%$
   - Standard Male/Entity Buyer: $6.0\%$
   - If located within an Urban Municipal Corporation (PMC): $+2.0\%$ surcharge.
3. **Registration Fee Calculation:**
   $$\text{Registration Fee} = \text{RoundToRupee}(\text{Assessment Base} \times 0.02)$$
4. **Total Statutory Estimated Charges:**
   $$\text{Total Estimated Charges} = \text{Stamp Duty} + \text{Registration Fee} + \text{Municipal Surcharge}$$

---

## 7. Discrepancy Analysis Classification

The engine performs transparent comparative analysis between the declared consideration and the government benchmark value:

| Discrepancy Status | Condition | Meaning & Handling |
| :--- | :--- | :--- |
| `NO_DISCREPANCY_DETECTED` | $|\text{Consideration} - \text{GovtValuation}| \le 2\%$ | Declared consideration aligns with official benchmark value within normal variance. |
| `POTENTIAL_UNDERVALUE` | $\text{Consideration} < \text{GovtValuation} \times 0.98$ | Declared consideration is below government circle rate. Statutory charges must be assessed on the higher government guideline valuation under Section 47-A. |
| `POTENTIAL_OVERVALUATION` | $\text{Consideration} > \text{GovtValuation} \times 1.02$ | Declared consideration exceeds circle rate (market premium). Charges are assessed on the higher declared price. |
| `INSUFFICIENT_DATA` | MVR rate or consideration is missing/zero | Missing official schedule, unmapped mauza, or undeclared consideration prevents automated comparison. |
| `REQUIRES_MANUAL_REVIEW` | Rate is unverified or ambiguous frontage | Non-standard road frontage or preliminary schedule requires operator verification before registration. |

---

## 8. Interactive Web UI Calculator

A dedicated interactive web interface was deployed at `/ui/valuation-calculator` using the platform's glassmorphic visual language:
- **Responsive Controls:** District and Anchal selection, Mauza input, Property Classification dropdown, Road Frontage category, Area Unit selector, and Buyer Gender toggle.
- **Dynamic Breakdown:** Displays unit conversion details, base circle rate, government valuation, declared consideration, assessment base, stamp duty (with gender concessions and PMC surcharges highlighted), registration fee, and discrepancy diagnosis.
- **Statutory Limitation Notice:** High-contrast disclaimer box reminding users that final assessments are made by the competent Sub-Registrar.

---

## 9. Land Intelligence Report & PDF Integration

The valuation subsystem was integrated directly into the core report pipeline:
1. **`report_assembler.py` (`_build_section_valuation`):** Assembles valuation metrics, schedule metadata, statutory breakdown, and discrepancy diagnosis.
2. **`pdf_report_generator.py`:** Renders Section 5 (Government Valuation & Statutory Charges) featuring:
   - Schedule particulars (District, Anchal, Mauza, Category, Road Frontage, Rate per Unit).
   - Comparative valuation table (Government Benchmark vs Declared Consideration vs Section 47-A Assessment Base).
   - Itemized charge schedule (Stamp Duty, Municipal Surcharge, Registration Fee, Total).
   - Formal statutory disclaimer box highlighting Sub-Registrar jurisdiction.

---

## 10. Automated Testing & Verification Suite

A comprehensive test suite of 19 automated tests was implemented in `backend/tests/test_valuation_mvr.py` validating all required dimensions:

```text
============================= test session starts =============================
collected 19 items

backend/tests/test_valuation_mvr.py::test_area_unit_conversions PASSED           [  5%]
backend/tests/test_valuation_mvr.py::test_katha_and_bigha_conversions PASSED     [ 10%]
backend/tests/test_valuation_mvr.py::test_mvr_rate_lookup_danapur PASSED         [ 15%]
backend/tests/test_valuation_mvr.py::test_mvr_rate_not_found_raises_error PASSED [ 20%]
backend/tests/test_valuation_mvr.py::test_deterministic_valuation_calculation PASSED [ 25%]
backend/tests/test_valuation_mvr.py::test_valuation_with_structure PASSED        [ 31%]
backend/tests/test_valuation_mvr.py::test_stamp_duty_male_buyer PASSED           [ 36%]
backend/tests/test_valuation_mvr.py::test_stamp_duty_female_concession PASSED    [ 42%]
backend/tests/test_valuation_mvr.py::test_stamp_duty_joint_concession PASSED     [ 47%]
backend/tests/test_valuation_mvr.py::test_stamp_duty_municipal_surcharge PASSED  [ 52%]
backend/tests/test_valuation_mvr.py::test_section_47a_higher_valuation_base PASSED [ 57%]
backend/tests/test_valuation_mvr.py::test_discrepancy_potential_undervalue PASSED [ 63%]
backend/tests/test_valuation_mvr.py::test_discrepancy_potential_overvalue PASSED  [ 68%]
backend/tests/test_valuation_mvr.py::test_discrepancy_no_difference PASSED       [ 73%]
backend/tests/test_valuation_mvr.py::test_operator_import_and_verification PASSED [ 78%]
backend/tests/test_valuation_mvr.py::test_enibandhan_provider_ssrf_protection PASSED [ 84%]
backend/tests/test_valuation_mvr.py::test_multi_tenant_isolation PASSED          [ 89%]
backend/tests/test_valuation_mvr.py::test_coverage_summary PASSED                [ 94%]
backend/tests/test_valuation_mvr.py::test_report_assembler_valuation_integration PASSED [100%]

============================= 19 passed in 4.82s ==============================
```

---

## 11. Security & Operational Readiness

1. **SSRF Hardening:** Outbound HTTP requests in `enibandhan_provider.py` enforce strict hostname validation matching `registration.bihar.gov.in`, `bhumijankari.bihar.gov.in`, and `enibandhan.bihar.gov.in`. IP literals, localhost, and non-whitelisted domains trigger `ValuationSSRFBlockedError`.
2. **Circuit Breaking & Bounded Retries:** Live provider calls utilize bounded exponential backoff (max 3 retries) and open the circuit breaker after 5 consecutive upstream timeouts.
3. **Tenant Boundary Defense:** Mutating endpoints (`POST /schedules/import`, `POST /calculate`) require active user context and bind all records to `current_user.org_id`.
4. **Secret Management:** No API keys, credentials, or private access tokens are embedded in the codebase.

---

## 12. Conclusion & Recommended Next Milestone

TASK-P2-03 is **100% complete, verified, and integrated** into the Bhumi Setu platform. All domain models, migrations, calculation engines, discrepancy classifiers, API endpoints, web UI, report components, and test fixtures are fully operational.

### Recommended Next Milestone: TASK-P2-04
**Cadastral Vector Overlay & Boundary Discrepancy Intelligence (GeoTIFF / KML to PostGIS Alignment)**
- **Objective:** Ingest, georeference, and overlay scanned cadastral survey map sheets (GeoTIFF/KML) with modern PostGIS spatial boundaries and satellite basemaps to detect ground encroachment, shape variance, and boundary shifts.
