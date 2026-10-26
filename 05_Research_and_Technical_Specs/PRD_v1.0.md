# BHUMI SETU — PRODUCT REQUIREMENTS DOCUMENT (PRD v1.0)

**Product:** BhumiSetu  
**Category:** Land Intelligence, Verification & Advisory Platform  
**Initial Geography:** Deoghar, Jharkhand + Banka, Bihar (20 km Urbanization Belts)  
**Primary Wedge:** Land survey, verification, documentation and advisory (Land Amin)  
**Long-term Category:** Land intelligence & transaction infrastructure  
**Document Version:** PRD v1.0  

---

## 1. Product Vision & Thesis

> **Build the trusted digital infrastructure through which people and organizations understand, verify, manage and transact land.**

### The Core Problem: The Gap Between Land Realities
Land decisions in India are paralyzed by discrepancies across 6 distinct realities:
1. **Legal Reality:** What registered sale deeds, will deeds, and power of attorney documents say.
2. **Government-Record Reality:** What Khatiyan, Jamabandi, Dakhil Kharij (mutation), and Cadastral maps show.
3. **Physical Reality:** What exists on the ground between boundary pins, ridges (*aals*), and markers.
4. **Possession Reality:** Who actually occupies, fences, or cultivates the land and exercises control.
5. **Transaction Reality:** Whether the parcel can legally, safely, and cleanly be transferred without encumbrances or tribal/tenancy restrictions (e.g., CNT/SPT Act).
6. **Market Reality:** The true commercial valuation and upcoming infrastructure developments.

**BhumiSetu lives in the gap between these realities.** It is the **Truth Layer** that cross-checks government records against physical ground reality.

---

## 2. Product Principles

1. **Property-Centric (Not Customer/Order-Centric):** The central entity in the database is the **Property Node** (`BS-JH-DEO-XXXXXX`). Orders, customers, surveys, and documents attach to the property.
2. **Evidence & Provenance-First:** No naked attributes. Every data point (Area, Owner, Road Width) tracks its source (Deed vs Survey), verifier ID, confidence, and timestamp.
3. **Services Fund the Data Asset:** High-frequency, high-trust field surveying (Land Amin) generates immediate cash flow and feeds structured coordinates into the proprietary property graph.
4. **Human-in-the-Loop AI:** AI assists in OCR, entity extraction, discrepancy detection, and report drafting, but certified professionals (Amins, Advocates) verify consequential findings.
5. **Offline-Capable Field Tooling:** Field Amins operate in low-connectivity peri-urban and rural areas; local caching with sync-on-reconnect is mandatory.

---

## 3. The 3 Interconnected Products

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        BHUMI SETU PLATFORM                             │
├───────────────────────┬────────────────────────┬───────────────────────┤
│ PRODUCT A:            │ PRODUCT B:             │ PRODUCT C:            │
│ FIELD SERVICE ENGINE  │ PROPERTY INTELLIGENCE  │ ENTERPRISE LAND OS    │
│ (Land Amin)           │ (Land Passport)        │ (Portfolio MGMT)      │
├───────────────────────┼────────────────────────┼───────────────────────┤
│ • Boundary Survey     │ • Bhumi Property ID    │ • Multi-Parcel Port.  │
│ • Area Measurement    │ • Truth Delta Engine   │ • Annual Verification │
│ • Chauhadri Check     │ • Risk Scoring Matrix  │ • Encroachment Alerts │
│ • Document Collation  │ • Longitudinal Timeline│ • Institutional DD    │
└───────────────────────┴────────────────────────┴───────────────────────┘
```

---

## 4. Entity Architecture & Property Schema

```text
PROPERTY (BS-JH-DEO-000001)
├── Metadata (State, District, Anchal, Mauza, Thana No, Khata No, Khasra/Plot No)
├── Owners (Claimants, Documented Raiyats, Possession holders)
├── Documents (Khatiyan, Registry Deeds, Mutation Receipts, Lagan Rasid)
├── Surveys (GPS Points, Boundary Polygon, Area, Chauhadri, Photo Evidence)
├── Evidence (Fact -> Source Document -> Page No -> Verifier -> Confidence)
├── Risk Assessment (6-Dimension Scoring: Title, Boundary, Mutation, Encumbrance, etc.)
├── Timeline (Historical reconstruction of transfers, partitions, surveys)
└── Reports (Generated Land Passport, Survey Certificate, Due Diligence Dossier)
```

---

## 5. Risk Assessment Engine: 6 Dimensions

1. **Title & Ownership Integrity:** Mismatches between Khatiyan Raiyat, Deed Transferee, and current Claimant.
2. **Spatial & Boundary Variance:** Difference between Cadastral map area, Deed area, and GPS measured ground area.
3. **Tenancy & Regulatory Restrictions:** Section 49 / CNT / SPT Act tribal land transfer restrictions, Ceiling Act limits.
4. **Mutation & Revenue Compliance:** Dakhil Kharij execution status, up-to-date Lagan (land revenue) receipts.
5. **Physical Encroachment & Access:** Verification of actual motorable road access and perimeter encroachments.
6. **Litigation & Dispute Signals:** Active 144/145 CrPC proceedings, local dispute intelligence, partition contestations.

---

## 6. Pilot Execution: Deoghar / Banka Wedge

- **Target Unit:** Deoghar District HQ + 20 km Urban/Peri-urban Expansion Belt (Mohanpur, Jasidih, Sarath, Kunda, Devpura).
- **Core Milestone:** First 500 Properties Verified -> 500 Structured Geo-Referenced Truth Nodes -> Foundations of the Local Land Graph.
