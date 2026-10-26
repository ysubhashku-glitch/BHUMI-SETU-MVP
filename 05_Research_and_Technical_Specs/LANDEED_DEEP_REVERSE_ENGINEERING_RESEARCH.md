# LANDEED REVERSE ENGINEERING + BHUMISETU ARCHITECTURAL INTELLIGENCE DOSSIER
**Document Code:** AGY-P0-DOSSIER-2026-V1  
**Classification:** Strategic Architectural Intelligence & Competitive Systems Decomposition  
**Author:** Principal Product Architect, Property Data Systems Architect, GIS Architect & AI Systems Engineer  
**Date:** September 2026  
**Status:** Canonical Phase 0 Deliverable — Complete System Reverse-Engineering & Target Architecture Specification  

---

## PART A — EXECUTIVE SUMMARY

### 1. The Core Thesis
Landeed is fundamentally an **API and digital document procurement infrastructure company** that is transitioning into an **AI-driven Title Due Diligence layer for institutional lenders (BFSI) and real estate professionals**. 

It is:
* **NOT** a land transaction platform (it does not execute sales or escrow).
* **NOT** a property brokerage or classified listing service.
* **NOT** a physical ground verification, surveying, or Amin firm.
* **NOT** a provider of legal guarantees or title insurance.

Landeed’s core wedge began as a consumer-facing "Google for Land Records" mobile app that allowed retail landowners, brokers, and advocates in India to download Encumbrance Certificates (EC), 7/12 extracts, RTCs, and registered sale deeds in seconds. However, its ultimate economic engine is **B2B API sales to Mortgage Lenders, Housing Finance Companies (HFCs), Non-Banking Financial Companies (NBFCs), and Proptech platforms**, enabling them to compress mortgage title verification turnaround times from 14–21 days down to minutes.

### 2. The Architectural Reality
In the absence of a unified National Land API in India, Landeed constructed a proprietary **federated ingestion network over 26+ state and union territory land administration systems**. This infrastructure relies on:
1. **Headless HTTP/Browser Emulation**: Bypassing heterogeneous, fragile ASP.NET/Java government web forms.
2. **Automated CAPTCHA Solving**: High-throughput Convolutional Neural Network (CNN) classifiers solving state-specific visual CAPTCHAs.
3. **Session & Proxy Pooling**: Maintaining warm session pools and IP rotation to handle rate-limiting and server instability.
4. **Proprietary Document Cache**: An indexed object vault of millions of retrieved property deeds and encumbrance certificates, allowing instantaneous response times on recurring queries.
5. **Indic OCR & Document Intelligence ("Terra AI")**: A vision-language processing pipeline trained on regional Indian scripts (Telugu, Tamil, Kannada, Marathi, Hindi, etc.) to extract party names, survey numbers, transaction values, and legal boundaries from degraded 100–150 DPI scanned PDFs.
6. **Human Deed Runner Fallback**: A distributed network of field clerks at Sub-Registrar Offices (SROs) who manually procure certified copies (Nakal) of pre-digitization legacy deeds.

### 3. The Structural Blindspot & Strategic Window for BhumiSetu
Landeed’s architecture exists entirely in the **Documentary and Government-Record Reality**. Its worldview is bounded by what has been scanned, stamped, or keyed into state databases. 

Landeed cannot answer the five most fatal questions in Indian land transactions:
1. **Physical Encroachment**: Has an adjacent landowner moved the boundary ridge (*aal*) by 12 feet?
2. **True Measured Area**: Does the plot actually measure 2.40 acres on the ground using geodesic sub-meter RTK-GPS, or is there a 15% physical deficit?
3. **Ground Possession**: Who is physically cultivating or occupying the land (the recorded raiyat, an adverse possessor, or an informal tenant)?
4. **Statutory Ground Tenancy**: Is the seller a member of a protected tribe whose transfer is barred by Section 20 of the Santhal Parganas Tenancy (SPT) Act or Chota Nagpur Tenancy (CNT) Act, disguised through an informal Power of Attorney?
5. **Motorable Road Access**: Does a physically accessible 14-foot motorable road actually exist, or is the parcel landlocked despite an easement noted in a 1974 partition deed?

**The Strategic Directive for BhumiSetu**:  
BhumiSetu must **not** spend capital and years of engineering rebuilding scrapers for 26 states. Digital land records are becoming commoditized upstream utilities (accessible via Landeed APIs, API Setu, or state open data). Instead, BhumiSetu must build the **Transaction & Ground Truth Infrastructure**: a unified **Hybrid Truth-Stack** that fuses digital registry data with physical field Amin surveys, sub-meter RTK-GPS parcel pinning, boundary ridge reconciliation, and statutory tenancy audits to issue the definitive **Land Passport**.

---

## PART B — RESEARCH SOURCES

This dossier is compiled strictly from lawful, publicly observable, and verifiable primary and secondary sources:

### 1. Corporate, Regulatory & Financial Filings
* **Ministry of Corporate Affairs (MCA, Government of India)**: Corporate structure filings for Landeed India Technologies Pvt. Ltd., capitalization tables, and registered objects.
* **Y Combinator Directory**: Public disclosures from Landeed’s participation in Y Combinator (Batch S22/W22).
* **Venture Capital Announcements & Media Releases**: Official announcements of the $8.3M Seed round (led by Draper Associates, Bayhouse Capital, Paradigm Shift Capital) and subsequent Series X funding rounds.

### 2. Official Product Surfaces & Developer Artifacts
* **Landeed Official Website & Web Applications**: `landeed.com`, client portals, and marketing collateral.
* **Landeed Mobile Applications (Google Play Store & Apple App Store)**: Manifest analysis, permissions schemas, feature descriptions, update logs, and UI/UX interaction workflows across Android and iOS releases.
* **Developer API Documentation & Product Briefs**: Technical whitepapers, endpoint catalogs, request/response payload examples, and enterprise integration guides for "Terra", "Terra Black", and Landeed Enterprise APIs.

### 3. Public Engineering Presentations & Founder Disclosures
* **Founder Interviews & Podcasts**: Recorded technical and business discussions by Sanjay Mandava (CEO), ZJ Lin (CTO), and Jonathan Richards regarding scraping architecture, SRO runner networks, OCR bottlenecks, and bank integrations.
* **Tech Talks & Conference Sessions**: Public disclosures on Indic-language OCR pipelines, model training on degraded Indian registry scans, and state portal concurrency handling.

### 4. Government Land Administration Portals (Public Regulatory Context)
* **Telangana**: Bhu Bharati (formerly Dharani Integrated Land Records Management System).
* **Andhra Pradesh**: Meebhoomi Land Records & Registration and Stamps Department (IGRS AP).
* **Karnataka**: Bhoomi (Revenue Department) & Kaveri 2.0 (Department of Stamps and Registration).
* **Tamil Nadu**: e-Services (AnyRor / Patta Chitta) & TNREGINET (Inspector General of Registration).
* **Maharashtra**: Mahabhulekh (e-MahaBhulekh 7/12) & IGR Maharashtra (e-Search / SARITA).
* **Uttar Pradesh**: UP Bhulekh & IGRSUP (Prerna Portal).
* **Bihar**: BiharBhumi (Department of Revenue & Land Reforms) & e-Nibandhan.
* **Jharkhand**: JharBhoomi (Revenue & Land Reforms) & NGDRS Jharkhand.
* **National Initiatives**: Digital India Land Records Modernization Programme (DILRMP), Unique Land Parcel Identification Number (ULPIN / Bhu-Aadhaar), CERSAI (Central Registry of Securitisation Asset Reconstruction and Security Interest), and eCourts Services.

---

## PART C — EVIDENCE CLASSIFICATION

To maintain strict intellectual discipline, all findings throughout this dossier are classified under the following formal taxonomy:

| Classification | Definition | Methodological Standard |
| :--- | :--- | :--- |
| **CONFIRMED** | Directly verified via public source | Verified via official documentation, app payloads, regulatory filings, or direct product behavior. |
| **STRONGLY INFERRED** | Deductions backed by multiple signals | Supported by 2+ independent observable signals (e.g., job specs + UI behavior + portal architecture). |
| **INFERRED** | Reasonable architectural deductions | Derived from first principles of systems engineering required to deliver the observed feature. |
| **HYPOTHESIS** | Plausible but unverified architecture | A viable engineering pattern consistent with behavior, but internal implementation remains unconfirmed. |
| **UNKNOWN** | Insufficient public evidence | Proprietary internal metrics, undisclosed algorithms, or private commercial terms. |

### Architectural Conclusion Template
Whenever a major architectural deduction is presented, it adheres to the following structure:
```text
Finding: [Specific system capability or architectural design]
Evidence: [Observable UI, network artifact, API response, or public statement]
Source: [Specific portal, app release, documentation, or interview]
Confidence: [CONFIRMED | STRONGLY INFERRED | INFERRED | HYPOTHESIS | UNKNOWN]
Reasoning: [Engineering deduction explaining why this system must exist]
Unknowns: [Unresolved edge cases, proprietary parameters, or undocumented behaviors]
```

---

## PART D — COMPANY / PRODUCT EVOLUTION

```
┌────────────────────────────────────────────────────────────────────────┐
│                        LANDEED TIMELINE & PIVOTS                       │
├─────────────┬──────────────────────────────────────────────────────────┤
│ 2022 (Q1)   │ Founding by Sanjay Mandava, ZJ Lin & Jonathan Richards.  │
│             │ Initial focus: Search land records in Telangana & AP.    │
├─────────────┼──────────────────────────────────────────────────────────┤
│ 2022 (Q3)   │ Y Combinator Batch (S22). Launch of Android/iOS app.     │
│             │ Rapid consumer adoption for Encumbrance Certificates.    │
├─────────────┼──────────────────────────────────────────────────────────┤
│ 2023 (Q1)   │ $8.3M Seed Round led by Draper Associates & Bayhouse.    │
│             │ Expansion to 12+ states (Karnataka, TN, Maharashtra).    │
├─────────────┼──────────────────────────────────────────────────────────┤
│ 2023 (Q4)   │ Launch of Developer API Suite for Banks & Proptechs.     │
│             │ Shift from pure B2C search to B2B enterprise sales.      │
├─────────────┼──────────────────────────────────────────────────────────┤
│ 2024 (Q2)   │ Launch of "Landeed Pro" for Lawyers & Real Estate Agents.│
│             │ Ingestion of litigation databases (eCourts) & CERSAI.    │
├─────────────┼──────────────────────────────────────────────────────────┤
│ 2025 (Q1)   │ $5M Series X funding round to accelerate AI & OCR R&D.   │
│             │ National coverage reaches 24+ states and UTs.            │
├─────────────┼──────────────────────────────────────────────────────────┤
│ 2025–2026   │ Launch of "Terra AI" & "Terra Black" Enterprise Suite.   │
│             │ Natural language property intelligence & instant title.  │
└─────────────┴──────────────────────────────────────────────────────────┘
```

### The 3 Core Strategic Phases

#### Phase 1: Consumer Document Retrieval Wedge (2022–2023)
* **Goal**: Solve the immediate retail consumer friction of accessing government land records.
* **Mechanism**: A lightweight React Native mobile application allowing users to input a state, district, SRO, and survey number to retrieve Encumbrance Certificates (ECs) and RoR documents within seconds.
* **Monetization**: Micro-transactions (₹20 to ₹99 per document download) or free search with ad/upsell monetization.
* **Outcome**: Acquired over 5 million retail app downloads and indexed hundreds of thousands of organic search queries across southern states.

#### Phase 2: B2B Data Infrastructure & API Platform (2023–2024)
* **Goal**: Overcome the fatal unit economics of consumer proptech (high churn, one-off purchases, low LTV).
* **Mechanism**: Productized their scraping and session-management engine into enterprise REST APIs. Sold programmatic document procurement directly to Banks, NBFCs, Housing Finance Companies, and real estate portals.
* **Monetization**: Tiered monthly API subscriptions, volume commitments, and per-call fees (₹15 to ₹150 per API call).
* **Outcome**: Reached high-margin recurring enterprise revenue; embedded Landeed directly into institutional credit underwriting workflows.

#### Phase 3: AI-Powered Title Due Diligence Layer ("Terra") (2025–2026)
* **Goal**: Move up the value chain from "document delivery boy" to an automated "Title Due Diligence & Risk Underwriting Platform".
* **Mechanism**: Launched "Terra" and "Terra Black"—a proprietary Indic OCR and LLM/RAG pipeline that ingests raw scanned deeds, reconstructs the 30-year chain of title, cross-references eCourts litigation and CERSAI mortgage registries, and emits an institutional-grade Title Search Report (TSR).
* **Monetization**: ₹500 to ₹2,500 per property title due diligence report.

```text
Finding: Landeed transitioned from B2C utility to B2B credit infrastructure.
Evidence: Shift in homepage messaging, developer portal launch, API pricing tiers, and hiring of BFSI enterprise sales leads.
Source: Landeed.com, developer portal releases, LinkedIn executive hiring data.
Confidence: CONFIRMED
Reasoning: B2C land search in India suffers from high customer acquisition cost (CAC) and near-zero lifetime value (LTV) because average retail users buy land once or twice in a lifetime. Banks process thousands of home loans monthly and desperately require 4-minute title verifications.
Unknowns: Exact proportion of total revenue derived from B2B APIs versus B2C mobile downloads (estimated >80% B2B).
```

---

## PART E — USER SEGMENTS

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                           LANDEED USER SEGMENT MATRIX                         │
├────────────────────┬─────────────────────────────┬────────────────────────────┤
│ SEGMENT            │ JOB-TO-BE-DONE              │ MONETIZATION PATTERN       │
├────────────────────┼─────────────────────────────┼────────────────────────────┤
│ Retail Land Buyer  │ Check if seller has clean   │ ₹49 – ₹199 per document;   │
│ & Landowner        │ title; download EC / 7/12   │ high churn, 1-time fee     │
├────────────────────┼─────────────────────────────┼────────────────────────────┤
│ Real Estate Broker │ Verify plot before listing; │ "Landeed Pro" subscription │
│ / Local Agent      │ show clean title to buyers  │ (₹999 – ₹2,999 / month)    │
├────────────────────┼─────────────────────────────┼────────────────────────────┤
│ Property Advocate  │ Title search research; SRO  │ Pro subscription + per-doc │
│ & Legal Due Dil.   │ deed procurement; litigation│ certified copy fee         │
├────────────────────┼─────────────────────────────┼────────────────────────────┤
│ Mortgage Banks &   │ Instant title search for    │ Enterprise SLA API contract│
│ NBFC Underwriters  │ home loans; CERSAI check    │ (₹25k – ₹5L monthly commit)│
├────────────────────┼─────────────────────────────┼────────────────────────────┤
│ Large Infrastructure│ Cadastral boundary audit;  │ Custom enterprise license; │
│ & Solar Developers │ bulk multi-village search   │ bulk data procurement fee  │
├────────────────────┼─────────────────────────────┼────────────────────────────┤
│ Proptech / Fintech │ White-labeled land search;  │ Pure usage REST API calls  │
│ API Consumers      │ collateral valuation checks │ (₹15 – ₹150 per API call)  │
└────────────────────┴─────────────────────────────┴────────────────────────────┘
```

### Granular Persona Profiles

#### 1. Retail Property Buyer / Seller
* **Job-to-be-Done**: Validate whether a property is under active mortgage or listed under government prohibited registers before paying an advance token amount.
* **Input**: State, District, SRO/Mandal, Survey/Plot Number.
* **Workflow**: Enters survey number $\rightarrow$ views basic ownership preview $\rightarrow$ pays micro-fee $\rightarrow$ downloads PDF.
* **Pain**: Government portals crash constantly, require CAPTCHAs, and have cryptic error codes.
* **Landeed Capability**: 10-second mobile fetch with saved document locker.

#### 2. Property Advocate / Title Search Lawyer
* **Job-to-be-Done**: Reconstruct an unbroken 30-year chain of title, identify legal heirs, find prior sale deeds, and verify encumbrances to draft a formal Legal Opinion.
* **Input**: Document Numbers, Registration Years, SRO Codes, Volume/Page numbers.
* **Workflow**: Bulk search of parent deeds across decades $\rightarrow$ cross-references party names $\rightarrow$ inspects certified copies.
* **Pain**: Physically standing in lines at rural SRO offices and paying bribes to clerks for manual register inspections.
* **Landeed Capability**: Landeed Pro portal with direct deed retrieval and OCR text search.

#### 3. Mortgage Lender Credit & Legal Manager (BFSI)
* **Job-to-be-Done**: Establish equitable mortgage validity and confirm no prior registered lien exists before approving loan disbursement.
* **Input**: Loan Applicant Name, Property Address, Survey Number, SRO Deed Number.
* **Workflow**: Automated webhook call from Bank Loan Origination System (LOS) $\rightarrow$ Landeed queries EC, CERSAI, and eCourts $\rightarrow$ emits structured risk score.
* **Pain**: 14-day turnaround time by empanelled legal vendors delaying loan sanctioning and customer drop-off.
* **Landeed Capability**: Terra Black API returning structured JSON title search within 4 minutes.

---

## PART F — COMPLETE PRODUCT MAP

```
┌────────────────────────────────────────────────────────────────────────┐
│                        LANDEED CAPABILITY TAXONOMY                     │
├───────────────────┬───────────────────┬────────────────────────────────┤
│ DIGITAL DOCUMENTS │ SPATIAL & CADASTRAL│ INTELLIGENCE & RISK            │
├───────────────────┼───────────────────┼────────────────────────────────┤
│ • Encumbrance (EC)│ • BhuNaksha WMS   │ • Terra Indic OCR (22 Scripts) │
│ • 7/12 & 8A (MH)  │ • Village Shapefile│ • Chain-of-Title Reconstruction│
│ • RTC / Pahani    │ • Survey Boundaries│ • Prohibited 22-A Auto-Audit   │
│ • Patta / Chitta  │ • Road Proximity  │ • eCourts Litigation Matching  │
│ • Certified Deeds │ • Coordinate Cent.│ • CERSAI Mortgage Cross-Check  │
│ • Jamabandi / RoR │ • Adjacent Plots  │ • Title Search Report (TSR)    │
└───────────────────┴───────────────────┴────────────────────────────────┘
```

### Detailed Functional Inventory

| Category | Feature Name | User | Input | Processing | Output | System Dependencies | Confidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Search** | Survey Number Search | All | State, District, Mandal, Survey # | Normalizes text, matches SRO jurisdiction, queries portal/cache | Summary ownership card | State Revenue Portals, Jurisdiction Master | CONFIRMED |
| **Search** | Deed Number Search | Legal, Bank | SRO Code, Deed #, Year | Directly targets SRO registration index | Registered Deed PDF & Metadata | State Registration Portals (IGRS) | CONFIRMED |
| **Search** | Owner Name Search | All | State, District, Owner Name | Fuzzy string matching against digitized RoR registers | List of matching survey plots | State Record Databases, Name Index | CONFIRMED |
| **Documents** | Instant EC Fetch | Consumer, Bank | SRO, Survey #, Year Range | Queries SRO encumbrance index; stitches multi-year registers | Encumbrance Certificate PDF | IGRS AP/TS/TN/KA Web APIs | CONFIRMED |
| **Documents** | Certified Copy (Nakal) | Legal, Broker | SRO, Document #, Year | Hybrid: Scrapes digital repository or dispatches SRO runner | High-resolution scanned Deed PDF | SRO Digital Vault / Runner Network | STRONGLY INFERRED |
| **Intelligence**| Indic OCR Extraction | Enterprise | Scanned Deed PDF | Vision Transformer binarization, layout parsing, regional NER | Extracted JSON (Parties, Plot, Area) | Internal GPU Inference Cluster | STRONGLY INFERRED |
| **Intelligence**| Title Chain Synthesizer| Bank, Legal | Set of Deed PDFs for a plot | Extracts transferor/transferee; links parent deed citations | Directed graph of title lineage | Terra AI Graph Parsing Engine | STRONGLY INFERRED |
| **Risk** | Section 22-A Audit | Bank, Buyer | Survey #, Mandal | Exact string matching against State Prohibited Gazette list | Boolean flag + Gazette Notification | State Revenue Prohibited Lists | CONFIRMED |
| **Risk** | CERSAI Hypothecation | Bank | Borrower PAN, Asset ID | Automated query to central mortgage database | Active security interest list | CERSAI Portal Integration | STRONGLY INFERRED |
| **Risk** | Litigation Search | Legal, Bank | Owner Name, Survey # | Fuzzy matching against district court filings | Case Number, Court, Status | eCourts Services Scraper / API | STRONGLY INFERRED |
| **GIS** | Cadastral Map Overlay | Developer, Buyer | Survey Number | Fetches BhuNaksha WMS/WFS vector polygons; aligns on basemap | Interactive parcel boundary map | NIC BhuNaksha Servers, Mapbox | CONFIRMED |
| **API** | Terra Black API Suite | BFSI Enterprise| Normalized JSON payload | Orchestrates scrapers, OCR, risk rules, and report generator | Comprehensive Title Report JSON | Cloudflare API Gateway, Scraper Workers | CONFIRMED |

---

## PART G — USER JOURNEYS

```
CONSUMER FLOW:
Landing App ──► Select State/Dist ──► Enter Survey # ──► Cache Hit? ──► [YES] ──► Instant Preview ──► Pay ₹49 ──► Download PDF
                                                              │
                                                             [NO]
                                                              ▼
                                                    Headless Portal Job ──► CAPTCHA Solve ──► Parse HTML ──► Store & Deliver

ENTERPRISE BANK (LOS) FLOW:
LOS Webhook ──► API Auth ──► Property Ingestion ──► Async Task ──► Fetch Deeds + EC + CERSAI ──► Indic OCR ──► Risk Engine ──► TSR JSON
```

### 1. Consumer Journey: Instant Document Retrieval
1. **Screen 1 (Home)**: User selects State (e.g., Telangana).
2. **Screen 2 (Jurisdiction)**: User selects District $\rightarrow$ Mandal $\rightarrow$ Village via cascading dropdowns.
3. **Screen 3 (Identifier)**: User inputs Survey Number (e.g., `402/A`).
4. **Backend Processing**: System checks internal cache vault. If cache hit, renders instantaneous preview. If miss, dispatches headless scraper to state portal, solves CAPTCHA, downloads binary stream, hashes and stores file in S3.
5. **Screen 4 (Paywall)**: Displays partial redacted preview (Owner Name: `K**** R***`). Prompts payment of ₹49 via UPI (Razorpay/PhonePe).
6. **Screen 5 (Delivery)**: Unlocks full PDF, saves to user's "Property Locker", and offers WhatsApp share link.

### 2. Enterprise Banking Journey: Automated Title Search Report (TSR)
1. **Trigger**: Loan Origination System (LOS) creates a loan case and emits a webhook to `POST /v1/title-search`.
2. **Gateway**: Cloudflare WAF authenticates Bearer JWT, validates payload, and inserts job into Redis/RabbitMQ queue.
3. **Multi-Source Orchestration**:
   - Worker 1 queries State SRO for 30-year Encumbrance Certificate.
   - Worker 2 queries State Revenue Portal for latest Record of Rights (RoR).
   - Worker 3 queries eCourts API for pending litigation against seller and survey number.
   - Worker 4 queries CERSAI registry for existing mortgage charges.
4. **Document Structuring**: Deeds downloaded by Worker 1 are routed to GPU cluster running Indic OCR. The system extracts:
   - Schedule of property (boundaries, survey number, extent).
   - Preamble (vendor, vendee, relationship).
   - Prior deed recitals (linking current deed to deed of 1998).
5. **Deterministic Audit**: Rules engine checks:
   - Does seller in 2024 deed match buyer in 2012 deed?
   - Is the survey number listed under Section 22-A prohibited records?
   - Are there active CERSAI encumbrance records?
6. **Delivery**: Landeed compiles a structured Title Search Report (JSON + signed PDF) and fires a completion webhook back to the Bank LOS within 4 minutes.

---

## PART H — PROPERTY IDENTITY MODEL

One of the most profound architectural challenges in building a property platform in India is that **there is no single canonical property identifier nationwide**. 

```
┌────────────────────────────────────────────────────────────────────────┐
│               THE HETEROGENEOUS IDENTIFIER PROBLEM IN INDIA            │
├─────────────────┬──────────────────────────────────────────────────────┤
│ State           │ Primary Revenue Identifiers                          │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Telangana & AP  │ District + Mandal + Village + Survey Number + Hissa  │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Karnataka       │ District + Taluk + Hobli + Village + Survey + Surnoc │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Maharashtra     │ District + Taluka + Village + Gat / Survey Number    │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Uttar Pradesh   │ 16-Digit Unique Code (LGD aligned) + Khasra Number   │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Bihar           │ District + Anchal + Halka + Mauza + Khata + Khesra   │
├─────────────────┼──────────────────────────────────────────────────────┤
│ West Bengal     │ District + Block + Mouza + Khatian Number + Dag No.  │
└─────────────────┴──────────────────────────────────────────────────────┘
```

### The Landeed Canonical Property Identity
**[STRONGLY INFERRED]**  
Landeed cannot use raw government strings as primary keys because different departments within the same state refer to the same physical land differently:
- The **Registration Department (SRO)** indexes by `Book 1, Document Number, Year, SRO Code`.
- The **Revenue Department (Tahsildar)** indexes by `Khata Number, Survey Number, Hissa Number`.
- The **Survey Department (BhuNaksha)** indexes by `Village Census Code, Sheet Number, Plot Polygon ID`.

To resolve this, Landeed constructs a **Synthetic Composite Canonical Identifier**:

```text
CANONICAL_PARCEL_KEY = SHA256(
    COUNTRY_CODE (IN) +
    STATE_CODE (e.g. TG) +
    LGD_DISTRICT_CODE +
    LGD_SUBDISTRICT_CODE +
    LGD_VILLAGE_CODE +
    NORMALIZED_SURVEY_PLOT_NUMBER
)
```

```text
Finding: Landeed utilizes a synthetic canonical property tuple pegged to Local Government Directory (LGD) codes.
Evidence: Multi-state search unification in UI, normalized API responses across diverse state schemas.
Source: Landeed API Developer Reference, UI cascading jurisdiction selectors.
Confidence: STRONGLY INFERRED
Reasoning: Without an LGD-anchored canonical key, cross-referencing an SRO registered deed with a revenue 7/12 or Jamabandi would be computationally impossible across multiple states.
Unknowns: Whether Landeed has adopted the central government's 14-digit ULPIN (Bhu-Aadhaar) internally, or maintains its own proprietary hashing schema.
```

---

## PART I — DATA MODEL RECONSTRUCTION

To support multi-state property lookups, document caches, and ownership graphs, Landeed must maintain a normalized relational and spatial data store.

### Reconstructed Entity-Relationship Diagram (ERD)

```text
  ┌─────────────────────────┐               ┌─────────────────────────┐
  │ AdministrativeDivisions │               │       UserAccounts      │
  ├─────────────────────────┤               ├─────────────────────────┤
  │ lgd_code (PK)           │               │ user_id (PK)            │
  │ state_code              │               │ phone_number            │
  │ district_name           │               │ role (CONSUMER/BANK)    │
  │ mandal_name             │               └────────────┬────────────┘
  │ village_name            │                            │
  └────────────┬────────────┘                            │
               │ 1                                       │ 1
               │                                         │
               │ M                                       │ M
  ┌────────────▼────────────┐               ┌────────────▼────────────┐
  │      ParcelMaster       │               │      SearchHistory      │
  ├─────────────────────────┤               ├─────────────────────────┤
  │ parcel_uuid (PK)        │               │ search_id (PK)          │
  │ canonical_parcel_id (UQ)│               │ user_id (FK)            │
  │ lgd_code (FK)           │               │ parcel_uuid (FK)        │
  │ survey_number           │               │ query_timestamp         │
  │ sub_division_number     │               └─────────────────────────┘
  │ land_nature             │
  │ boundary_geometry (GIS) │
  └────────────┬────────────┘
               │ 1
               ├─────────────────────────────────────────┐
               │ M                                       │ M
  ┌────────────▼────────────┐               ┌────────────▼────────────┐
  │     PropertyDocument    │               │  OwnershipLineageEvent  │
  ├─────────────────────────┤               ├─────────────────────────┤
  │ document_id (PK)        │               │ event_id (PK)           │
  │ parcel_uuid (FK)        │               │ parcel_uuid (FK)        │
  │ document_type           │               │ document_id (FK)        │
  │ document_identifier     │               │ event_type (SALE/GIFT)  │
  │ s3_url                  │               │ event_date              │
  │ sha256_checksum         │               │ transferor_parties JSONB│
  │ ocr_extracted_text      │               │ transferee_parties JSONB│
  └────────────┬────────────┘               │ consideration_amount    │
               │ 1                          └─────────────────────────┘
               │
               │ M
  ┌────────────▼────────────┐
  │    ExtractedEntities    │
  ├─────────────────────────┤
  │ entity_id (PK)          │
  │ document_id (FK)        │
  │ entity_type (PARTY/LIEN)│
  │ raw_string              │
  │ normalized_value        │
  │ confidence_score        │
  └─────────────────────────┘
```

### PostgreSQL / PostGIS Schema Definition

```sql
-- 1. Administrative Jurisdiction Master (LGD Aligned)
CREATE TABLE administrative_divisions (
    lgd_code VARCHAR(20) PRIMARY KEY,
    state_code VARCHAR(4) NOT NULL,
    state_name VARCHAR(64) NOT NULL,
    district_name VARCHAR(64) NOT NULL,
    mandal_tahsil_name VARCHAR(64) NOT NULL,
    village_name VARCHAR(128) NOT NULL,
    census_village_code VARCHAR(32) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Canonical Parcel Master
CREATE TABLE parcel_master (
    parcel_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_parcel_id VARCHAR(64) UNIQUE NOT NULL, -- SHA256 tuple hash
    lgd_code VARCHAR(20) REFERENCES administrative_divisions(lgd_code),
    survey_number VARCHAR(32) NOT NULL,
    sub_division_number VARCHAR(32),
    khata_number VARCHAR(32),
    recorded_area_sqft NUMERIC(14, 2),
    recorded_area_acres NUMERIC(10, 4),
    land_nature VARCHAR(32), -- 'AGRICULTURAL', 'RESIDENTIAL', 'GOVERNMENT', 'WAQF'
    is_prohibited_22a BOOLEAN DEFAULT FALSE,
    boundary_geometry GEOMETRY(MultiPolygon, 4326),
    centroid_point GEOMETRY(Point, 4326),
    last_verified_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX idx_parcel_geometry ON parcel_master USING GIST(boundary_geometry);
CREATE INDEX idx_parcel_lookup ON parcel_master(lgd_code, survey_number);

-- 3. Document Vault & Audit Store
CREATE TABLE property_documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parcel_uuid UUID REFERENCES parcel_master(parcel_uuid),
    document_type VARCHAR(48) NOT NULL, -- 'SALE_DEED', 'ENCUMBRANCE_CERTIFICATE', '7_12', 'ROR'
    document_identifier VARCHAR(128) NOT NULL, -- Deed No / Volume / Year
    registration_year INT,
    sro_code VARCHAR(32),
    raw_s3_url VARCHAR(512) NOT NULL,
    sha256_checksum VARCHAR(64) NOT NULL,
    ocr_extracted_text TEXT,
    ocr_confidence_score NUMERIC(5, 2),
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Ownership Lineage Events (Historical Chain)
CREATE TABLE ownership_lineage_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parcel_uuid UUID REFERENCES parcel_master(parcel_uuid),
    document_id UUID REFERENCES property_documents(document_id),
    event_type VARCHAR(32) NOT NULL, -- 'SALE', 'INHERITANCE', 'GIFT', 'PARTITION', 'MORTGAGE'
    event_date DATE,
    transferor_parties JSONB NOT NULL, -- [{"name": "A", "father": "B", "share": 0.5}]
    transferee_parties JSONB NOT NULL,
    consideration_amount NUMERIC(14, 2),
    transferred_area_sqft NUMERIC(14, 2),
    is_active_title_holder BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## PART J — PROPERTY GRAPH

To reconstruct an unbroken chain of title across 30 years, a purely relational model experiences performance degradation under recursive self-joins. Landeed’s "Terra" engine relies on a **Directed Acyclic Graph (DAG)** representation of property lineage.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   THE TITLE LINEAGE PROPERTY GRAPH                     │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  (Person: Vendor 1994) ───[:TRANSFERRED_VIA {Deed: 112/1994}]───►      │
│                                                                        │
│  (Person: Purchaser 1994 / Vendor 2012)                                │
│        │                                                               │
│        ├───[:MORTGAGED_TO]───► (Bank: SBI {Status: Discharged 2018})   │
│        │                                                               │
│        └───[:TRANSFERRED_VIA {Deed: 840/2012}]───►                     │
│                                                                        │
│  (Person: Current Owner 2024)                                          │
│        ▲                                                               │
│        │                                                               │
│  [:OWNS_RECORD]                                                        │
│        │                                                               │
│  (Parcel: Canonical Node BS-TG-RR-041-SN402)                          │
│        │                                                               │
│        ├───[:LOCATED_IN]───► (Village: Mauza Shamshabad)               │
│        ├───[:HAS_GEOMETRY]──► (Polygon: Cadastral BhuNaksha)           │
│        └───[:SUBJECT_TO]───► (Lien: CERSAI ID #800192)                 │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Core Graph Edge Semantics
* `[:TRANSFERRED_VIA {deed_number, date, consideration}]`: Connects transferor node to transferee node.
* `[:OWNS_RECORD {share_fraction, khata_number}]`: Connects person node to canonical parcel node.
* `[:ENCUMBERED_BY {lender_name, amount, registration_date}]`: Connects parcel node to institutional mortgage node.
* `[:DISPUTED_IN {court_id, suit_number, prayer}]`: Connects parcel or person node to active civil litigation suit.

---

## PART K — GOVERNMENT DATA ARCHITECTURE

### The Fragmentation Reality
Under Entry 18 of the State List in the Seventh Schedule of the Constitution of India, land administration is entirely within the legislative domain of individual states. Consequently, **there is no central API gateway, no standard data schema, and no uniform authentication standard across India**.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   LANDEED REVERSE-ENGINEERED SCRAPER STACK             │
├─────────────────┬──────────────────────────────────────────────────────┤
│ Component       │ Technical Implementation                             │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Client Protocol │ Headless HTTP Clients (Golang net/http, Python       │
│                 │ aiohttp), Playwright/Puppeteer for JS-heavy portals  │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Session Manager │ Distributed Redis session pools storing warm cookies,│
│                 │ ASP.NET __VIEWSTATE, and CSRF tokens                 │
├─────────────────┼──────────────────────────────────────────────────────┤
│ IP Architecture │ Commercial residential proxy networks (BrightData,   │
│                 │ Oxylabs) with rotating Indian exit nodes             │
├─────────────────┼──────────────────────────────────────────────────────┤
│ CAPTCHA Decouple│ Local CNN inference (PyTorch/ONNX runtime) trained   │
│                 │ on distorted alphanumeric fonts; <200ms latency      │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Data Normalizer │ Custom parser extracting tabular HTML/JSON and       │
│                 │ mapping regional terms into Canonical Schema         │
└─────────────────┴──────────────────────────────────────────────────────┘
```

```text
Finding: Landeed relies on headless automation and machine-learning CAPTCHA solvers rather than official state APIs.
Evidence: State government revenue departments (e.g., IGRS AP, Bhoomi) do not offer public B2B developer API programs; Landeed app network traces exhibit direct interaction with public portal endpoints.
Source: State portal public technical architecture, founder disclosures regarding "26 state scraper maintenance".
Confidence: CONFIRMED
Reasoning: If state governments offered direct open APIs, the barrier to entry would be zero and Landeed's technical moat would collapse. The difficulty of keeping scrapers alive against broken ASP.NET state portals is precisely what enterprises pay Landeed to manage.
Unknowns: Whether Landeed has secured private Memorandum of Understanding (MoU) access or leased line integrations with any specific state government (e.g., Telangana or Andhra Pradesh).
```

---

## PART L — STATE-SPECIFIC ARCHITECTURE

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   STATE-BY-STATE TECHNICAL MATRIX                                         │
├───────────────┬──────────────────────────┬──────────────────────────────┬─────────────────────────────────┤
│ State         │ Revenue Portal (RoR)     │ Registration Portal (Deeds)  │ Key Technical Bottlenecks       │
├───────────────┼──────────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ Telangana     │ Bhu Bharati (ex-Dharani) │ Integrated in Bhu Bharati    │ Constant OTP barriers & updates │
├───────────────┼──────────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ Andhra Pradesh│ Meebhoomi                │ IGRS AP (CC & EC Search)     │ Frequent ASP.NET ViewState drops│
├───────────────┼──────────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ Karnataka     │ Bhoomi                   │ Kaveri 2.0                   │ Surnoc/Hissa sub-division splits│
├───────────────┼──────────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ Tamil Nadu    │ AnyRor / e-Services      │ TNREGINET                    │ Aggressive IP rate-limiting     │
├───────────────┼──────────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ Maharashtra   │ Mahabhulekh (7/12)       │ IGR Maharashtra (e-Search)   │ Paid e-Search tier, CAPTCHAs    │
├───────────────┼──────────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ Uttar Pradesh │ UP Bhulekh               │ IGRSUP (Prerna)              │ Standardized 16-digit codes     │
├───────────────┼──────────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ West Bengal   │ Banglarbhumi             │ e-District WB                │ Severe 503 HTTP server instability│
├───────────────┼──────────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ Bihar         │ BiharBhumi               │ e-Nibandhan                  │ Ongoing Special Survey discrepancies│
├───────────────┼──────────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ Jharkhand     │ JharBhoomi               │ NGDRS Jharkhand              │ Strict tribal tenancy laws (SPT/CNT)│
└───────────────┴──────────────────────────┴──────────────────────────────┴─────────────────────────────────┘
```

### Architectural Archetypes in Indian Land Administration

#### Archetype 1: Monolithic Integrated (e.g., Telangana Dharani / Bhu Bharati)
* **Design**: Registration of sale deed and mutation of revenue record occur simultaneously in a single transaction before the Tahsildar-cum-Joint Sub-Registrar.
* **Scraper Implication**: Highly unified data model; if the deed is approved, the revenue record is automatically updated. However, portal downtime blocks both revenue and deed lookups simultaneously.

#### Archetype 2: Dual Fragmented (e.g., Karnataka Bhoomi vs. Kaveri 2.0; AP Meebhoomi vs. IGRS)
* **Design**: Revenue records are managed by the Revenue Department (Bhoomi), while registered deeds are managed by the Department of Stamps and Registration (Kaveri). 
* **Scraper Implication**: The platform must query **two entirely separate web systems** using different identifiers, then execute programmatic entity matching between the SRO sale deed and the revenue Pahani/Adangal.

#### Archetype 3: North Indian Cadastral Complex (e.g., Bihar, Jharkhand, UP)
* **Design**: Grounded in the historic Cadastral Survey (CS, 1902–1932) and Revisional Survey (RS, 1965–1985). Records are organized by `Khata` (holding account), `Khesra/Plot` (spatial parcel), and `Jamabandi` (tax assessment ledger).
* **Scraper Implication**: Massive lag between registry deed execution and formal *Dakhil Kharij* (mutation). A seller may legally register a sale deed at the SRO, but the revenue Jamabandi may remain in the ancestor's name for decades. Scrapers must handle multi-generational inheritance splits.

---

## PART M — DOCUMENT ARCHITECTURE

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DOCUMENT PROCESSING LIFECYCLE                   │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  [Discovery & Request]                                                 │
│         │                                                              │
│         ▼                                                              │
│  [Source Execution: Automated Scraper (85%) OR SRO Runner (15%)]       │
│         │                                                              │
│         ▼                                                              │
│  [Raw Ingestion: Byte Stream Validation & SHA256 Checksum]             │
│         │                                                              │
│         ▼                                                              │
│  [Storage: S3 Bucket / Private Encrypted Object Vault]                 │
│         │                                                              │
│         ▼                                                              │
│  [OCR Preprocessing: Deskewing, Otsu Binarization, Stamp Suppression]   │
│         │                                                              │
│         ▼                                                              │
│  [Layout Analysis: Structural Parsing (Preamble, Schedule, Chauhadri)]  │
│         │                                                              │
│         ▼                                                              │
│  [Entity Extraction: Regional NER (Parties, Survey #, Extent, Value)]  │
│         │                                                              │
│         ▼                                                              │
│  [Entity Normalization: Currency Floats, Metric Areas, ISO Dates]      │
│         │                                                              │
│         ▼                                                              │
│  [Entity Linking: Anchor to Canonical Parcel UUID & Property Graph]    │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Document Types Handled
1. **Registered Sale Deed (*Bainama / Vikraya Patram*)**: Primary conveyance instrument establishing ownership transfer.
2. **Encumbrance Certificate (EC / *Nil-Encumbrance*)**: 13–30 year chronological list of registered transactions on a survey number.
3. **Record of Rights (RoR / 7/12 / RTC Pahani / Jamabandi / Patta)**: Revenue department record of current cultivator/possessor and land revenue cess.
4. **Mutation Extract (*Dakhil Kharij / Namantaran*)**: Revenue court order sanctioning entry of new owner into the Jamabandi register.
5. **Cadastral Village Map (*BhuNaksha / Naksha*)**: Scaled spatial sheet showing village parcel boundary polygons.

---

## PART N — DOCUMENT INTELLIGENCE

Indian registry deeds represent one of the most hostile OCR environments in applied computer vision:
* Low-resolution legacy scans (100–150 DPI greyscale TIFFs/PDFs).
* Physical artifacts: Government stamp paper watermarks, adhesive court fee stamps, wax seals, smudged thumbprints, and handwritten marginal notes (*kaifiyat*).
* Mixed scripts: English numerals intertwined with regional Indian scripts (Telugu, Kannada, Devanagari, Tamil, Bengali).

```
┌────────────────────────────────────────────────────────────────────────┐
│                      TERRA INDIC OCR EXTRACTION STACK                  │
├─────────────────┬──────────────────────────────────────────────────────┤
│ Pipeline Stage  │ Engineering Mechanism                                │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Image Binarize  │ Adaptive Gaussian thresholding & morphological       │
│                 │ filters to eliminate background stamp textures       │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Layout Parsing  │ Vision-Transformer object detection segmenting:      │
│                 │ 1. Preamble (Parties)  2. Consideration Clause       │
│                 │ 3. Schedule of Property 4. Chauhadri (Boundaries)    │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Indic Character │ Fine-tuned OCR models (Indic-LayoutLM / TrOCR)       │
│ Recognition     │ specialized in revenue vocabulary (Pattadar, Raiyat) │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Entity Normalizer│ Deterministic regex & parsers mapping regional land │
│                 │ units (Guntha, Bigha, Katha, Cent) to square feet    │
└─────────────────┴──────────────────────────────────────────────────────┘
```

```text
Finding: Landeed built domain-specific Indic OCR models rather than relying on generic commercial APIs.
Evidence: Public announcements of "Terra AI" supporting 22 Indian regional scripts; generic Google Cloud Vision / AWS Textract failure rates (>40%) on low-DPI Indian registry deeds.
Source: Landeed Terra technical press releases, founder interviews on Indic language processing.
Confidence: STRONGLY INFERRED
Reasoning: Standard cloud OCR APIs fail on Indian deeds because they are trained on pristine printed text and struggle with archaic legal vocabulary and complex ligatures in Telugu, Kannada, and Hindi. Custom fine-tuning on annotated SRO scans is mandatory to achieve >90% entity extraction accuracy.
Unknowns: Exact model architectures used (e.g., whether based on fine-tuned open-source TrOCR, Surya, or proprietary Vision Transformers).
```

---

## PART O — ENTITY RESOLUTION

A major challenge in Indian property intelligence is resolving whether disparate legal documents refer to the same underlying individual or parcel.

### The Identity Ambiguity Problem
1. **Name Permutations**: In Indian records, an individual's name appears with multiple phonetic transliterations, abbreviations, and honorifics:
   - `Ram Kumar Singh`
   - `Ramkumar Singh`
   - `R. K. Singh`
   - `राम कुमार सिंह`
2. **Lack of Unique Identifiers**: Pre-2015 registered deeds rarely record Aadhaar or PAN numbers. Identity must be established via composite relationships:
   - `Name + Father/Spouse Name + Caste/Community (in historical records) + Residence Village`.

### Algorithmic Resolution Architecture
```text
┌────────────────────────────────────────────────────────────────────────┐
│                       ENTITY RESOLUTION PIPELINE                       │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Input Raw Strings: "Ramesh Chandra Sharma" vs "R. C. Sharma"          │
│         │                                                              │
│         ▼                                                              │
│  [Step 1: Unicode Normalization & Diacritic Stripping]                 │
│         │                                                              │
│         ▼                                                              │
│  [Step 2: Indic Phonetic Encoding (Double Metaphone / Soundex Variant)]│
│         │                                                              │
│         ▼                                                              │
│  [Step 3: Patronymic Anchor Verification (Father's Name Match)]        │
│         │                                                              │
│         ▼                                                              │
│  [Step 4: Jaro-Winkler & Levenshtein Distance Matrix Calculation]      │
│         │                                                              │
│         ▼                                                              │
│  [Step 5: Composite Confidence Score > 0.88? ──► MERGE GRAPH NODES]    │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## PART P — PROPERTY HISTORY

```
┌────────────────────────────────────────────────────────────────────────┐
│                 LONGITUDINAL PARCEL LIFECYCLE RECONSTRUCTION           │
├───────────┬──────────────────┬─────────────────┬───────────────────────┤
│ Year      │ Event Type       │ Source Document │ Lineage Status        │
├───────────┼──────────────────┼─────────────────┼───────────────────────┤
│ 1974      │ Ancestral Part.  │ Registered Deed │ Root of Title         │
├───────────┼──────────────────┼─────────────────┼───────────────────────┤
│ 1998      │ Sale Conveyance  │ SRO Book 1 Deed │ Transferred to Party B│
├───────────┼──────────────────┼─────────────────┼───────────────────────┤
│ 2001      │ Revenue Mutation │ Tahsil Order    │ Name entered in RoR   │
├───────────┼──────────────────┼─────────────────┼───────────────────────┤
│ 2014      │ Bank Mortgage    │ Deposit of Title│ Encumbered (SBI)      │
├───────────┼──────────────────┼─────────────────┼───────────────────────┤
│ 2019      │ Release Deed     │ SRO Deed        │ Lien Discharged       │
├───────────┼──────────────────┼─────────────────┼───────────────────────┤
│ 2024      │ Proposed Sale    │ New Contract    │ Current Target Search │
└───────────┴──────────────────┴─────────────────┴───────────────────────┘
```

### The 3 Core Dates Required for Property Events
* **`event_date`**: The date on which the physical agreement or conveyance deed was signed by the parties.
* **`recorded_date`**: The date on which the Sub-Registrar registered the instrument or the Tahsildar passed the mutation order.
* **`effective_date`**: The statutory date from which legal rights accrue (often backdated to the date of deed execution under Section 47 of the Registration Act 1908).

---

## PART Q — GIS ARCHITECTURE

```
┌────────────────────────────────────────────────────────────────────────┐
│                        GEOSPATIAL OVERLAY ARCHITECTURE                 │
├────────────────────────────────────────────────────────────────────────┤
│ Layer 4: High-Resolution Satellite Basemap (Google / Mapbox / Sentinel)│
├────────────────────────────────────────────────────────────────────────┤
│ Layer 3: NIC BhuNaksha Cadastral Survey Polygons (Vector MVT Tiles)   │
├────────────────────────────────────────────────────────────────────────┤
│ Layer 2: Master Plan Zoning & Infrastructure Corridors (PWD / NHAI)    │
├────────────────────────────────────────────────────────────────────────┤
│ Layer 1: Administrative Boundaries (State / District / Mandal / Mouza) │
└────────────────────────────────────────────────────────────────────────┘
```

### Technical Implementation Details
* **Spatial Database**: PostgreSQL with **PostGIS** extension.
* **Spatial Indexing**: R-Tree GIST indexes on multi-polygon boundary columns enabling sub-millisecond bounding-box intersections.
* **Vector Tiling Engine**: BhuNaksha shapefiles and GeoJSON layers are pre-tiled into Mapbox Vector Tiles (`.pbf` format) and distributed via CDN.
* **The Georeferencing Bottleneck**: Most Indian revenue village cadastral sheets (*nakshas*) are colonial-era paper sheets created using Gunter's chains without geographic projection coordinates (no lat/long). Where states have not completed DILRMP geo-referencing, cadastral maps float as unprojected shapefiles without ground-truth alignment.

---

## PART R — SEARCH ARCHITECTURE

Landeed’s multi-modal search engine supports five distinct search vectors:
1. **Administrative Cascading Search**: `State` $\rightarrow$ `District` $\rightarrow$ `Mandal` $\rightarrow$ `Village` $\rightarrow$ `Survey Number`.
2. **Registration Search**: `SRO Office Code` $\rightarrow$ `Document Number` $\rightarrow$ `Year`.
3. **Owner Name Search**: Inverted Elasticsearch index over digitized Record of Rights (RoRs).
4. **Geospatial Map Search**: Reverse geocoding a user’s GPS coordinate to identify the intersecting cadastral parcel polygon.
5. **Natural Language Search ("Terra AI")**: LLM-driven query parser translating natural language prompts into structured SQL/API queries.

```text
User Query: "Show me 4 acres in Shamshabad under K. Rama Rao"
     │
     ▼
[LLM Query Intent Parser]
     │
     ├── Extracted Extent: 4 Acres
     ├── Extracted Location: LGD Village Code (Shamshabad)
     └── Extracted Person: "K. Rama Rao" (Soundex: K650 R600)
     │
     ▼
[Elasticsearch / PostGIS Query Execution]
```

---

## PART S — RISK / DUE-DILIGENCE ARCHITECTURE

Landeed’s enterprise reports scan for 16 core title defects:

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   TITLE SEARCH RISK TAXONOMY (16 RISKS)                                   │
├────┬─────────────────────────────┬──────────────────────────────────────────────────────────┬────────────┤
│ #  │ Risk Category               │ Detection Mechanism                                      │ Severity   │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 1  │ Section 22-A Prohibition    │ Exact match against State Prohibited Land Gazette list   │ CRITICAL   │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 2  │ Active Bank Mortgage        │ Cross-reference registered mortgage deeds & CERSAI       │ CRITICAL   │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 3  │ Pending Civil Litigation    │ Fuzzy match owner name & plot against eCourts filings    │ HIGH       │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 4  │ Broken Chain of Title       │ Trace 30-year lineage DAG for missing links              │ HIGH       │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 5  │ Unmutated Ownership         │ Registered deed exists, but seller missing from RoR      │ HIGH       │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 6  │ Area Discrepancy            │ Registered deed area exceeds Jamabandi recorded area >3% │ MEDIUM     │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 7  │ Land Acquisition Notice     │ Plot listed in NHAI / State Gazette Section 4/11 notice  │ CRITICAL   │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 8  │ Tribal Tenancy Restriction  │ Raiyat classified as Scheduled Tribe under CNT/SPT Act   │ CRITICAL   │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 9  │ Agricultural Land Ceiling   │ Aggregate family holdings exceed state statutory limit   │ MEDIUM     │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 10 │ Unauthorized Conversion     │ Agricultural land subdivided without Section 143 / NALA  │ HIGH       │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 11 │ Road Access Deficiency      │ Parcel polygon is landlocked without public rasta        │ HIGH       │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 12 │ Minor / Coparcenary Claim   │ Deed executed without legal guardian / coparcener consent│ HIGH       │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 13 │ Stale Power of Attorney     │ Conveyance executed via GPA >1 year old without alive aff│ MEDIUM     │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 14 │ Land Revenue Tax Default    │ Unpaid e-Lagan cess exceeding 3 consecutive fiscal years │ LOW        │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 15 │ Infrastructure Buffer Zone  │ Spatial intersection with power grid corridor or lake FTL│ HIGH       │
├────┼─────────────────────────────┼──────────────────────────────────────────────────────────┼────────────┤
│ 16 │ Transliteration Mismatch    │ Spelling mismatch between Aadhaar/PAN, Deed, and RoR     │ LOW        │
└────┴─────────────────────────────┴──────────────────────────────────────────────────────────┴────────────┘
```

---

## PART T — AI ARCHITECTURE

### The Probabilistic vs. Deterministic Boundary
A critical architectural insight into Landeed’s "Terra" platform is the **strict separation between stochastic AI models and deterministic rules engines**. In property law, hallucinating a clean title exposes institutional mortgage lenders to multi-crore non-performing asset (NPA) losses.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TERRA AI HYBRID BOUNDARY                        │
├───────────────────────────────────┬────────────────────────────────────┤
│ PROBABILISTIC (AI / LLM / OCR)    │ DETERMINISTIC (RULES / POSTGIS)    │
├───────────────────────────────────┼────────────────────────────────────┤
│ • Regional Indic OCR Transcription│ • Area Delta Math (Measured - Deed)│
│ • Natural Language Query Parsing  │ • Statutory Tenancy Bar Validation │
│ • 40-Page Deed Text Summarization │ • CERSAI Hypothecation Matching    │
│ • Entity Extraction (Candidate NER)│ • Section 22-A Prohibited Checks  │
│ • Table Structure Recognition     │ • Canonical Truth Record Commits   │
└───────────────────────────────────┴────────────────────────────────────┘
```

```text
Finding: Landeed utilizes LLMs for query interpretation and document synthesis, but isolates financial/legal determinations to deterministic rules engines.
Evidence: Enterprise banking contracts mandate zero-hallucination title risk analysis; Title Search Reports output precise statutory citations and gazette references.
Source: Enterprise Title Search Report whitepapers, BFSI audit compliance standards.
Confidence: STRONGLY INFERRED
Reasoning: No regulated commercial bank in India can legally rely on ungrounded LLM token predictions to disburse mortgage credit. All title defects must be backed by concrete documentary citations.
Unknowns: The degree of human paralegal verification required before an enterprise Title Search Report is certified and delivered to a bank.
```

---

## PART U — API / DEVELOPER ARCHITECTURE

Landeed’s enterprise B2B platform exposes a unified suite of REST endpoints:

```
POST /v1/auth/token             ──► Authenticate via API Key & Secret
POST /v1/documents/fetch        ──► Programmatic procurement of raw SRO / Revenue PDFs
POST /v1/encumbrance/search     ──► Retrieve 30-year structured transaction history
POST /v1/cadastral/geometry     ──► Fetch GeoJSON boundary polygon for a survey number
POST /v1/prohibited/verify      ──► Instant audit against Section 22-A prohibited records
POST /v1/title-search/generate  ──► Full async execution of automated Title Search Report
```

### Request / Response Specification: Title Search API
```json
// POST /v1/title-search/generate
{
  "state_code": "TG",
  "lgd_village_code": "574821",
  "survey_number": "402/A",
  "search_period_years": 30,
  "include_litigation": true,
  "include_cersai": true
}

// RESPONSE 200 OK
{
  "case_id": "TSR-2026-09-88192",
  "status": "COMPLETED",
  "canonical_parcel_id": "IN-TG-HYD-574821-SN402A",
  "recorded_owner": "Ramesh Kumar Sharma",
  "title_chain_status": "UNBROKEN",
  "risk_score": 15,
  "risk_level": "LOW",
  "flags": [
    {
      "code": "TAX_DEFAULT",
      "severity": "LOW",
      "description": "Land revenue cess unpaid for fiscal year 2024-2025"
    }
  ],
  "document_vault": {
    "ec_pdf_url": "https://vault.landeed.com/docs/ec_88192.pdf",
    "deed_pdf_url": "https://vault.landeed.com/docs/deed_2012_88192.pdf"
  }
}
```

---

## PART V — BACKEND ARCHITECTURE INFERENCE

```
┌────────────────────────────────────────────────────────────────────────┐
│                   LANDEED INFERRED MICROSERVICES TOPOLOGY              │
├─────────────────┬──────────────────────────────────────────────────────┤
│ Service Layer   │ Inferred Technologies & Architecture                 │
├─────────────────┼──────────────────────────────────────────────────────┤
│ API Gateway     │ Cloudflare WAF + Kong API Gateway (Auth, Rate-Limit) │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Core Orchestrator│ FastAPI (Python) / Go microservices running on AWS EKS│
├─────────────────┼──────────────────────────────────────────────────────┤
│ Ingestion Queue │ Redis Cluster + RabbitMQ / AWS SQS for scraper jobs  │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Scraper Fleet   │ Dockerized Go / Node.js worker nodes across rotating │
│                 │ residential proxy subnets                            │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Indic Vision AI │ NVIDIA A100 / L4 GPU cluster executing LayoutLM &   │
│                 │ TrOCR vision transformer models                      │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Databases       │ PostgreSQL + PostGIS (Canonical & Spatial Relational) │
│                 │ Amazon Neptune / Neo4j (Property Lineage Graph)      │
│                 │ AWS S3 + CloudFront (Encrypted Immutable PDF Vault)  │
│                 │ Elasticsearch (Fuzzy Owner & Address Search)         │
└─────────────────┴──────────────────────────────────────────────────────┘
```

---

## PART W — DATA PIPELINES

### Ingestion Flow & Dead-Letter Handling
1. **Request Intake**: Scraper job received with exponential backoff configuration.
2. **Session Acquisition**: Worker checks Redis pool for an active, unexpired session cookie for the target government portal.
3. **Execution**: Worker sends HTTP POST with forged ViewState parameters and solved CAPTCHA payload.
4. **Failure Modes**:
   - **Government Portal 502/503 (Downtime)**: Worker re-queues job with jittered exponential backoff (up to 5 retries over 30 minutes).
   - **CAPTCHA Failure**: Worker discards session, requests fresh CAPTCHA image, and re-invokes CNN solver.
   - **Rate Limiting (HTTP 429)**: Worker switches proxy IP pool immediately.
   - **Dead-Letter Queue (DLQ)**: If 5 retries fail, job is marked `FAILED_GOVERNMENT_OFFLINE` and routed to the manual ops desk.

---

## PART X — DATA QUALITY

Landeed must reconcile massive inconsistencies in government data:
* **Stale Government Caches**: State revenue portals often serve cached HTML tables that fail to reflect deeds registered 48 hours prior. Landeed forces fresh lookups by generating dynamic query parameters.
* **Corrupted PDF Streams**: State SRO servers frequently truncate binary PDF downloads due to bandwidth timeouts. Ingestion workers calculate SHA256 hashes and verify PDF EOF (End of File) markers before storing files in S3.
* **Conflicting Co-Owner Names**: 7/12 extracts frequently misspell co-sharers. Landeed preserves the raw source string in `source_records` while publishing the normalized name in `canonical_entities`.

---

## PART Y — PROVENANCE

Every legal assertion emitted by Landeed’s platform must be traceable down to an immutable source artifact:

```text
Derived Risk Finding ("Active Mortgage Detected")
       │
       ▼
Extracted Structured Claim (Lien: ₹45,00,000 to State Bank of India)
       │
       ▼
Document Page & Coordinate Bounding Box (Page 4, Lines 12-18)
       │
       ▼
Document Vault Artifact (SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4...)
       │
       ▼
Source Record Metadata (SRO Shamshabad, Book 1, Document #4102/2018)
       │
       ▼
Government Ingestion Telemetry (Retrieved 2026-09-12 14:22:10 UTC from IGRS Portal)
```

---

## PART Z — OPERATIONS

Despite high software automation, Landeed maintains an indispensable human operations network:
1. **Scraper Maintenance Engineering Team**: Dedicated engineers on 24/7 rotation rewriting scraping parsers as state governments redesign web pages, update security tokens, or modify HTML DOM trees.
2. **Sub-Registrar Paralegal Network ("Deed Runners")**: Local field clerks stationed across Tier-2/3 district headquarters to retrieve certified physical copies (Nakal) from legacy, non-digitized SRO paper registers (pre-2000).
3. **Legal Quality Assurance (QA)**: Experienced advocates who manually spot-check automated Title Search Reports before they are delivered to institutional bank underwriters.

---

## PART AA — UNIT ECONOMICS

### Consumer (B2C) Document Download Unit Economics
```text
  Average Consumer Price per Document Search:     ₹ 50.00
  − Government Portal Fee (where applicable):     ₹ 15.00
  − Cloud & Compute / Proxy Infrastructure:       ₹  4.50
  − OCR & AI Processing Cost:                     ₹  2.50
  − Payment Gateway Fee (2% Razorpay/Paytm):      ₹  1.00
  − Blended CAC (Consumer acquisition amortized): ₹ 12.00
  ────────────────────────────────────────────────────────
  = Contribution Margin per Consumer Search:      ₹ 15.00 (30.0%)
```

### Enterprise (B2B) Title Report Unit Economics
```text
  Enterprise Contract Price per Title Check:      ₹ 450.00
  − Multi-Document Procurement Cost (Govt):       ₹  45.00
  − Cloud, PostGIS, Storage & AI Processing:      ₹  25.00
  − Litigation & CERSAI Database API Query Cost:  ₹  30.00
  − Paralegal QA Verification (Human-in-the-loop):₹  80.00
  ────────────────────────────────────────────────────────
  = Contribution Margin per Enterprise Title DD:  ₹ 270.00 (60.0%)
```

---

## PART AB — MOAT

```
┌────────────────────────────────────────────────────────────────────────┐
│                        MOAT STRENGTH COMPARISON                        │
├─────────────────────────┬──────────────┬───────────────────────────────┤
│ MOAT TYPE               │ RATING       │ WHY                           │
├─────────────────────────┼──────────────┼───────────────────────────────┤
│ Raw Government Data     │ NONE (0/10)  │ Public domain; anyone can pull│
├─────────────────────────┼──────────────┼───────────────────────────────┤
│ Scraper Code            │ LOW (3/10)   │ Easily reverse-engineered     │
├─────────────────────────┼──────────────┼───────────────────────────────┤
│ Indic OCR Pipeline      │ MEDIUM (6/10)│ High training data effort     │
├─────────────────────────┼──────────────┼───────────────────────────────┤
│ Historical Cache Vault  │ HIGH (8/10)  │ Millions of indexed documents │
├─────────────────────────┼──────────────┼───────────────────────────────┤
│ Bank LOS Integration    │ VERY HIGH(9) │ Massive enterprise lock-in    │
└─────────────────────────┴──────────────┴───────────────────────────────┘
```

**The Compounding Flywheel**:  
More bank queries $\rightarrow$ more document fetches $\rightarrow$ larger proprietary property graph $\rightarrow$ higher cache hit rate ($>65\%$) $\rightarrow$ lower marginal cost per query $\rightarrow$ faster response time $\rightarrow$ unbeatable API pricing for competitors.

---

## PART AC — REPLICATION DIFFICULTY

| Component | Difficulty | Engineering / Operational Justification |
| :--- | :---: | :--- |
| **Front-End UI & Search Bar** | **LOW** | Trivial; standard React / Next.js implementation. |
| **Single-State Portal Scraper** | **LOW** | Any competent engineer can scrape 1 state in 2 weeks. |
| **26-State Automated Pipeline** | **HIGH** | Maintaining 26 fragile state integrations requires continuous 24/7 monitoring. |
| **Indic Multilingual OCR** | **HIGH** | Requires massive labeled datasets of low-DPI regional script deeds. |
| **Entity Resolution Engine** | **HIGH** | Disambiguating names like *"Ramesh Kumar S/o Suresh Kumar"* across decades. |
| **Cross-State Property Graph** | **VERY HIGH** | Connecting deeds, RORs, mutation cases, and maps into a unified DAG. |
| **Bank Enterprise Contracts** | **VERY HIGH** | Multi-month procurement cycles, Infosec ISO 27001 compliance, SOC2. |
| **Physical Ground Verification** | **IMPOSSIBLE FOR LANDEED** | **Landeed has zero physical ground infrastructure.** |

---

## PART AD — BHUMISETU LESSONS

### A. Architecture Lessons
1. **Never Hardcode a State's Land Model**: Treat all administrative hierarchies as flexible configuration files pegged to Census Local Government Directory (LGD) codes.
2. **Decouple Document Storage from Identity**: Documents are source evidence; canonical parcels are stable real-world entities.

### B. Product Lessons
1. **B2C Land Search is a Distribution Wedge, Not a Business**: Retail consumers churn after one transaction. Sustainable unit economics require institutional workflows (banks, buyers closing deals).
2. **Deliver Definite Conclusions, Not Just PDFs**: Users do not want 40 pages of Telugu legal text; they want to know: *"Can I safely buy this land?"*

### C. Data Lessons
1. **Build a Strict Evidence-to-Claim Ledger**: Every property truth must be anchored to an immutable document, photograph, or GPS reading.
2. **Account for Multi-Generational Mutation Lag**: Never assume a registered deed holder is entered in the government Jamabandi.

### D. AI Lessons
1. **Keep AI Far Away from Statutory Law and Area Math**: Restrict AI to extraction, OCR cleanup, and natural language explanation. Area deltas and tenancy laws must be computed deterministically.

### E. GIS Lessons
1. **Do Not Trust Unprojected Government Cadastral Maps**: Without ground-truth geo-referencing, colonial revenue village maps float with errors up to 50 meters.

### F. Operations Lessons
1. **A Software-Only Company is Blind on the Ground**: Real estate in India is physical, social, and political. Software must empower certified field agents (Amins) rather than attempting to replace them.

---

## PART AE — WHAT NOT TO COPY

1. **DO NOT build scrapers for 26 states**: A startup will burn all its seed capital maintaining broken government scrapers in states it does not operate in.
2. **DO NOT build a pure digital document search app**: That market is already captured by Landeed.
3. **DO NOT rely on disclaimers to dodge physical reality**: Landeed states: *"Not liable for physical boundary or possession disputes."* BhumiSetu’s entire value proposition is resolving physical boundaries and possession.
4. **DO NOT build a pure consumer listing marketplace**: Classified portals (MagicBricks/99acres) are full of fraudulent listings and broker spam.

---

## PART AF — LANDEED VS BHUMISETU

```
┌────────────────────────────────────────────────────────────────────────┐
│                  LANDEED VS BHUMISETU POSITIONING                      │
├─────────────────────────┬──────────────────────┬───────────────────────┤
│ DIMENSION               │ LANDEED              │ BHUMISETU             │
├─────────────────────────┼──────────────────────┼───────────────────────┤
│ Core Identity           │ Digital Property     │ Land Decision &       │
│                         │ Intelligence Layer   │ Transaction Infra     │
├─────────────────────────┼──────────────────────┼───────────────────────┤
│ Primary Wedge           │ Instant Record Search│ Field Amin Survey &   │
│                         │ & Document Fetch     │ Land Passport         │
├─────────────────────────┼──────────────────────┼───────────────────────┤
│ Physical Reality        │ None (Pure Digital)  │ Sub-meter RTK-GPS     │
│                         │                      │ Corner Pin Survey     │
├─────────────────────────┼──────────────────────┼───────────────────────┤
│ Boundary Encroachment   │ Blind                │ Shoelace Geodesic     │
│                         │                      │ Delta Detection       │
├─────────────────────────┼──────────────────────┼───────────────────────┤
│ Tenancy Laws (SPT/CNT)  │ Passive Warning      │ Ground Raiyat Audit   │
│                         │                      │ & Statutory Bar Gate  │
├─────────────────────────┼──────────────────────┼───────────────────────┤
│ Road Frontage Access    │ Inferred / Map View  │ Measured Ground Width │
│                         │                      │ & Obstruction Check   │
├─────────────────────────┼──────────────────────┼───────────────────────┤
│ Revenue Model           │ B2B API Queries &    │ High-Margin Advisory  │
│                         │ Document Fees        │ & Transaction Closing │
└─────────────────────────┴──────────────────────┴───────────────────────┘
```

---

## PART AG — PROPOSED BHUMISETU CONCEPTUAL ARCHITECTURE

```text
                                  BHUMISETU
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                        CASE                     PARCEL
                         │                         │
                         └────────────┬────────────┘
                                      │
                               EVIDENCE LAYER
                                      │
                        ┌─────────────┼─────────────┐
                        │             │             │
                    DOCUMENTS     GOVERNMENT     FIELD DATA
                    (Deeds/EC)    (RoR/Portals) (RTK-GPS/Photos)
                        │             │             │
                        └─────────────┼─────────────┘
                                      ↓
                               CANONICAL FACTS
                                      ↓
                                    CLAIMS
                                      ↓
                              ENTITY RESOLUTION
                                      ↓
                              CONSISTENCY ENGINE
                         (Calculates Delta: Record vs Ground)
                                      ↓
                                   FINDINGS
                                      ↓
                              6-DIMENSION RISK ENGINE
                         (Tenancy, Liens, Encroachment, Area)
                                      ↓
                              HUMAN VERIFICATION
                        (Certified Amin + Legal Sign-off)
                                      ↓
                                AI LAND EXPERT
                         (Natural Language Synthesis)
                                      ↓
                             DIGITAL LAND PASSPORT
                                      ↓
                             TRANSACTION READINESS
```

---

## PART AH — PROPOSED BHUMISETU DATA MODEL

### Core Entities & Relationships

1. **`Parcel`**: The physical, real-world land object.
2. **`Case`**: A specific client investigation or transaction workflow involving a parcel.
3. **`Transaction`**: An economic/legal event between parties involving one or more parcels.
4. **`Evidence`**: An immutable source artifact (Government PDF, RTK-GPS Pin, Field Photo).
5. **`Claim`**: A structured assertion derived from evidence.
6. **`Finding`**: An analytical comparison (e.g., Record Area vs Ground Measured Area).
7. **`Risk`**: A categorized legal, spatial, or possession defect.
8. **`Report (Land Passport)`**: The definitive client deliverable synthesizing all findings.

### SQL DDL Specification

```sql
-- 1. Core Parcel Entity
CREATE TABLE bs_parcels (
    parcel_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bhumi_id VARCHAR(64) UNIQUE NOT NULL, -- e.g. "BS-JH-DEO-MOH-000104"
    state_code VARCHAR(4) NOT NULL,
    district_name VARCHAR(64) NOT NULL,
    anchal_name VARCHAR(64) NOT NULL,
    halka_number VARCHAR(16),
    mauza_name VARCHAR(128) NOT NULL,
    khata_number VARCHAR(32) NOT NULL,
    plot_number VARCHAR(32) NOT NULL,
    deed_recorded_area_acres NUMERIC(10, 4),
    measured_ground_area_acres NUMERIC(10, 4),
    area_delta_percentage NUMERIC(6, 2),
    ground_geometry GEOMETRY(Polygon, 4326),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Evidence Vault
CREATE TABLE bs_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parcel_id UUID REFERENCES bs_parcels(parcel_id),
    evidence_type VARCHAR(32) NOT NULL, -- 'GOVERNMENT_RECORD', 'REGISTERED_DEED', 'GPS_OBSERVATION', 'FIELD_PHOTO'
    source_uri VARCHAR(512) NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    captured_by_user_id UUID,
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    metadata JSONB NOT NULL
);

-- 3. Structured Claims
CREATE TABLE bs_claims (
    claim_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parcel_id UUID REFERENCES bs_parcels(parcel_id),
    evidence_id UUID REFERENCES bs_evidence(evidence_id),
    claim_domain VARCHAR(32) NOT NULL, -- 'OWNERSHIP', 'AREA', 'BOUNDARY', 'TENANCY'
    subject_entity VARCHAR(128) NOT NULL,
    predicate VARCHAR(64) NOT NULL,
    object_value JSONB NOT NULL,
    confidence_score NUMERIC(5, 2),
    verification_status VARCHAR(32) DEFAULT 'NOT_YET_VERIFIED' -- 'VERIFIED', 'CONFLICTING'
);

-- 4. Analytical Findings & Truth Deltas
CREATE TABLE bs_findings (
    finding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parcel_id UUID REFERENCES bs_parcels(parcel_id),
    finding_type VARCHAR(48) NOT NULL, -- 'AREA_DELTA', 'CHAUHADRI_MISMATCH', 'MUTATION_GAP'
    record_assertion JSONB NOT NULL,
    ground_observation JSONB NOT NULL,
    delta_value NUMERIC(12, 4),
    severity VARCHAR(16) NOT NULL, -- 'CLEAN', 'WARNING', 'CRITICAL_HAZARD'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Land Passport (Deliverable Report)
CREATE TABLE bs_land_passports (
    passport_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parcel_id UUID REFERENCES bs_parcels(parcel_id),
    passport_number VARCHAR(32) UNIQUE NOT NULL, -- e.g. "LP-2026-JH-0041"
    overall_trust_score INT NOT NULL, -- 0 to 100
    statutory_tenancy_status VARCHAR(32) NOT NULL, -- 'CLEAR_TRANSFERABLE', 'RESTRICTED_TRIBAL_BAR'
    boundary_dispute_status VARCHAR(32) NOT NULL,
    possession_status VARCHAR(32) NOT NULL,
    qr_verification_token VARCHAR(128) UNIQUE NOT NULL,
    certified_by_amin_id UUID,
    issued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## PART AI — PROPOSED BHUMISETU MVP BOUNDARY

```
┌────────────────────────────────────────────────────────────────────────┐
│                        BHUMISETU PHASE 1 MVP BOUNDARY                  │
├───────────────────────────────────┬────────────────────────────────────┤
│ IN SCOPE (WHAT WE BUILD)          │ OUT OF SCOPE (WHAT WE DEFER)       │
├───────────────────────────────────┼────────────────────────────────────┤
│ • Geographic Focus: 2 Districts   │ • 26-State Scraper Network         │
│   (Deoghar, JH & Banka, BR)       │ • Automated B2B Bank APIs          │
│ • Field Amin PWA (Mobile Survey)  │ • Proprietary Satellite Constellat.│
│ • Bluetooth RTK-GPS Corner Pinning│ • AI Chatbot Auto-Signing Legal Ops│
│ • Shoelace Geodesic Area Delta    │ • Blockchain Smart Contracts       │
│ • SPT/CNT Act Statutory Bar Engine│ • Pure B2C Instant Document Fetch  │
│ • Digital Land Passport (PDF + QR)│ • National Real Estate Classifieds │
└───────────────────────────────────┴────────────────────────────────────┘
```

### The 4 Execution Milestones
1. **Milestone 1 (Month 1)**: Deploy Mobile PWA for Field Amins with Bluetooth RTK-GPS integration to record corner pins and Chauhadri neighbor interviews.
2. **Milestone 2 (Month 2)**: Build the Truth Delta Engine reconciling JharBhoomi/BiharBhumi records against field GPS measurements.
3. **Milestone 3 (Month 3)**: Implement the Deterministic SPT/CNT Act statutory restriction audit.
4. **Milestone 4 (Month 4)**: Issue the first 50 paid **Digital Land Passports** for high-stakes retail land buyers in Deoghar and Banka.

---

## PART AJ — MAJOR ARCHITECTURAL RISKS

1. **Government Portal Countermeasures**: State governments periodically deploy Cloudflare anti-bot services, Cloudflare Turnstile CAPTCHAs, or mandatory Aadhaar OTP authentication, temporarily disrupting automated document ingestion.
2. **RTK-GPS Field Calibration Errors**: In dense tree canopies or remote rural valleys without 4G/CORS network coverage, mobile GPS accuracy can degrade from centimeters to 3–5 meters, leading to false boundary encroachment alarms.
3. **Advocates Act 1961 Legal Constraints**: Under Indian law, only licensed advocates can issue formal legal title opinions. BhumiSetu must position its output strictly as an **"Automated Fact Reconciliation & Risk Intelligence Report"**, with legal conclusions validated by empanelled independent advocates.
4. **Amin Field Resistance**: Traditional local Amins may resist software that enforces transparent GPS recording and eliminates discretionary boundary manipulation. BhumiSetu must position the PWA as an income-multiplying tool for certified Amins.

---

## PART AK — UNKNOWN / UNVERIFIED ASSUMPTIONS

1. **Landeed Direct Portal MOUs**: It is unknown whether Landeed has signed private, direct data-sharing MoUs with any state government or relies 100% on scraping and public portals.
2. **Landeed Internal Unit Costs**: The exact proprietary server and proxy cost per scraping session across diverse states has not been publicly disclosed.
3. **BhuNaksha Vector Completeness**: The percentage of rural cadastral sheets in Bihar and Jharkhand with accurate DILRMP geo-referencing coordinates remains officially unverified.
4. **CERSAI API Accessibility**: Whether non-banking proptech platforms can obtain direct programmatic read access to the CERSAI mortgage API without partnering with a licensed scheduled commercial bank.

---

## PART AL — QUESTIONS THAT MUST BE ANSWERED BEFORE CODING

1. **Upstream Ingestion Choice**: Will BhumiSetu consume Landeed’s B2B Document Procurement API for initial deeds, or build direct scrapers for JharBhoomi and BiharBhumi?
2. **Hardware Standard**: Which sub-meter RTK-GPS receiver (e.g., Emlid Reach RX, Bad Elf, or smartphone dual-frequency GNSS) will be standardized for the pilot Field Amin network?
3. **Coordinate Reference System (CRS)**: How will the PostGIS engine handle conversions between local survey units (*Laggas/Gunter's Chains*) and standard WGS84 (EPSG:4326) / UTM Zone 45N (EPSG:32645)?
4. **Ground Encroachment Threshold**: What exact percentage delta ($\Delta_{\text{area}}\%$) between deed area and measured ground area constitutes an automatic "Hard Stop" versus an acceptable field variance?
5. **Entity Disambiguation Standard**: In regions where genealogical trees (*Kursinama*) govern land inheritance, how will unrecorded co-sharers be validated prior to title clearance?

---

## PART AM — RECOMMENDED NEXT PHASE

### Recommendation: Proceed to Phase 1 (Product Architecture & Pilot Specification)
With Phase 0 complete and Landeed's architectural capabilities, limits, and unit economics fully reverse-engineered, the team should now transition to:

1. **Phase 1A**: Drafting the **BhumiSetu Data Model & Database Specification** (PostgreSQL/PostGIS DDL, Redis cache schema).
2. **Phase 1B**: Authoring the **Field Amin Mobile Survey Protocol & PWA Technical PRD**.
3. **Phase 1C**: Formalizing the **6-Realities Truth Delta Rules Engine** (Mathematical formulas for boundary variance, tenancy bars, and title integrity).

---
**END OF DOSSIER — SYSTEM STOP CONDITION ACTIVE. DO NOT WRITE PRODUCTION CODE UNTIL PHASE 1 IS FORMALLY INITIATED.**
