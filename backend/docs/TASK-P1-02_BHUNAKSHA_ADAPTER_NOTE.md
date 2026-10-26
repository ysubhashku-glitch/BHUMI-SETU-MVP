# Technical Implementation Note: TASK-P1-02 Bihar Bhu-Naksha Cadastral Map Ingestion & Spatial Cache

**Component:** Bihar Bhu-Naksha Cadastral Vector Map Ingestion & Spatial Cache Adapter  
**Target Path:** `backend/app/services/scrapers/bhunaksha.py`  
**Router Path:** `backend/app/routers/parcels.py`  
**Test Suite:** `backend/tests/test_bhunaksha_adapter.py`  
**Date:** October 24, 2026  
**Status:** Completed & Tested (20/20 new tests passing, 62/62 regression tests passing)

---

## 1. Official Government Source & Operational Characteristics

* **Official Portal:** Directorate of Land Records & Survey (DLRS), Department of Revenue and Land Reforms, Government of Bihar (राजस्व एवं भूमि सुधार विभाग, बिहार)
* **Target Interface:** NIC Bhu-Naksha Web GIS Engine
* **Verified URL:** `https://bhunaksha.bihar.gov.in/` (Redirects to `/10/index.jsp` / `/10/indexmain.jsp`)
* **Access Architecture:**
  1. **Dual-Mode Operational Ingestion:**
     - **Automated Live Query Client (`BhuNakshaLiveClient`):** Handles session initialization, cookie jar preservation (F5 BIG-IP WAF ASM token `TS012e5105`, `JSESSIONID`, `Bhu_Nak_cookies_Name`), village extent georef queries (`/rest/MapInfo/getVVVVExtentGeoref`), and official Land Parcel Map (LPM) Certificate PDF downloads (`/rest/Reports/PlotReportPDF`).
     - **Resilient User-Assisted / Manual Importer (`ingest_cadastral_artifact`):** Ingests official cadastral survey vector artifacts (GeoJSON, SVG, WKT, or Base64 LPM PDFs). This ensures investigations remain 100% operational during government maintenance, WAF/Cloudflare throttling, or un-digitized Mauzas.
  2. **Security & Validation Controls:**
     - Explicit CRS enforcement (`EPSG:32645` or `EPSG:4326`); rejects undocumented or missing CRS.
     - Coordinate range sanity verification against Bihar geographic envelope (Lon 83.0–88.5, Lat 24.0–27.8) and UTM Zone 45N grid (Easting 150,000–950,000, Northing 2,600,000–3,150,000).
     - Cryptographic SHA-256 deduplication and evidence anchoring.
     - Sanitized logging: zero session cookies, credentials, or client tokens are logged.

---

## 2. Administrative Hierarchy & Selection Workflow

The adapter models the official 7-level NIC Bhu-Naksha administrative hierarchy:

| Level | Administrative Entity | Source Mechanism / Endpoint |
| :--- | :--- | :--- |
| **Level 1** | District (`level_1`) | 38 official districts with 2-digit NIC codes (e.g. `28 PATNA`, `35 GAYA`, `14 MUZAFFARPUR`). |
| **Level 2** | Sub-Division (`level_2`) | `POST /ScalarDatahandler` with `OP=2, level=2, selections={dist_code}, state=10`. |
| **Level 3** | Circle / Anchal (`level_3`) | `POST /ScalarDatahandler` with `OP=2, level=3, selections={dist},{sub}, state=10`. |
| **Level 4** | Mauza / Village (`level_4`) | `POST /ScalarDatahandler` with `OP=2, level=4, selections={dist},{sub},{circle}, state=10`. |
| **Level 5** | Survey Type (`level_5`) | Cadastral Survey (CS 1905–1915) vs Revision Survey (RS 1965–1985). |
| **Level 6** | Map Instance (`level_6`) | Digitized sheet instance index. |
| **Level 7** | Sheet Number (`level_7`) | Cadastral village sheet number (e.g. `Sheet 01`, `Sheet 02`). |
| **Plot** | Khesra / Plot Number | Parcel polygon selection by plot number or coordinate intersection (`/rest/MapInfo/getPlotAtXY`). |

---

## 3. Supported Geometry Formats & Metrology

The adapter parses and standardizes heterogeneous vector representations into valid Shapely 2.0 `Polygon` or `MultiPolygon` structures:

| Ingested Format | Parser Engine | Normalization Target | Metrology & Area Conversion |
| :--- | :--- | :--- | :--- |
| **GeoJSON** | `shapely.geometry.shape` | GeoJSON dict & WKT string | If `EPSG:32645`: direct polygon area in square meters. If `EPSG:4326`: geodesic scaling factor applied. |
| **SVG XML** | `xml.etree.ElementTree` regex parser | Extracts `<polygon points="...">` or `<path d="M...L...Z">` | Standardized to 2D polygon vertices. |
| **WKT** | `shapely.from_wkt` | Validates polygon coordinates | Standard WKT representation in `parcels.authoritative_boundary`. |
| **LPM Certificate PDF** | Base64 decode + SHA-256 digest | PDF Evidence reference | Preserves official government plot map certificate as immutable document evidence. |

### Topology Validation & Repair Rules
- **Empty Geometry:** Automatically rejected with `BiharBhuNakshaGeometryValidationError`.
- **Topological Defects:** Evaluates `geom.is_valid`. If invalid (e.g. self-intersecting polygon ring), applies non-destructive `shapely.validation.make_valid()`, recording `repair_applied=True` while retaining original defect details in `topology_error`.
- **CRS Non-Hallucination:** Rejects inputs with missing CRS. Never silently assumes an unverified coordinate system.

---

## 4. Revenue-to-Map Cross-Referencing Engine

`BiharBhuNakshaAdapter.compare_cadastral_to_revenue()` creates an explicit, auditable bridge between cadastral map geometry and revenue Jamabandi records:

1. **Plot Identifier Concordance:** Checks if Khesra and Khata numbers correspond across map sheets and revenue ledgers. Mismatches flag `IDENTIFIER_MISMATCH`.
2. **Area Metrology Consistency:** Evaluates revenue stated area (converted to square meters) against GIS calculated polygon area using Bhumi Setu's `check_area_delta()`:
   - Delta $\le 5\%$: `CONCORDANT` (Informational severity).
   - Delta $> 5\%$ to $15\%$: `AREA_DISCREPANCY` (High severity).
   - Delta $> 15\%$: `AREA_DISCREPANCY` (Critical severity, triggers Amin field survey recommendation).
3. **Statutory Legal Disclaimers:** Explicitly attaches disclaimers noting that cadastral maps reflect historical revenue survey lines and do not confirm real-time ground possession or the absence of boundary encroachments (*aal* shifts).

---

## 5. Domain Model Integration & Cryptographic Provenance

When persisting to the Bhumi Setu domain database:
1. **Canonical Bhumi ID:** Generates composite ID `BR-{DIST}-{CIRCLE}-{MAUZA}-PL{PLOT}` (e.g. `BR-PAT-DAN-KOT-PL112`).
2. **Idempotent Parcel Persistence:** Updates existing `Parcel` with `authoritative_boundary` and `centroid_point`, preserving administrative hierarchy.
3. **Audit Trail Versioning:** Creates a `ParcelVersion` record (`change_reason="BHUNAKSHA_CADASTRAL_INGESTION"`).
4. **Evidence Anchoring:** Inserts an immutable `Evidence` record:
   - `evidence_type = EvidenceType.MAP`
   - `authority_tier = AuthorityTier.REVENUE_RECORD`
   - `sha256_hash = record.sha256_hash`
   - `storage_uri = source://bhunaksha/cadastral/{district}/{mauza}/plot_{khesra}`
5. **Epistemic Claim Generation:** Formulates a `Claim` with `predicate = ClaimPredicate.CADASTRAL_GEOMETRY`, storing normalized geometry, CRS, and calculated area metrics.
6. **Multi-Tenant Security:** Strictly enforces tenant boundaries; cross-tenant access to spatial geometry returns HTTP 403 Forbidden.

---

## 6. API Endpoints Reference

| HTTP Method | Route | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/parcels/bihar/bhunaksha/query` | Queries live Bhu-Naksha metadata, GIS code, and CRS for village. |
| `POST` | `/api/v1/parcels/bihar/bhunaksha/ingest` | Ingests cadastral artifact (GeoJSON, SVG, WKT, LPM PDF) with validation and optional domain persistence. |
| `POST` | `/api/v1/parcels/bihar/bhunaksha/compare-revenue` | Cross-references cadastral parcel with Jamabandi revenue record (area delta & discrepancies). |
| `GET` | `/api/v1/parcels/{parcel_id}/spatial` | Retrieves boundary geometry, GeoJSON, bounding box, area metrics, and evidence provenance. |

---

## 7. Verification & Regression Suite

* **Unit & Integration Suite (`test_bhunaksha_adapter.py`):** 20 passed of 20 tests.
* **Full Backend Regression Suite:** 62 passed of 62 tests in 14.96s (100% pass rate).
* **Zero Regressions:** All existing API, auth, document pipeline, consistency, and database tests remain completely passing.
