# 05 - Observed Routes and Integrations

**Investigation Target:** Landeed Platform Infrastructure  
**Audit Date:** October 24, 2026  
**Auditor:** Bhumi Setu Engineering Intelligence  

---

## 1. Domain and Route Topology

Through network tracing and CDP inspection, Landeed's distributed architecture was observed across the following distinct hostnames:

| Hostname | Purpose / Stack | Observed Protocol |
| :--- | :--- | :--- |
| `www.landeed.com` | Marketing website, product overviews, pricing, enterprise demo booking (Astro / Cloudflare CDN). | HTTPS |
| `web.landeed.com` | Primary citizen & enterprise web application (Next.js 14/15, Tailwind, Mapbox). | HTTPS |
| `backend.landeed.com` | Core business logic, authentication, configuration, order state management (Python / FastAPI / Uvicorn). | HTTPS / REST |
| `bedrock.landeed.com` | AI orchestration, prompt categorization, Terra reasoning engine (Python / Uvicorn / LLM adapter). | HTTPS / REST |
| `api.landeed.com` | Public enterprise B2B REST API for programmatic document procurement (`/v1/orders`, `/v1/documents/retrieve`). | HTTPS / REST |
| `dv-*.ecs.us-east-1.on.aws` | AWS Elastic Container Service (ECS) telemetry and event collection endpoint. | HTTPS / REST |

---

## 2. Documented API Endpoints & Schemas

### 2.1 Feature Flags & Client Configuration
* **Endpoint:** `GET https://backend.landeed.com/api/v1/app_config/v2/feature_flags/`
* **Observed Headers:**
  - `Accept: application/json; version=web2.0`
  - `Platform: Web`
  - `x-web-build: 0.75.7`
* **Response Status:** `200 OK` (Server: `uvicorn`)
* **Extracted Payload Schema:**
  ```json
  {
    "anr_show_voice_ai": false,
    "anr_show_landeed_lens": false,
    "anr_show_webview_pdf_viewer": true,
    "default_login_otp_method": 1,
    "app_bills_tab_enabled": false,
    "voice_agent_default_price": 99,
    "multi_doc_minimum_price": 199,
    "show_terra_on_home_search_send_cta": true,
    "show_terra_map_banner": true,
    "gs_price_extra_percent": 30,
    "show_get_all_documents": false
  }
  ```

### 2.2 Dynamic State Intent Categories
* **Endpoint:** `GET https://bedrock.landeed.com/api/home/categories?state=bihar`
* **Observed Headers:**
  - `x-terra-version: TERRA4.0`
  - `Accept: application/json`
  - `Host: bedrock.landeed.com`
* **Response Status:** `200 OK` (Server: `uvicorn`)
* **Payload Structure:** Returns tailored prompt categories for the specified state (`Know Before You Buy`, `Explore the Map`, `Get Certified Proof`, `Ancestral Records`).

### 2.3 B2B Document Procurement API (Enterprise)
* **Endpoint:** `POST https://api.landeed.com/v1/documents/retrieve`
* **Request Schema:**
  ```json
  {
    "survey_no": "42/1",
    "district": "Rangareddy",
    "state": "TS",
    "types": ["ec", "sale_deed", "mutation"]
  }
  ```
* **Response Schema:**
  ```json
  {
    "status": "success",
    "property_id": "ts-rr-42-1",
    "documents": [
      {
        "type": "ec",
        "status": "ready",
        "url": "https://storage.landeed.com/docs/.../ec.pdf",
        "retrieved_at": "2026-10-24T02:15:00Z"
      }
    ]
  }
  ```

### 2.4 B2B Order Creation API (Hybrid Counter + Source)
* **Endpoint:** `POST https://api.landeed.com/v1/orders`
* **Request Schema:**
  ```json
  {
    "state": "KA",
    "document": "encumbrance_certificate",
    "sro": "Hoskote",
    "hobli": "Anugondanahalli",
    "village": "Samethanahalli",
    "survey_no": "114/2",
    "years": 30
  }
  ```
* **Response Status:** `202 Accepted`
* **Lifecycle Webhook:** Fires `order.fulfilled` when certified copy is scanned from physical SRO.

---

## 3. Terra MCP Remote Server Specification

Landeed exposes an official **Model Context Protocol (MCP)** interface for AI agents (`streamable-http`, OAuth 2.1):

| Tool Name | Parameters | Return Type | Data Source |
| :--- | :--- | :--- | :--- |
| `resolve_property` | `address: string, survey_no?: string, khata?: string, village?: string` | `CandidateParcels[]` | Revenue & Municipal master registers |
| `check_coverage` | `state: string, district: string, document: string` | `CoverageReport` | Landeed live availability matrix |
| `get_ownership` | `property_id: string` | `OwnershipRecord` | Digitized RoR / Jamabandi / RTC |
| `get_encumbrances`| `property_id: string, years: number` | `EncumbranceFinding[]` | EC Form 15, CERSAI, ROC charges |
| `list_transactions`| `property_id: string` | `TransactionHistory[]` | SRO registered deed indices |
| `search_litigation`| `property_id: string, parties: string[]` | `CourtCaseFinding[]` | eCourts, High Courts, NCLT |
| `get_land_classification`| `property_id: string` | `ClassificationReport` | Revenue classification & master zoning |
| `get_source_document` | `document_id: string` | `SourceDocumentPDF` | Raw certified document copy |

---

## 4. Third-Party Integrations Fingerprint

* **Mapping & Geodata:** Mapbox GL JS Vector Tiles, custom style `cm99s72oi000101s83aw6gkgj`.
* **Authentication & Identity:** Firebase Authentication (`firebaseinstallations.googleapis.com`), Project `landeed`.
* **Telemetry & Product Analytics:** Amplitude (`api2.amplitude.com`), Microsoft Clarity (`scripts.clarity.ms`), Google Analytics 4 (`analytics.google.com`).
* **Cloud Infrastructure:** AWS ECS (US-East-1), Cloudflare CDN for edge caching.
