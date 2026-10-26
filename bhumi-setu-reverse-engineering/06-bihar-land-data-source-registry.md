# 06 - Bihar Land Data Source Registry

**Target Jurisdiction:** Bihar, India  
**Authority:** Department of Revenue and Land Reforms (राजस्व एवं भूमि सुधार विभाग) & Registration, Excise and Prohibition Department (मद्यनिषेध, उत्पाद एवं निबंधन विभाग)  
**Date of Audit:** October 24, 2026  
**Auditor:** Bhumi Setu Engineering Intelligence  

---

## 1. Official Bihar Land Portals: Empirical Evaluation

| Portal Name | Official URL | Responsible Authority | Primary Land Record Type | Verification Status | Access Constraint |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Bihar Bhumi** | `biharbhumi.bihar.gov.in` / `emutation.bihar.gov.in` | Revenue & Land Reforms Dept (LRC) | Jamabandi (Register-II), Mutation (Dakhil Kharij), Land Possession Certificate (LPC), Revenue Court (RCMS) | **Active (200 OK)** | Public query without captcha for basic search; citizen login required for applications. |
| **Bhu-Naksha Bihar** | `bhunaksha.bihar.gov.in` | Directorate of Land Records & Survey (DLRS) | Cadastral maps, Mauza village sheets, plot boundaries, parcel geometries | **Active (200 OK)** | Web GIS interface; exports plot PDFs and SVG/vector tiles. |
| **Bhu-Abhilekh** | `bhuabhilekh.bihar.gov.in` | DLRS Bihar | Scanned historical survey records (Cadastral Survey Khatiyan, Revision Survey Khatiyan) | **Active (200 OK)** | High-resolution PDF viewer; watermark applied. |
| **Bhumi Jankari** | `bhumijankari.bihar.gov.in` | Registration & Stamps Dept (IGRS Bihar) | Registered Sale Deeds, Minimum Valuation Register (MVR), Encumbrance Index-II | **Active (Legacy SSL / High Load)** | Strict rate-limits; connection reset under heavy traffic; deeds require SRO/year/deed no. |
| **Parimarjan Plus** | `parimarjanplus.bihar.gov.in` | Revenue & Land Reforms Dept | Digitized Jamabandi rectification, missing Khatiyan/plot area corrections | **Active (200 OK)** | Public application tracking via tracking ID; requires citizen phone OTP to file petitions. |
| **e-Mapi Bihar** | `emapi.bihar.gov.in` | Revenue & Land Reforms Dept | Official government land demarcation / Amin measurement booking | **Active (200 OK)** | Booking requires citizen login and Amin fee deposition. |

---

## 2. In-Depth Source Specifications

### 2.1 Source 1: Bihar Bhumi (Jamabandi Register-II)
* **Underlying Service:** `emutation.bihar.gov.in/biharBhumireport/ViewJamabandi.aspx`
* **Administrative Scope:** All 38 Districts, 534 Anchals (Circles), and 45,000+ Mauzas in Bihar.
* **Required Query Identifiers:**
  - District Code (`district_id`)
  - Anchal Code (`circle_id`)
  - Halka Code (`halka_id`)
  - Mauza Code (`mauza_id`)
  - *Plus one of:* Rayat Name, Khata Number, Khesra (Plot) Number, or Jamabandi Number.
* **Returned Fields:**
  - Jamabandi Number, Page Number, Volume Number
  - Rayat Name & Father/Husband Name
  - Khata Number, Khesra/Plot Number
  - Area in Acre, Decimal, Bigha, Katha, Dhur
  - Lagan demand (Annual Rent & Cess)
  - Mutation Case Reference Number & Date
* **Integration Feasibility:** High. Web-accessible structured table with predictable DOM layout and session cookies.

### 2.2 Source 2: Bhu-Naksha Bihar (Cadastral Maps)
* **Underlying Service:** NIC Bhu-Naksha Web GIS Engine (`bhunaksha.bihar.gov.in`)
* **Administrative Scope:** Mauzas with digitized cadastral sheets.
* **Query Parameters:** District -> Sub-Division -> Circle -> Mauza -> Plot Number (`khesra_no`).
* **Returned Data:**
  - Vector polygon coordinates (GeoJSON / SVG)
  - Adjoining parcel boundaries (North, South, East, West neighbor plots)
  - Linked Jamabandi summary for selected plot.
* **Integration Feasibility:** Medium-High. Geometries can be cached in Bhumi Setu's PostGIS spatial database for lightning-fast GIS rendering.

### 2.3 Source 3: Bhumi Jankari (Registration & Deed Search)
* **Underlying Service:** IGRS Bihar Deeds & Encumbrance Portal
* **Record Categories:**
  - Registered Deeds from 1990 to present (digitized post-2006).
  - Minimum Valuation Register (MVR circle rates per decimal for residential, commercial, industrial, and agricultural categories).
* **Integration Constraints:**
  - Server intermittently resets connections during daytime peak hours.
  - Pre-1990 deeds are archived in physical SRO bahi-khatas (volumes) and are not online.
* **Mitigation Strategy:** Hybrid approach — automated scraper for post-2006 digital records + LandAmin field runner network for physical counter inspections in Bihar SROs.

### 2.4 Source 4: Parimarjan Plus (Revenue Rectification Ledger)
* **Underlying Service:** `parimarjanplus.bihar.gov.in/ParimarjanNew/`
* **Purpose:** Allows land owners to apply for correction of digitisation errors in Jamabandi (incorrect name spelling, wrong Khesra, missing area).
* **Value for Bhumi Setu:**
  - Querying Parimarjan Plus tracking (`trackapplication.aspx`) reveals pending rectification disputes or unapproved alterations on a parcel, acting as an early warning signal for property buyers.

---

## 3. Recommended Minimal Viable Source Set (Bihar MVP Pilot)

For Bhumi Setu's initial operational pilot in Bihar, the platform will integrate a curated **Three-Pillar Core Registry**:

1. **Pillar 1 (Revenue Title & Ownership):** `Bihar Bhumi Jamabandi` (identifies recorded rayat, area, Khata/Khesra).
2. **Pillar 2 (Cadastral Geometry):** `Bhu-Naksha Bihar` (validates plot geometry, boundaries, and overlap).
3. **Pillar 3 (Dispute & Rectification Audit):** `Parimarjan Plus & Mutation Defect Tracker` (flags pending title disputes and rejected mutations).

*Deed procurement for pre-2006 transactions will route through the LandAmin field network.*
