# 12 - Property Passport and Land Intelligence Report Design

**Project:** Bhumi Setu  
**Document:** Technical Specification for Property Passports and Generated Land Intelligence Reports  
**Date:** October 24, 2026  

---

## 1. Property Passport Concept

The **Property Passport** is Bhumi Setu's canonical, living digital twin for any land parcel in India. Unlike temporary search results that evaporate after a session, a Property Passport persists across the property's entire lifecycle.

### 1.1 Passport Components
1. **Canonical Identifier:** Guaranteed unique key (e.g. `BR-PAT-DAN-KOT-KH48-PL112`) anchored to state, district, circle, mauza, Khata, and Khesra.
2. **Document Vault:** Tamper-evident repository containing all source documents (deeds, Jamabandi, Bhu-Naksha maps, tax receipts) with SHA-256 integrity proofs.
3. **Living Chain-of-Title Timeline:** Interactive chronological visualization from the root Cadastral Survey Khatiyan through intermediate partitions and transfers to the current recorded holder.
4. **Active Discrepancy Ledger:** Tracks all detected issues, status updates, and resolutions.
5. **Cadastral Geospatial Card:** Interactive PostGIS map showing parcel boundaries, area measurements, and neighboring plots.
6. **Field Verification Dossier:** LandAmin survey measurements, geotagged photographs, and local inquiries.
7. **Complete Audit Trail:** Immutable log of every view, extraction, update, and export.

---

## 2. Land Intelligence Report Structure

The **Land Intelligence Report** is an exportable, publication-grade PDF generated directly from the Property Passport. It is designed to satisfy the rigorous evidentiary standards of bank risk committees, corporate real estate acquirers, and high-court advocates.

### 2.1 Standard 8-Section Report Blueprint

#### Section 1: Property Identification & Executive Brief
* Canonical Property ID & State Administrative Hierarchy (State, District, Circle, Mauza, Thana No).
* Core Revenue Identifiers (Khata Number, Khesra / Plot Number, Jamabandi Number).
* Geographic Coordinates (Centroid Lat/Long) & Cadastral Area (in Local Bihar Units: Bigha-Katha-Dhur and Metric Sq. Meters).
* **Executive Diligence Verdict:** Categorized as `CLEAR / LOW RISK`, `PROVISIONAL / ACTION REQUIRED`, or `HIGH RISK / STOP`.

#### Section 2: Investigation Scope & Records Examined
* Comprehensive audit table listing every document reviewed:
  - Document Type (e.g. *Jamabandi Register-II, Registered Sale Deed, Encumbrance Certificate*)
  - Issuing Office / Authority (e.g. *Circle Office Danapur, SRO Danapur*)
  - Official Document Number & Date
  - Retrieval Rail (*Digital Source API* vs. *SRO Counter Physical Inspection*)
  - Retrieval Date and Cryptographic Hash.

#### Section 3: Verified Ownership & Lineage (Chain of Title)
* Root of Title (Cadastral Survey Khatiyan / RS Khatiyan Rayat).
* Chronological sequence of conveyances (Sale, Gift, Inheritance, Partition).
* Current Recorded Rayat(s) with recorded shares, mutation case numbers, and revenue demand.

#### Section 4: Encumbrance, Charge & Debt Search
* Encumbrance Certificate (EC) findings across the statutory search period (13 years / 30 years).
* CERSAI registered equitable mortgages and financial hypothecations.
* Unsatisfied charges or unreleased deeds highlighted with red warning callouts.

#### Section 5: Cadastral Map & Spatial Analysis
* High-resolution Bhu-Naksha cadastral map snippet showing plot polygon highlighted in blue.
* Tabular verification of boundaries (Chauhaddi) comparing deed descriptions with actual adjacent plot numbers.
* Road access status and notified infrastructure acquisition zones.

#### Section 6: Litigation & Regulatory Compliance
* eCourts search results for matching party names and property schedules.
* Revenue Court Management System (RCMS) dispute status.
* Land ceiling act, government land (*gairmajarua*), and tribal land tenancy restrictions verification.

#### Section 7: LandAmin Field Observations (Ground Truth)
* Summary of physical site visit conducted by certified LandAmin.
* Actual physical possession verification (Who is physically farming/occupying the land?).
* Demarcation notes, boundary stone markers, and geotagged timestamped site photographs.

#### Section 8: Evidentiary Disclaimers & Certification
* **Mandatory Statutory Disclaimer:**
  > *"This Land Intelligence Report is an evidentiary synthesis of available public revenue, registration, survey, and field records. It does not constitute a statutory certificate of conclusive title under Indian law, nor is it a substitute for a signed legal title certificate issued by an enrolled advocate. Official revenue records are prima facie evidence of possession and fiscal liability, not conclusive proof of title."*
* QR Code linking directly to the live digital Property Passport for verification of authenticity.

---

## 3. Automated Report Generation Engine

* **Technology Stack:** Python `WeasyPrint` rendering responsive HTML5/CSS3 templates into print-ready PDF/A archival documents.
* **Execution Time:** Under 2.5 seconds to compile and render an 8-page report with embedded vector map graphics.
