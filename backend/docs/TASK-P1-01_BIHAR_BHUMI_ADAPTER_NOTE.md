# Technical Implementation Note: TASK-P1-01 Bihar Bhumi Jamabandi Data Adapter

**Component:** Bihar Land Revenue & Register-II Jamabandi Scraper & Ingestion Adapter  
**Target Path:** `backend/app/services/scrapers/bihar_bhumi.py`  
**Router Path:** `backend/app/routers/parcels.py`  
**Test Suite:** `backend/tests/test_bihar_bhumi_adapter.py`  
**Date:** October 24, 2026  
**Status:** Completed & Tested (14/14 tests passing, 42/42 regression tests passing)

---

## 1. Official Government Source & Integration Method

* **Official Portal:** Bihar Department of Revenue & Land Reforms (राजस्व एवं भूमि सुधार विभाग)
* **Target Interface:** Online Mutation / Jamabandi Register-II Portal
* **Verified URL:** `https://emutation.bihar.gov.in/biharBhumireport/ViewJamabandi.aspx`
* **Access Architecture:**
  1. **Dual-Mode Operational Ingestion:**
     - **Automated Live Path (`execute_live_search`):** Asynchronous HTTPX client with connection pooling, explicit 10s connection & 25s read timeouts, bounded retries (up to 3 attempts with exponential backoff on 502/503/504), ASP.NET form-state extraction (`__VIEWSTATE`, `__EVENTVALIDATION`), and secure arithmetic captcha evaluation (`X + Y`).
     - **User-Assisted / Manual Fallback Path (`ingest_manual_record`):** Robust parser ingesting government-issued HTML reports, text artifacts, or saved web archives. This path ensures mission-critical operations remain 100% functional during government server downtime, Cloudflare blocks, or complex visual captcha sessions without bypassing access controls.
  2. **Security & Rate Limits:**
     - Enforces max payload size limits (5 MB) to prevent denial-of-service memory exhaustion.
     - HTTP 429 rate limit detection triggering explicit `BiharBhumiRateLimitError` rather than blind retries.
     - Input validation enforcing 38 official Bihar administrative districts, preventing SSRF and injection attacks.
     - Sanitized logging: Zero session cookies, credentials, or personally identifiable information are logged.

---

## 2. Supported Search Parameters

The adapter supports the exact search taxonomy verified in the live Bihar Bhumi workflow:

| Parameter | Type | Validation / Constraints | Description |
| :--- | :--- | :--- | :--- |
| `state` | String | Fixed: `"Bihar"` | Source state jurisdiction. |
| `district` | String | Must match one of 38 official districts (e.g. `PATNA`, `GAYA`, `MUZAFFARPUR`). Auto-normalizes aliases (e.g. `Motihari` -> `East Champaran`). | Administrative District |
| `circle` / `anchal` | String | Required, trimmed, uppercase | Administrative Anchal |
| `halka` | String | Optional | Revenue Halka number / name |
| `mauza` | String | Required | Revenue village / Mauza name |
| `search_type` | Enum | One of: `KHATA`, `PLOT_NUMBER`, `RAIYAT_NAME`, `JAMABANDI_NUMBER`, `COMPUTERIZED_JAMABANDI_NUMBER` | Target search index |
| `search_value` | String | 1 to 128 characters, non-blank | The query token |

---

## 3. Normalized Record Schema & Field Mappings

The adapter maps only verified revenue fields into the strongly-typed `BiharJamabandiRecord` schema:

| Government Field (Hindi / Portal) | Normalized Internal Field | Schema Type | Conversion & Semantics |
| :--- | :--- | :--- | :--- |
| क्र० सं० (Serial No) | N/A | Row index | Internal table indexing. |
| हल्का (Halka) | `halka` | `Optional[str]` | Revenue subdivision. |
| मौजा (Mauza) | `mauza` | `str` | Revenue village name. |
| खाता संख्या (Khata No) | `khata_number` | `str` | Revenue account identifier. |
| खसरा संख्या (Plot / Khesra No) | `plot_khesra_number` | `str` | Cadastral plot identifier. |
| जमाबंदी संख्या (Jamabandi No) | `jamabandi_number` | `str` | Register-II manual ledger index. |
| कम्प्यूटरीकृत जमाबंदी संख्या | `computerized_jamabandi_number` | `Optional[str]` | Unique 16-digit digital identifier. |
| भाग वर्तमान (Volume) | `volume_bhag_vartaman` | `Optional[str]` | Current physical ledger volume. |
| पृष्ठ संख्या वर्तमान (Page) | `page_pristh_vartaman` | `Optional[str]` | Current physical ledger page. |
| रैयत का नाम (Raiyat Name) | `raiyat_name` | `str` | Recorded tenant / rent payer. |
| पिता / पति का नाम | `father_husband_name` | `Optional[str]` | Parentage / spouse name. |
| कुल रकबा (Total Area) | `original_area_string` | `str` | Preserved verbatim string (e.g. `"1 एकड़ 50 डिसमिल"`). |
| Rakba Extracted Acre | `recorded_area_acre` | `float` | Acre component. |
| Rakba Extracted Decimal | `recorded_area_decimal` | `float` | Decimal component. |
| Calculated Total Acres | `recorded_area_total_acres` | `float` | `acre + (decimal / 100.0)`. |
| Calculated SI Area | `recorded_area_sqm` | `float` | Standardized square meters (1 Ac = 4046.86 sqm, 1 Dec = 40.47 sqm). |
| लगान / भूमि लगान | `lagan_amount_inr` | `Optional[float]` | Annual land revenue cess in INR. |
| जमीन का प्रकार (Land Nature) | `land_nature` | `Optional[str]` | Land classification (e.g. Bhith, Dhanhar, Makan). |

---

## 4. Cryptographic Provenance & Domain Integration

To conform with the Bhumi Setu epistemic architecture, retrieved Jamabandi data is ingested into the domain model without fabricating ownership:

1. **Canonical Property ID Generation:**  
   Calculates an immutable composite ID: `BR-{DISTRICT}-{ANCHAL}-{MAUZA}-KH{KHATA}-PL{PLOT}` (e.g. `BR-PAT-DAN-KOT-KH48-PL112`).
2. **Idempotent Parcel Persistence:**  
   Checks existing `parcels` by `(org_id, state_code, district, anchal, mauza, khata, plot)`. If existing, reuses the existing `Parcel` instance to eliminate duplicates.
3. **Evidence Anchoring:**  
   Creates an immutable `Evidence` row:
   - Authority Tier: `AuthorityTier.REVENUE_RECORD`.
   - Evidence Type: `EvidenceType.GOVERNMENT_RECORD`.
   - Cryptographic Hash: SHA-256 digest calculated directly on raw source HTML/response payload.
   - Storage URI: `source://biharbhumi/jamabandi/{canonical_property_id}`.
4. **Case Linking & Multi-Tenancy:**  
   Associates the parcel and evidence to active investigations via `CaseParcel` and `CaseEvidence` records.
5. **Epistemic Claims Formulation:**  
   Generates strongly-typed `Claim` entities:
   - `ClaimPredicate.RECORDED_OWNER`: Object contains `raiyat_name`, `father_husband_name`, and `jamabandi_number` (with explicit disclaimer `record_type: "JAMABANDI_TENANT"`).
   - `ClaimPredicate.RECORDED_AREA`: Object stores original verbatim area string, acre, decimal, and normalized square meters.
6. **Consistency Engine Integration:**  
   Permits automated comparison of Jamabandi recorded area vs registered sale deeds and cadastral GIS boundaries via `evaluate_claims_consistency()`.

---

## 5. Legal Caveats & Source Limitations

Every query response automatically includes statutory revenue caveats:

> **IMPORTANT STATUTORY NOTICE:**  
> A Jamabandi (Register-II) entry denotes a fiscal tenancy for rent collection purposes under the Bihar Tenancy Act, 1885. In accordance with established Supreme Court jurisprudence (*Sawarni v. Inder Kaur*, 1996; *Bhimabai Mahadeo Kambekar v. Arthur Import & Export Co.*, 2019):
> 1. Revenue entries do not confer, extinguish, or create conclusive legal title to immovable property.
> 2. Jamabandi entries do not record civil court injunctions, lis pendens, or pending partition suits.
> 3. Unregistered family arrangements (Khangi Batwara) are not reflected.
> 4. Recent registered deeds take 30 to 90 days to reflect following mutation proceedings (Dakhil Kharij).

---

## 6. Verification & Test Suite Summary

Executed via `pytest` under Python 3.14 on Windows:
* **Adapter Test Suite:** 14 passed in 2.01s (`backend/tests/test_bihar_bhumi_adapter.py`).
* **Full Backend Regression Suite:** 42 passed in 11.37s.
* **Scenarios Covered:**
  - Arithmetic captcha parsing and regex-based safe evaluation.
  - Query validation: 38 Bihar districts whitelist, valid aliases, and rejection of invalid values.
  - Malformed HTML and empty/ambiguous table handling.
  - Manual ingestion with cryptographic SHA-256 verification.
  - Live HTTP client timeout and HTTP 429 rate limit backoff.
  - Database persistence idempotency (preventing duplicate parcels).
  - Multi-tenant case linking and claim materialization.
  - Conflict detection via Consistency Engine (`RULE_AREA_DELTA_CHECK`).
  - REST API endpoint verification (`/api/v1/parcels/bihar/jamabandi/ingest-manual`).
