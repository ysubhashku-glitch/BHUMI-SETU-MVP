# BHUMISETU ARCHITECTURE BLUEPRINT V1
**Document Code:** BS-ARCH-BLUEPRINT-2026-V1  
**Classification:** Core System Architecture Specification & Engineering Blueprint  
**Author:** Principal Product Architect, Property Data Systems Architect, GIS Architect & AI Systems Engineer  
**Date:** September 2026  
**Status:** Canonical Phase 1 Deliverable — Fully Synthesized System Architecture & MVP Data Contract  

---

## A. Executive Architecture

### 1. Product Mission & Architectural Identity
BhumiSetu is an integrated platform for **Digital Land Intelligence, Physical Verification, and Transaction Readiness**. It is engineered to solve the fundamental problem facing land buyers, lenders, and investors in India:
> *"I am considering buying or transacting on this land. Help me understand the available evidence, identify inconsistencies and unknowns, physically verify what matters on the ground, and organize the structured information required for professional and legal review before I commit capital."*

BhumiSetu rejects the "pure digital scraper" paradigm popularized by Landeed and similar aggregators. Land in India cannot be verified solely by querying state web portals or parsing PDFs because:
1. Government records are historically disconnected across registration (deeds), revenue (Jamabandi/RoR), and survey departments (BhuNaksha).
2. Mutation lags often exceed decades, leaving legal titles unrecorded in local revenue records.
3. Boundaries (*aal*), true surface area, physical possession, and statutory tribal/tenancy restrictions (e.g., Santhal Parganas Tenancy Act Section 20, Chota Nagpur Tenancy Act Section 46) exist in physical and social reality, completely invisible to internet bots.

BhumiSetu bridges this gap by decoupling the long-term asset (**The Parcel**) from the operational workflow (**The Property Case**), unified by a deterministic **Claim-and-Evidence Ledger** and audited on the ground by certified field professionals (Amins).

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 THE 18 SYSTEM LAYERS                                   │
├────────────────────┬───────────────────────────────────────────────────────────────────┤
│ Layer              │ Core Responsibility & Architectural Boundary                       │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 1. Identity        │ Tenant, Organization, User, Amin, Advocate, and RBAC enforcement. │
│ 2. Parcel          │ Long-term canonical land object, spatial boundaries, and master key│
│ 3. Case            │ Bounded verification lifecycle, investigation scope, and SLA.     │
│ 4. Evidence        │ Immutable vault of raw source artifacts, field photos, and GPS.   │
│ 5. Source          │ Provenance tracking of government portals, registries, and API runs│
│ 6. Canonical Facts │ Normalized administrative master data (LGD codes, villages, units)│
│ 7. Claim           │ Atomic, attributed assertions derived from evidence (Subject-P-O).│
│ 8. Entity Resol.   │ Deterministic & probabilistic linking of people, plots, and deeds.│
│ 9. Temporal/Event  │ 30+ year longitudinal timeline of conveyances, mutations, and liens│
│ 10. Consistency    │ Deterministic rules engine comparing cross-source discrepancies.   │
│ 11. Finding        │ Structured delta records emitted when claims conflict.            │
│ 12. Risk Engine    │ Severity categorization (Critical to Low) without blackbox scores. │
│ 13. Human Review   │ Legal and operational review gates certifying findings.           │
│ 14. Field Verif.   │ Mobile survey protocol, corner pin GPS capture, and neighbor audit│
│ 15. AI Expert      │ Grounded, read-only RAG assistant answering case-specific queries.│
│ 16. Report Layer   │ Tamper-evident Digital Land Passport synthesizer (PDF + QR).      │
│ 17. Tx Readiness   │ Deterministic checklist gatekeeper for transaction clearance.      │
│ 18. Audit/Proven.  │ Append-only ledger recording all actor changes, edits, and reads. │
└────────────────────┴───────────────────────────────────────────────────────────────────┘
```

---

## B. Product Boundary

### 1. In Scope for BhumiSetu
* **Case-Centric Land Due Diligence**: Commissioning, executing, and delivering verified land assessments.
* **Multi-Source Evidence Aggregation**: Ingestion of uploaded user deeds, digitized khatiyans, online revenue records, and cadastral maps.
* **Sub-Meter Field Survey Protocol**: Capturing RTK-GPS corner pins, boundary ridge (*aal*) alignment, and physical occupation.
* **Deterministic Discrepancy Detection**: Mathematical area deltas, owner spelling mismatches, Chauhadri boundary divergences, and unmutated title gaps.
* **Statutory Tenancy Audits**: Hardcoded statutory restriction gates (SPT Act / CNT Act tribal transfer bars).
* **The Digital Land Passport**: An actionable, insurance-grade verification asset delivered to buyers and lenders.

### 2. Out of Scope (Explicitly Deferred)
* **Open National Property Search**: No broad consumer search engine across 26 states.
* **Property Brokerage / Classified Listings**: No real estate marketplace or advertising.
* **Automated Title Insurance / Legal Guarantees**: BhumiSetu provides structured evidence and risk identification, not legal indemnity.
* **Direct Escrow / Fund Settlement**: No payment holding or fund transfer execution.
* **Direct Autonomous Land Purchases**: No speculative land buying or flipping.

---

## C. Core Domain Objects

The system strictly enforces the following separation of concerns:

```
  PARCEL (Real-world physical land)
    │
    ├── CASE (Operational investigation instance)
    │     │
    │     ├── EVIDENCE (Immutable raw artifacts: PDFs, GPS pins, Photos)
    │     │     │
    │     │     └── CLAIM (Structured assertions: "Owner is Ram Kumar")
    │     │           │
    │     │           └── FINDING (Analytical deltas: "Area short by 12%")
    │     │                 │
    │     │                 └── RISK (Categorized hazard: "Boundary Conflict")
    │     │                       │
    │     │                       └── REVIEW (Human validation by Advocate/Amin)
    │     │                             │
    │     │                             └── REPORT (Digital Land Passport)
    │     │
    └── TRANSACTION (Historical/proposed conveyance involving the parcel)
```

### Definitions & Lifecycle Responsibilities

1. **Parcel**: The enduring physical land entity. Identified canonically via hierarchical geographic keys. Holds authoritative geometry, centroid, and historical relationships. Does *not* store volatile facts directly.
2. **Case**: A billable, stateful operational investigation on a parcel initiated by a user or enterprise client. Governed by a formal state machine from `DRAFT` to `FINAL`.
3. **Transaction**: A legal or economic event (sale, partition, gift, mortgage) transferring rights, either historical (part of chain of title) or prospective (the deal being verified).
4. **Evidence**: An immutable, tamper-evident digital artifact (government Jamabandi extract, registered deed scan, raw EXIF-tagged field photo, RTK-GPS coordinate stream).
5. **Claim**: An atomic, structured assertion derived from evidence. Formatted as `(Subject, Predicate, Object)` with an explicit authority and confidence tier. Competing claims do not overwrite; they coexist.
6. **Finding**: An analytical result generated by the **Consistency Engine** comparing two or more claims (e.g., Registered Area = 2.40 Acres vs. Measured Ground Area = 2.12 Acres $\implies$ Area Shortfall Finding).
7. **Risk**: A finding classified by severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFORMATIONAL`) representing an actionable legal, spatial, or financial defect.
8. **Review**: Formal sign-off by a qualified human professional (Certified Amin, Title Advocate, Ops Lead) validating or overturning findings.
9. **Report (Land Passport)**: The final immutable, compiled presentation artifact summarizing all evidence, findings, and readiness statuses for client consumption.

---

## D. Parcel Architecture

A parcel represents physical ground. It must outlive any individual case, user account, or transaction.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CANONICAL PARCEL MODEL                          │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Canonical Key: IN-JH-DEO-MOH-K104-P542                                │
│  Administrative Hierarchy:                                             │
│    State: Jharkhand (JH)                                               │
│    District: Deoghar (DEO)                                             │
│    Anchal/Block: Mohanpur (MOH)                                        │
│    Halka: 04                                                           │
│    Mauza / Village: Mohanpur (Census LGD: 362910)                      │
│                                                                        │
│  State-Agnostic Identifiers:                                           │
│    primary_identifier: "542" (Plot / Khesra / Survey No)               │
│    secondary_identifier: "104" (Khata / Holding / Patta)               │
│    subdivision_identifier: "A" (Hissa / Surnoc / Bata)                 │
│                                                                        │
│  Spatial Representation:                                               │
│    centroid: POINT(86.7021 24.4832)                                    │
│    authoritative_boundary: MultiPolygon (SRID 4326)                    │
│    recorded_area: 2.40 Acres                                           │
│                                                                        │
│  Decoupled Ownership (Via Claims/Interests):                           │
│    [OwnershipInterest 1] ──► Person: Ramesh Yadav (Share: 50%)         │
│    [OwnershipInterest 2] ──► Person: Suresh Yadav (Share: 50%)         │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Avoiding Derived Truth on the Parcel Entity
To prevent schema corruption and silent overwrites, the `parcels` table **never** stores a plain text `current_owner` or `legal_status` column. Ownership is dynamic, contested, and multi-layered. Instead, ownership is resolved at query time through active, verified `claims` tied to `ownership_interests`.

---

## E. Case Architecture

A case represents a single unit of client work.

```
┌────────────────────────────────────────────────────────────────────────┐
│                          CASE STATE MACHINE                            │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  [DRAFT] ──► [PARCEL_IDENTIFIED] ──► [DOCUMENT_COLLECTION]             │
│                                              │                         │
│  [ANALYSIS] ◄── [PROCESSING & EXTRACTION] ◄──┘                         │
│      │                                                                 │
│      ├──► [VERIFICATION_REQUIRED] ──► [FIELD_VERIFICATION]             │
│      │                                        │                        │
│      └──► [LEGAL_REVIEW] ◄────────────────────┘                        │
│                 │                                                      │
│                 ▼                                                      │
│          [REPORT_DRAFT] ──► [REPORT_REVIEW] ──► [FINAL]                │
│                                                                        │
│  Exceptional States (From any stage):                                  │
│  ──► [BLOCKED] | [DATA_UNAVAILABLE] | [CONFLICTING_DATA] | [CANCELLED] │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### State Transition Invariants
* Transitions must be explicit and validated by the `CaseStateMachine` service.
* A case cannot enter `PROCESSING` without at least one uploaded document or registered identifier.
* A case cannot enter `REPORT_DRAFT` if there are unassigned field verification tasks.
* Transition to `FINAL` freezes the case snapshot and seals the **Digital Land Passport** with a cryptographic SHA-256 hash.

---

## F. Evidence Architecture

All facts in BhumiSetu originate from immutable evidence items.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CASE EVIDENCE LEDGER                            │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Evidence Item: EV-2026-JH-00912                                       │
│  Type: REGISTERED_DOCUMENT                                             │
│  Source URI: s3://bhumisetu-vault-prod/cases/c1/deeds/deed_2018.pdf     │
│  SHA-256: 7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200...│
│  Captured By: User U-104 (Buyer)                                       │
│  Captured At: 2026-09-12 10:14:22 UTC                                  │
│                                                                        │
│  Metadata:                                                             │
│    SRO Office: Mohanpur (Deoghar)                                      │
│    Book: 1, Volume: 42, Deed No: 4122, Year: 2018                      │
│    Pages: 14                                                           │
│                                                                        │
│  Generated Claims:                                                     │
│    CLM-01: Transferor = "Gopal Yadav"                                  │
│    CLM-02: Transferee = "Ramesh Yadav"                                 │
│    CLM-03: Stated Area = 2.40 Acres                                    │
│    CLM-04: Stated North Boundary = "Khesra 541 (Suresh Yadav)"         │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Supported Evidence Classes
1. `GOVERNMENT_RECORD`: Extracts from JharBhoomi, BiharBhumi, or UP Bhulekh.
2. `REGISTERED_DOCUMENT`: Certified copies of Sale, Gift, Partition, or Mortgage deeds.
3. `USER_DOCUMENT`: Private agreements, unprobated wills, tax receipts (*lagan rashid*).
4. `MAP`: Scanned Cadastral Survey (*CS*) or Revisional Survey (*RS*) village sheets.
5. `GIS_RECORD`: NIC BhuNaksha vector polygons or state shapefile layers.
6. `FIELD_PHOTO`: Geotagged high-resolution photos of plot corners, physical boundary ridges, and access roads.
7. `GPS_OBSERVATION`: Raw NMEA/RTK point logs captured via Bluetooth GNSS receivers.
8. `EXPERT_OBSERVATION`: Written field notes and boundary testimony recorded by a licensed Amin.
9. `LEGAL_REVIEW`: Structured analysis submitted by an empanelled title advocate.
10. `AI_DERIVATION`: Candidate entity extractions emitted by vision-language models (strictly uncommitted until validated).

---

## G. Claim Architecture

The **Claim** is the atomic knowledge unit in BhumiSetu. It bridges raw evidence and high-level analytical findings.

```
┌────────────────────────────────────────────────────────────────────────┐
│                         ATOMIC CLAIM STRUCTURE                         │
├─────────────────┬──────────────────────────────────────────────────────┤
│ Field           │ Specification & Example                              │
├─────────────────┼──────────────────────────────────────────────────────┤
│ claim_id        │ UUID v4 (e.g. `clm_88f12a...`)                       │
│ case_id         │ Foreign key to active Case                           │
│ parcel_id       │ Foreign key to Canonical Parcel                      │
│ subject_id      │ Target Entity UUID (e.g. Parcel UUID or Person UUID) │
│ predicate       │ Standardized ontology verb (e.g. `RECORDED_OWNER`)   │
│ object_value    │ JSONB payload: `{"name": "Ram Kumar", "share": 1.0}` │
│ evidence_id     │ Foreign key to backing `Evidence` record             │
│ evidence_span   │ Coordinate bounding box or page: `{"page": 2, ...}`  │
│ authority_tier  │ `STATUTORY_REGISTRY` | `REVENUE_RECORD` | `FIELD_OBS`│
│ confidence      │ Numeric float: `0.95`                                │
│ verification    │ `VERIFIED` | `DISPUTED` | `UNVERIFIED`               │
│ status          │ `ACTIVE` | `SUPERSEDED` | `REJECTED`                 │
└─────────────────┴──────────────────────────────────────────────────────┘
```

### Handling Competing Claims
The system explicitly allows conflicting claims to exist simultaneously. For example:
* **Claim A**: Subject: `Parcel-542`, Predicate: `RECORDED_OWNER`, Object: `Ram Kumar`, Evidence: `Jamabandi Register II (Revenue)`, Authority: `REVENUE_RECORD`.
* **Claim B**: Subject: `Parcel-542`, Predicate: `RECORDED_OWNER`, Object: `Shyam Kumar`, Evidence: `Registered Sale Deed 2021 (SRO)`, Authority: `STATUTORY_REGISTRY`.
* **Claim C**: Subject: `Parcel-542`, Predicate: `PHYSICAL_POSSESSOR`, Object: `Gopal Yadav`, Evidence: `Amin Field Survey`, Authority: `FIELD_OBSERVATION`.

The database retains all three claims. The **Consistency Engine** inspects the conflict, generates an `OWNER_MUTATION_GAP` Finding, and presents the dispute clearly in the Land Passport.

---

## H. Property Event Architecture

Land transactions form a longitudinal sequence across decades. BhumiSetu models property history as an append-only timeline of `PropertyEvent` records.

```
┌────────────────────────────────────────────────────────────────────────┐
│                       PROPERTY EVENT TIMELINE                          │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  1932 (CS Survey) ──► Khesra 542 recorded in Khatiyan under Raiyat A   │
│                             │                                          │
│  1974 (Partition) ──► Registered Partition Deed between Sons B1 & B2   │
│                             │                                          │
│  1998 (Sale Deed) ──► B1 sells 1.20 Acres to Purchaser C (Deed #112)   │
│                             │                                          │
│  2001 (Mutation)  ──► Dakhil Kharij Case #42 approved; Jamabandi open │
│                             │                                          │
│  2018 (Mortgage)  ──► Purchaser C creates equitable mortgage with Bank │
│                             │                                          │
│  2024 (Current)   ──► Proposed conveyance to Client Buyer              │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Event Data Schema Invariants
Every event requires three distinct timestamps:
* `event_date`: When the agreement or conveyance was executed by the parties.
* `recorded_date`: When the public registrar or Tahsildar registered the event.
* `effective_date`: The statutory date from which ownership rights accrue.

Supported event types include: `SALE`, `TRANSFER`, `REGISTRATION`, `MUTATION`, `PARTITION`, `INHERITANCE`, `MORTGAGE`, `RELEASE`, `SUBDIVISION`, `CONSOLIDATION`, `SURVEY`, and `LEGAL_EVENT`.

---

## I. Source Architecture

To guarantee legal auditability, BhumiSetu tracks the exact source origin and parser lifecycle of all ingested information.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SOURCE PROVENANCE MODEL                         │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Source Master: JharBhoomi Revenue Portal                              │
│    authority: "Department of Revenue & Land Reforms, Jharkhand"        │
│    official_url: "https://jharbhoomi.jharkhand.gov.in"                 │
│    source_type: "GOVERNMENT_PORTAL"                                    │
│                                                                        │
│  SourceVersion: v2026.04                                               │
│    parser_signature: "jh_khatiyan_parser_v2.1"                         │
│                                                                        │
│  DataRetrieval Execution:                                              │
│    retrieval_id: "ret_9921b..."                                        │
│    retrieved_at: 2026-09-15 08:30:12 UTC                              │
│    raw_payload_hash: SHA-256 (64 hex characters)                      │
│    http_status: 200                                                    │
│    proxy_ip: "103.xxx.xxx.xxx"                                         │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

This model ensures BhumiSetu can authoritatively answer: *"What exact government payload did we retrieve on September 15, 2026, using what parser, and did the portal content change subsequently?"*

---

## J. Document Architecture

Raw documents are stored immutably in private cloud object storage (S3-compatible). Document processing decomposes files into pages, layout elements, and text spans before claims are generated.

```
┌────────────────────────────────────────────────────────────────────────┐
│                     IMMUTABLE DOCUMENT PIPELINE                        │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  [Raw Document PDF] (Immutable S3 Object; SHA-256 Checksum)            │
│         │                                                              │
│         ▼                                                              │
│  [DocumentPages] (Rendered high-res 300 DPI PNGs per page)             │
│         │                                                              │
│         ▼                                                              │
│  [OCR / Extraction Layer] (Tesseract / Indic Vision Model)             │
│         │                                                              │
│         ▼                                                              │
│  [ExtractedFields] (Tokenized text, bounding boxes: [x0, y0, x1, y1])  │
│         │                                                              │
│         ▼                                                              │
│  [EvidenceSpan] ("Schedule B, Line 14: Khesra No. 542, Extent 2.40 Ac")│
│         │                                                              │
│         ▼                                                              │
│  [Candidate Claim] (Subject: P-542, Predicate: EXTENT, Value: 2.40 Ac) │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

The original PDF is never modified. All OCR text layers, bounding boxes, and translations exist as relational child records referencing parent page numbers.

---

## K. Entity Resolution

Indian land records suffer from pervasive naming variations, transliteration drift between Hindi/Bengali and English, and missing national identity numbers.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   ENTITY RESOLUTION LOGIC & GATES                      │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Candidate String A: "रघुनाथ यादव" (Raghunath Yadav)                   │
│  Candidate String B: "R. N. Yadav, S/o Late Ram Prasad Yadav"          │
│                                                                        │
│  Resolution Pipeline:                                                  │
│    1. Unicode Normalization & Diacritic Stripping                      │
│    2. Indic Transliteration to Canonical Roman Script                  │
│    3. Token Sorting & Honorific Removal ("Late", "Sri", "Pandit")      │
│    4. Patronymic Extraction (Father / Husband anchor match)            │
│    5. Jaro-Winkler & Levenshtein Matrix Scoring                        │
│                                                                        │
│  Classification Output:                                                │
│    • MATCHED: Confidence >= 0.92 + Patronymic / Village Match          │
│    • PROBABLE_MATCH: Confidence 0.80 - 0.91 (Requires Flag)            │
│    • POSSIBLE_MATCH: Confidence 0.65 - 0.79 (Requires Human Review)    │
│    • CONFLICT: Name Match but Explicitly Divergent Father / Address    │
│    • UNMATCHED: Confidence < 0.65                                      │
│                                                                        │
│  CRITICAL INVARIANT: Never silently merge entities. Ambiguous matches  │
│  are presented to the reviewing advocate as a reconciliation task.     │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## L. Consistency Engine

The **Consistency Engine** is a 100% deterministic rules system. It performs rigorous cross-evidence comparisons and produces structured `Finding` objects.

```
┌────────────────────────────────────────────────────────────────────────┐
│                     CONSISTENCY COMPARISON MATRIX                      │
├───────────────────────┬────────────────────────────────────────────────┤
│ Consistency Check     │ Deterministic Rule & Inputs                    │
├───────────────────────┼────────────────────────────────────────────────┤
│ 1. Area Delta         │ Compare Registered Deed Area vs Measured Ground│
│                       │ Area: $\Delta\% = |(A_{\text{ground}} -        │
│                       │ A_{\text{deed}})| / A_{\text{deed}} \times 100$│
├───────────────────────┼────────────────────────────────────────────────┤
│ 2. Owner Discrepancy  │ Compare Deed Transferee vs Jamabandi Raiyat    │
├───────────────────────┼────────────────────────────────────────────────┤
│ 3. Chauhadri Variance │ Compare Deed Boundary Neighbors vs Field Ground│
│                       │ Physical Cultivators on N / S / E / W          │
├───────────────────────┼────────────────────────────────────────────────┤
│ 4. Identifier Match   │ Match Khesra/Khata on Deed vs Online Bhulekh   │
├───────────────────────┼────────────────────────────────────────────────┤
│ 5. Mutation Integrity │ Check if SRO Deed is followed by Dakhil Kharij │
├───────────────────────┼────────────────────────────────────────────────┤
│ 6. Statutory Tenancy  │ Evaluate Caste / Community of Seller against   │
│                       │ SPT Act Section 20 / CNT Act Section 46 bar    │
└───────────────────────┴────────────────────────────────────────────────┘
```

### Finding Object Structure
```json
{
  "finding_id": "fnd_77a192bc",
  "case_id": "cas_10294",
  "parcel_id": "pcl_542",
  "rule_id": "RULE_AREA_DISCREPANCY_DELTA",
  "severity": "CRITICAL",
  "confidence": 0.98,
  "status": "OPEN",
  "observed_values": {
    "deed_recorded_area_acres": 2.40,
    "ground_measured_area_acres": 2.112,
    "variance_percentage": -12.0
  },
  "explanation": "Ground RTK-GPS survey measured 2.112 Acres, revealing a physical deficit of 0.288 Acres (12.0%) compared to the 2.40 Acres stated in registered deed #4122/2018.",
  "recommended_action": "Amin must resurvey the eastern boundary ridge (aal) adjoining Plot 543 to verify suspected encroachment."
}
```

---

## M. Risk Engine

The Risk Engine consumes `Findings` and classifies them into standardized risk tiers. It **does not** emit a single, misleading 0–100 score.

```
┌────────────────────────────────────────────────────────────────────────┐
│                          RISK TAXONOMY MATRIX                          │
├───────────────┬──────────────────────────────────┬─────────────────────┤
│ Severity Tier │ Criteria / Defect Type           │ Legal Implication   │
├───────────────┼──────────────────────────────────┼─────────────────────┤
│ CRITICAL      │ • SPT / CNT Act Tribal Bar       │ Transaction is void │
│               │ • Section 22-A Government Land   │ ab initio; criminal │
│               │ • Physical Deficit > 10%         │ liability / loss of │
│               │ • Active Bank Mortgage Lien      │ entire capital.     │
├───────────────┼──────────────────────────────────┼─────────────────────┤
│ HIGH          │ • Unmutated Sale Deed            │ Seller lacks revenue│
│               │ • Adverse Possessor on Ground    │ title; civil court  │
│               │ • Active Title Suit in eCourts   │ injunction hazard.  │
├───────────────┼──────────────────────────────────┼─────────────────────┤
│ MEDIUM        │ • Physical Deficit 3% – 10%      │ Boundary adjustment │
│               │ • Chauhadri Neighbor Name Drift  │ or price renegoti-  │
│               │ • Stale Power of Attorney (>1 yr)│ ation required.     │
├───────────────┼──────────────────────────────────┼─────────────────────┤
│ LOW           │ • e-Lagan Tax Default (1-2 yrs)  │ Minor compliance;   │
│               │ • Minor Phonetic Spelling Drift  │ rectifiable via fee │
├───────────────┼──────────────────────────────────┼─────────────────────┤
│ INFORMATIONAL │ • Agricultural Land Zone Status  │ Permitted uses and  │
│               │ • Distance to PWD Highway        │ factual background. │
└───────────────┴──────────────────────────────────┴─────────────────────┘
```

Risk Statuses are strictly managed: `OPEN`, `UNDER_REVIEW`, `RESOLVED`, `ACCEPTED` (by client in writing), or `DISMISSED` (by supervising advocate with justification).

---

## N. Human Review Layer

Software detects; humans verify. BhumiSetu establishes two mandatory human validation gates:
1. **Certified Field Amin Gate**: Confirms that GPS survey points match village demarcations (*sehadat / thakbast*), boundary ridges (*aals*) were correctly pinned, and neighbor interviews were conducted in person.
2. **Empanelled Legal Advocate Gate**: Confirms chain of title legality, evaluates succession/heirship risks under personal law, validates statutory tenancy compliance (SPT/CNT), and formally signs the legal section of the Land Passport.

---

## O. Field Verification Layer

Field verification is BhumiSetu’s defining operational advantage. It transforms subjective village impressions into mathematically verifiable spatial evidence.

```
┌────────────────────────────────────────────────────────────────────────┐
│                     FIELD AMIN VERIFICATION WORKFLOW                   │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  [1. Task Dispatch] ──► Case triggers field inspection; Amin assigned  │
│                                │                                       │
│  [2. Preparation]   ──► Amin loads village cadastral map (*Naksha*)    │
│                         and deed Chauhadri on Mobile PWA               │
│                                │                                       │
│  [3. Ground Survey] ──► Bluetooth RTK-GPS receiver pins parcel corners │
│                         (Accuracy: < 0.5 meters)                       │
│                                │                                       │
│  [4. Boundary Audit]──► Photographic proof of all 4 boundary ridges    │
│                         recorded with compass azimuth + EXIF geotags   │
│                                │                                       │
│  [5. Neighbor Test.]──► Recorded audio/notes of physical cultivators   │
│                         on North, South, East, and West boundaries     │
│                                │                                       │
│  [6. PWA Sync]      ──► Encrypted sync to cloud; stored as Evidence    │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## P. GIS Architecture

BhumiSetu uses **PostgreSQL + PostGIS** as its core spatial engine.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SPATIAL GEOMETRY LAYERS                         │
├─────────────────────────┬──────────────────────────────────────────────┤
│ Layer Type              │ Definition & PostGIS Representation          │
├─────────────────────────┼──────────────────────────────────────────────┤
│ Authoritative Geometry  │ Formal government DILRMP digitized vector    │
│                         │ shapefile (EPSG:4326 MultiPolygon)           │
├─────────────────────────┼──────────────────────────────────────────────┤
│ Source Geometry         │ Raw unprojected colonial village map sheet   │
│                         │ vectorization (BhuNaksha CAD/WFS)            │
├─────────────────────────┼──────────────────────────────────────────────┤
│ Derived Geometry        │ Centroid approximations or bounding boxes    │
│                         │ computed from village gazetteers             │
├─────────────────────────┼──────────────────────────────────────────────┤
│ Field-Observed Geometry │ Closed polygon computed from Amin RTK-GPS    │
│                         │ corner pins using geodesic Shoelace math     │
└─────────────────────────┴──────────────────────────────────────────────┘
```

### Critical GIS Invariant
The system **never** marks derived or digitized cadastral map boundaries as authoritative. Cadastral maps in Jharkhand and Bihar are largely unprojected paper scans from 1932. They serve as reference overlays, while the **Field-Observed Geometry** represents physical ground truth.

---

## Q. AI Land Expert

The **BhumiSetu AI Land Expert** is a strictly grounded, read-only intelligence layer.

```
┌────────────────────────────────────────────────────────────────────────┐
│                         AI LAND EXPERT BOUNDARY                        │
├───────────────────────────────────┬────────────────────────────────────┤
│ WHAT THE AI IS PERMITTED TO DO    │ ABSOLUTE ARCHITECTURAL BARS        │
├───────────────────────────────────┼────────────────────────────────────┤
│ • Parse natural language queries  │ • AI CANNOT create or modify       │
│ • Summarize 40-page deed recitals │   canonical parcel records.        │
│ • Point users to specific evidence│ • AI CANNOT resolve or dismiss     │
│ • Explain statutory legal clauses │   findings or risk flags.          │
│ • Draft recommended next actions  │ • AI CANNOT compute area deltas    │
│ • Suggest questions for the Amin  │   or tenancy compliance math.      │
└───────────────────────────────────┴────────────────────────────────────┘
```

### The 6-Point Grounded Response Contract
Every response emitted by the AI assistant must adhere to this structured format:
```text
1. ANSWER: Concise factual response to the user's prompt.
2. EVIDENCE: Specific document title, page number, or GPS pin reference.
3. SOURCE: Official authority (e.g. SRO Mohanpur Deed #4122/2018).
4. CONFIDENCE: Tonal/numeric confidence based on underlying evidence authority.
5. UNCERTAINTY: Explicit declaration of what is NOT known or unverified.
6. NEXT ACTION: Concrete operational recommendation for the buyer, Amin, or advocate.
```

---

## R. Report Engine

The Report Engine compiles the case's evidence, claims, findings, and reviews into the **Digital Land Passport**.

```
┌────────────────────────────────────────────────────────────────────────┐
│                     DIGITAL LAND PASSPORT SECTIONS                     │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Passport Header & Unique Bhumi ID (QR Verification Seal)            │
│ 2. Executive Decision Summary & Transaction Readiness State            │
│ 3. Side-by-Side Reality Matrix: Record vs Ground Truth                 │
│    • Area Comparison: Deed vs Revenue vs RTK-GPS Measured              │
│    • Boundary Audit: Deed Chauhadri vs Ground Possessors               │
│ 4. Statutory Tenancy & Legal Restrictions Audit (SPT/CNT Act Analysis) │
│ 5. Complete 30-Year Longitudinal Chain of Title DAG                    │
│ 6. Cadastral Map & Field GPS Survey Polygon Overlay                    │
│ 7. Itemized Findings & Risk Register (With Mitigations)                │
│ 8. Field Amin Survey Sign-Off (GPS Pins, Photos, Audio Testimonies)    │
│ 9. Title Advocate Legal Certification                                  │
│ 10. Unresolved Discrepancies & Cautionary Disclaimers                  │
│ 11. Complete Evidence Appendix (Citations & SHA-256 Hashes)            │
└────────────────────────────────────────────────────────────────────────┘
```

---

## S. Transaction Readiness

Rather than presenting an arbitrary numerical score (e.g., "78/100 Safe"), BhumiSetu evaluates transaction readiness through an explicit, deterministic checklist:

```
┌────────────────────────────────────────────────────────────────────────┐
│                     TRANSACTION READINESS CHECKLIST                    │
├──────────────────────────────────────────────────────┬─────────────────┤
│ Verification Gate                                    │ Status Required │
├──────────────────────────────────────────────────────┼─────────────────┤
│ 1. Parcel Identity Unambiguously Established         │ PASSED          │
│ 2. Registered Conveyance Deed Ingested & Parsed      │ PASSED          │
│ 3. Online Revenue Record (Jamabandi) Verified        │ PASSED          │
│ 4. Mutation Integrity Check (Deed matches Jamabandi) │ PASSED          │
│ 5. SPT/CNT Act Tribal Tenancy Bar Check              │ PASSED (CLEAR)  │
│ 6. Physical Field Survey by Certified Amin Completed │ PASSED          │
│ 7. Ground Area Variance $\le 5.0\%$                  │ PASSED          │
│ 8. Physical Possession Confirmed Without Adverse Clm│ PASSED          │
│ 9. Zero Open CRITICAL Severity Risks                 │ PASSED          │
│ 10. Empanelled Title Advocate Sign-Off               │ PASSED          │
└──────────────────────────────────────────────────────┴─────────────────┘
```

### Readiness Output States
* `NOT_READY`: Missing core documents, pending field visit, or unverified identity.
* `BLOCKED_CRITICAL_HAZARD`: Statutory tenancy bar detected (e.g., SPT Section 20 tribal land), active court injunction, or fatal title break.
* `REQUIRES_CONDITIONAL_RESOLUTION`: Medium risks exist (e.g., unpaid land cess, 4% area variance) requiring price adjustment or rectification deed.
* `READY_FOR_LEGAL_CLOSING`: All physical and documentary gates passed; clear for transaction execution.

---

## T. Database Architecture (MVP Schema)

The database is built on **PostgreSQL 16 + PostGIS 3.4**. It is a clean, relational schema designed for tenant isolation, auditability, and spatial integrity.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CORE RELATIONAL ERD (MVP)                       │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  organizations ──1:M──► users ──1:M──► cases ──1:1──► parcels          │
│                           │              │               │             │
│                           │              ├──1:M──► case_evidence       │
│                           │              │               │             │
│                           │              ├──1:M──► claims              │
│                           │              │               │             │
│                           │              ├──1:M──► findings            │
│                           │              │               │             │
│                           │              ├──1:M──► field_surveys       │
│                           │              │               │             │
│                           │              └──1:1──► land_passports      │
│                           │                                            │
│                           └─────────────1:M──► audit_logs              │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Complete MVP DDL (PostgreSQL / PostGIS)

```sql
-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- 1. Organizations (Multi-Tenancy)
CREATE TABLE organizations (
    org_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) NOT NULL,
    slug VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Users & Roles
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(org_id),
    full_name VARCHAR(128) NOT NULL,
    email VARCHAR(128) UNIQUE NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    role VARCHAR(32) NOT NULL, -- 'CLIENT', 'FIELD_AMIN', 'LEGAL_REVIEWER', 'ADMIN'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Canonical Parcels
CREATE TABLE parcels (
    parcel_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(org_id),
    bhumi_id VARCHAR(64) UNIQUE NOT NULL, -- 'IN-JH-DEO-MOH-K104-P542'
    state_code VARCHAR(4) NOT NULL,
    district_name VARCHAR(64) NOT NULL,
    anchal_block_name VARCHAR(64) NOT NULL,
    halka_number VARCHAR(16),
    mauza_name VARCHAR(128) NOT NULL,
    census_village_code VARCHAR(32),
    khata_number VARCHAR(32) NOT NULL,
    plot_khesra_number VARCHAR(32) NOT NULL,
    recorded_area_acres NUMERIC(10, 4),
    land_nature VARCHAR(32) DEFAULT 'AGRICULTURAL', -- 'AGRICULTURAL', 'HOMESTEAD', 'GOVERNMENT'
    centroid_point GEOMETRY(Point, 4326),
    authoritative_geometry GEOMETRY(MultiPolygon, 4326),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_parcels_lookup ON parcels(state_code, district_name, anchal_block_name, mauza_name, plot_khesra_number);
CREATE INDEX idx_parcels_geometry ON parcels USING GIST(authoritative_geometry);

-- 4. Cases
CREATE TABLE cases (
    case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(org_id),
    case_number VARCHAR(32) UNIQUE NOT NULL, -- 'CAS-2026-0001'
    parcel_id UUID REFERENCES parcels(parcel_id),
    client_user_id UUID REFERENCES users(user_id),
    assigned_amin_id UUID REFERENCES users(user_id),
    assigned_advocate_id UUID REFERENCES users(user_id),
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    target_transaction_type VARCHAR(32) NOT NULL, -- 'PURCHASE', 'MORTGAGE', 'PARTITION'
    target_price_inr NUMERIC(14, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Case Evidence Ledger
CREATE TABLE case_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(case_id),
    parcel_id UUID REFERENCES parcels(parcel_id),
    evidence_type VARCHAR(32) NOT NULL, -- 'GOVERNMENT_RECORD', 'REGISTERED_DOCUMENT', 'FIELD_PHOTO', 'GPS_OBSERVATION'
    authority_tier VARCHAR(32) NOT NULL, -- 'STATUTORY_REGISTRY', 'REVENUE_RECORD', 'FIELD_OBSERVATION'
    source_name VARCHAR(128) NOT NULL,
    source_uri VARCHAR(512) NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    captured_by_user_id UUID REFERENCES users(user_id),
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Structured Claims
CREATE TABLE claims (
    claim_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(case_id),
    parcel_id UUID REFERENCES parcels(parcel_id),
    evidence_id UUID REFERENCES case_evidence(evidence_id),
    subject_entity_id VARCHAR(64) NOT NULL,
    predicate VARCHAR(64) NOT NULL, -- 'RECORDED_OWNER', 'RECORDED_AREA', 'BOUNDARY_NORTH'
    object_value JSONB NOT NULL,
    authority_tier VARCHAR(32) NOT NULL,
    confidence_score NUMERIC(5, 2) NOT NULL,
    verification_status VARCHAR(32) DEFAULT 'UNVERIFIED', -- 'VERIFIED', 'DISPUTED'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. Analytical Findings & Discrepancies
CREATE TABLE findings (
    finding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(case_id),
    parcel_id UUID REFERENCES parcels(parcel_id),
    rule_id VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL, -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFORMATIONAL'
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN', -- 'OPEN', 'UNDER_REVIEW', 'RESOLVED', 'ACCEPTED'
    observed_values JSONB NOT NULL,
    explanation TEXT NOT NULL,
    recommended_action TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 8. Field Surveys (Amin Ground Inspections)
CREATE TABLE field_surveys (
    survey_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(case_id),
    parcel_id UUID REFERENCES parcels(parcel_id),
    amin_user_id UUID REFERENCES users(user_id),
    gnss_device_model VARCHAR(64),
    measured_area_acres NUMERIC(10, 4) NOT NULL,
    measured_boundary_geometry GEOMETRY(Polygon, 4326) NOT NULL,
    north_ground_neighbor VARCHAR(128),
    south_ground_neighbor VARCHAR(128),
    east_ground_neighbor VARCHAR(128),
    west_ground_neighbor VARCHAR(128),
    road_access_type VARCHAR(32), -- 'PUCCA_ROAD', 'KACHA_RASTA', 'LANDLOCKED'
    road_frontage_feet NUMERIC(8, 2),
    physical_possessor_name VARCHAR(128),
    possession_nature VARCHAR(32), -- 'SELF_CULTIVATION', 'SHARECROPPER', 'ADVERSE_ENCROACHER'
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_surveys_geometry ON field_surveys USING GIST(measured_boundary_geometry);

-- 9. Digital Land Passports (Compiled Deliverable)
CREATE TABLE land_passports (
    passport_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID UNIQUE REFERENCES cases(case_id),
    parcel_id UUID REFERENCES parcels(parcel_id),
    passport_number VARCHAR(32) UNIQUE NOT NULL, -- 'LP-2026-JH-0041'
    readiness_status VARCHAR(32) NOT NULL, -- 'NOT_READY', 'BLOCKED_CRITICAL_HAZARD', 'READY_FOR_LEGAL_CLOSING'
    statutory_tenancy_status VARCHAR(32) NOT NULL, -- 'CLEAR_TRANSFERABLE', 'RESTRICTED_TRIBAL_BAR'
    area_variance_percentage NUMERIC(6, 2),
    sha256_sealed_hash VARCHAR(64) NOT NULL,
    pdf_vault_url VARCHAR(512) NOT NULL,
    issued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 10. Immutable Audit Trail
CREATE TABLE audit_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(org_id),
    actor_user_id UUID REFERENCES users(user_id),
    action VARCHAR(64) NOT NULL, -- 'CASE_STATUS_CHANGED', 'EVIDENCE_INGESTED', 'FINDING_OVERRULED'
    entity_name VARCHAR(32) NOT NULL,
    entity_id UUID NOT NULL,
    previous_state JSONB,
    new_state JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_audit_lookup ON audit_logs(entity_name, entity_id);
```

---

## U. API Architecture (MVP Endpoints)

The API is built using **FastAPI (Python)** adhering to RESTful standards, authenticated via Bearer JWTs, and isolated by organization headers.

```
┌────────────────────────────────────────────────────────────────────────┐
│                            MVP API MATRIX                              │
├───────────────────────────────────┬────────────────────────────────────┤
│ Endpoint                          │ Purpose & Responsibility           │
├───────────────────────────────────┼────────────────────────────────────┤
│ POST   /api/v1/cases              │ Initialize a new investigation case│
│ GET    /api/v1/cases/:id          │ Retrieve full case status & summary│
│ PATCH  /api/v1/cases/:id/status   │ Trigger validated state transition │
├───────────────────────────────────┼────────────────────────────────────┤
│ POST   /api/v1/cases/:id/parcels  │ Link or create canonical parcel    │
├───────────────────────────────────┼────────────────────────────────────┤
│ POST   /api/v1/cases/:id/evidence │ Upload deed / photo / GPS evidence │
│ GET    /api/v1/cases/:id/evidence │ Retrieve full case evidence ledger │
├───────────────────────────────────┼────────────────────────────────────┤
│ GET    /api/v1/cases/:id/claims   │ List atomic structured claims      │
│ GET    /api/v1/cases/:id/findings │ List detected inconsistency findings│
├───────────────────────────────────┼────────────────────────────────────┤
│ POST   /api/v1/cases/:id/surveys  │ Field Amin submits RTK-GPS survey  │
├───────────────────────────────────┼────────────────────────────────────┤
│ POST   /api/v1/cases/:id/reports  │ Compile and seal Land Passport PDF │
│ GET    /api/v1/cases/:id/reports  │ Download signed Land Passport      │
├───────────────────────────────────┼────────────────────────────────────┤
│ POST   /api/v1/cases/:id/ai/query │ Query grounded AI Land Expert      │
└───────────────────────────────────┴────────────────────────────────────┘
```

---

## V. UI Architecture

The frontend is implemented as a **Next.js (React) + TypeScript** single-page application and mobile-responsive Progressive Web App (PWA) styled with Vanilla CSS tokens.

```
┌────────────────────────────────────────────────────────────────────────┐
│                           UI SCREEN TOPOLOGY                           │
├───────────────────┬────────────────────────────────────────────────────┤
│ View              │ Core Purpose & Primary Components                  │
├───────────────────┼────────────────────────────────────────────────────┤
│ 1. Dashboard      │ Active case queue, SLA timers, and status badges.  │
│ 2. Create Case    │ Property identification: District, Block, Mauza,   │
│                   │ Khata, and Plot number intake.                     │
│ 3. Case Workspace │ Central split-pane command center:                 │
│                   │ Left: Evidence & Document Viewer (PDF canvas).     │
│                   │ Center: Reality Comparison Matrix (Record vs Ground)│
│                   │ Right: Findings, Risks & Readiness Checklist.      │
│ 4. Evidence Vault │ Tabular ledger with SHA-256 hashes & download links│
│ 5. Amin Field PWA │ Mobile survey mode: Bluetooth GNSS pairing, GPS pin│
│                   │ capture, photo uploader with EXIF validation.      │
│ 6. Map Studio     │ Mapbox/Leaflet viewer overlaying BhuNaksha cadastral│
│                   │ shapefile with Amin field-surveyed polygon.        │
│ 7. AI Assistant   │ Grounded chat drawer citing case evidence spans.   │
│ 8. Land Passport  │ Tamper-evident, print-ready document preview.      │
└───────────────────┴────────────────────────────────────────────────────┘
```

---

## W. Security & Compliance

1. **Multi-Tenant Isolation**: Every database query is scoped by `org_id`. Cross-tenant data leakage is prohibited at the database query level.
2. **Encrypted Evidence Vault**: Files stored in S3 are encrypted at rest via AES-256. Client browser downloads are authorized strictly via temporary **Pre-Signed URLs** expiring in 15 minutes.
3. **PII Masking**: In compliance with the Digital Personal Data Protection Act (DPDP Act 2023), Aadhaar numbers and private bank details appearing on scanned deeds are automatically redacted before document rendering.
4. **Advocates Act 1961 Compliance**: Software outputs are categorized strictly as **"Technical Due Diligence & Discrepancy Analysis"**. Legal opinions require certified digital sign-off from licensed independent advocates.

---

## X. Auditability & Provenance

Every state modification emits an immutable row into `audit_logs`:
* Who executed the action (`actor_user_id`).
* What entity was modified (`entity_name`, `entity_id`).
* Exactly what changed (`previous_state` vs `new_state` as JSONB diffs).
* Originating IP address and timestamp.

The **Land Passport** is cryptographically sealed with a SHA-256 signature calculated over the entire canonical finding dataset. Any post-issuance tampering renders the verification QR seal invalid.

---

## Y. Data-Moat Architecture

While digital portal scrapers can be copied, **BhumiSetu builds a compounding, defensible physical ground truth moat**:

```
                  THE COMPOUNDING GROUND-TRUTH FLYWHEEL
                  
               [Customer Commissions Land Verification Case]
                                    │
                                    ▼
                 [Field Amin Captures 8 Sub-Meter GPS Pins]
                                    │
                                    ▼
             [Ridge (Aal) Alignment & True Geodesic Polygon Created]
                                    │
                                    ▼
          [Neighbor Cultivators & Adjacent Plot Boundaries Indexed]
                                    │
                                    ▼
       [Permanent High-Precision Ground Node Added to BhumiSetu Graph]
                                    │
                                    ▼
      [Adjacent Future Lookups Resolve Instantly at Zero Field Cost]
```

---

## Z. MVP Boundary

### 1. In Scope for MVP
1. **Target Geography**: Deoghar District (Mohanpur, Sarwan, Devipur Anchal), Jharkhand.
2. **Core Ingestion**: Registered Sale Deeds, Khatiyan extracts, and JharBhoomi online records.
3. **Mobile Field Tool**: PWA for local Amins capturing GPS corner pins and photos.
4. **Deterministic Engine**: Area delta calculations and Santhal Parganas Tenancy (SPT) Act Section 20 tribal protection checks.
5. **Report**: PDF generation of the official **Digital Land Passport** with verification QR code.
6. **Case-Grounded AI**: Read-only assistant answering questions strictly from uploaded case evidence.

---

## AA. Build Now / Next / Later

```
┌────────────────────────────────────────────────────────────────────────┐
│                        BUILD PHASING MATRIX                            │
├─────────────────┬──────────────────────────────────────────────────────┤
│ Horizon         │ Capabilities & Modules                               │
├─────────────────┼──────────────────────────────────────────────────────┤
│ BUILD NOW       │ • Core Postgres/PostGIS Schema (Parcels, Cases,      │
│ (MVP)           │   Evidence, Claims, Findings, Surveys, Passports)    │
│                 │ • FastAPI Backend & Next.js Workspace UI             │
│                 │ • S3 Evidence Vault with Pre-Signed Uploads          │
│                 │ • Amin Field Survey PWA with GPS Pinning             │
│                 │ • Deterministic Consistency & SPT Act Risk Rules     │
│                 │ • Digital Land Passport PDF Generation               │
│                 │ • Grounded AI Land Expert (RAG on Case Documents)    │
├─────────────────┼──────────────────────────────────────────────────────┤
│ BUILD NEXT      │ • Expansion to Banka & Dumka Districts               │
│ (Phase 2)       │ • Automated scrapers for JharBhoomi & BiharBhumi     │
│                 │ • Bluetooth RTK-GNSS hardware auto-sync              │
│                 │ • Cadastral BhuNaksha vector map overlay studio      │
│                 │ • eCourts litigation sync for title disputes         │
├─────────────────┼──────────────────────────────────────────────────────┤
│ BUILD LATER     │ • B2B Enterprise Title Search API for Mortgage Banks │
│ (Phase 3)       │ • Automated Indic OCR Vision Pipeline                │
│                 │ • CERSAI Mortgage Registry Integration               │
│                 │ • Cross-state expansion (Bihar, UP, Maharashtra)     │
├─────────────────┼──────────────────────────────────────────────────────┤
│ DO NOT BUILD    │ • 26-State automated scraper cluster                 │
│                 │ • Consumer property classifieds marketplace          │
│                 │ • Unsupervised AI legal opinion generator            │
│                 │ • Blockchain / Web3 tokenization schemes             │
└─────────────────┴──────────────────────────────────────────────────────┘
```

---

## AB. Architecture Decision Records (ADRs)

### ADR-01: Modular Relational Monolith over Microservices
* **Context**: Need high velocity, strong relational integrity, and simple operations.
* **Decision**: Adopt a modular monolith (FastAPI + PostgreSQL + Next.js).
* **Consequences**: Zero distributed transaction overhead; immediate transactional consistency across Cases, Evidence, and Findings.

### ADR-02: PostgreSQL + PostGIS as Single Source of Truth
* **Context**: System requires relational data integrity alongside spatial parcel polygons.
* **Decision**: Use PostgreSQL with PostGIS extension rather than a separate spatial engine or graph database.
* **Consequences**: Native spatial queries (`ST_Area`, `ST_Intersects`) directly joinable with cases and claims.

### ADR-03: Decoupled Claim & Evidence Model
* **Context**: Government records, deeds, and field surveys frequently present conflicting ownership and area numbers.
* **Decision**: Facts are modeled as atomic, attributed `Claims` referencing raw `Evidence`. Parcels never store derived ownership directly.
* **Consequences**: Full tolerance of conflicting information without schema corruption.

### ADR-04: Strict AI Boundary (Read-Only Assistance)
* **Context**: LLMs can hallucinate legal title and area calculations, creating catastrophic financial liability.
* **Decision**: AI is restricted to summarization, candidate extraction, and grounded Q&A. Canonical database commits require deterministic rules or human approval.
* **Consequences**: Zero risk of AI hallucinating clear property title.

### ADR-05: Deterministic Risk Evaluation over 0–100 Scoring
* **Context**: Single numerical safety scores hide fatal legal risks and create false confidence.
* **Decision**: Categorize findings by explicit severity tiers (`CRITICAL` to `LOW`) and evaluate transaction readiness via a deterministic checklist.
* **Consequences**: Absolute transparency for buyers and institutional lenders.

---

## AC. Risk Register

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ARCHITECTURAL RISK REGISTER                     │
├──────────────────────────────┬──────┬──────┬───────────────────────────┤
│ Risk Description             │ Prob │ Imp  │ Mitigation Strategy       │
├──────────────────────────────┼──────┼──────┼───────────────────────────┤
│ 1. JharBhoomi Downtime       │ HIGH │ MED  │ Asynchronous job queue;   │
│                              │      │      │ manual deed fallback ops. │
├──────────────────────────────┼──────┼──────┼───────────────────────────┤
│ 2. Field GPS Multipath Drift │ MED  │ HIGH │ Enforce HDOP < 1.5 &      │
│    in Remote Rural Valleys   │      │      │ multi-point averaging.    │
├──────────────────────────────┼──────┼──────┼───────────────────────────┤
│ 3. Advocates Act Legal Bar   │ MED  │ HIGH │ Position platform as      │
│                              │      │      │ factual due diligence;    │
│                              │      │      │ advocate sign-off gate.   │
├──────────────────────────────┼──────┼──────┼───────────────────────────┤
│ 4. Amin PWA Adoption Drag    │ MED  │ MED  │ Build offline-first PWA;  │
│                              │      │      │ simple vernacular UI.     │
├──────────────────────────────┼──────┼──────┼───────────────────────────┤
│ 5. Degraded Legacy Scan OCR  │ HIGH │ MED  │ Human-in-the-loop manual  │
│                              │      │      │ extraction fallback.      │
└──────────────────────────────┴──────┴──────┴───────────────────────────┘
```

---

## AD. Unknowns

1. **State BhuNaksha Vector Quality**: The exact proportion of villages in Deoghar Anchal with fully rectified, geo-referenced digital vector shapefiles versus unprojected scanned sheets.
2. **Local CORS Network Availability**: Density of Survey of India Continuously Operating Reference Stations (CORS) in Santhal Pargana for real-time RTK-GPS differential corrections.
3. **CERSAI Third-Party Query Access**: Feasibility of direct non-bank API access to central mortgage registries without an intermediary sponsor bank.

---

## AE. Open Decisions

1. **Standard GNSS Hardware Receiver**: Selecting between commercial sub-meter Bluetooth GNSS receivers (e.g., Emlid Reach RX at ~₹1.8 Lakhs) versus dual-frequency smartphone GNSS for initial pilot Amins.
2. **Upstream Ingestion Partnership**: Choosing between licensing Landeed’s B2B Document API for certified SRO deed downloads versus deploying local SRO document runners in Deoghar.

---

## AF. Recommended Phase 2 Implementation Plan

With the Phase 1 Architecture Blueprint synthesized and approved, the team should execute Phase 2 in four sequential sprints:

1. **Sprint 1 (Weeks 1–2): Core Data Infrastructure & Storage**
   * Initialize PostgreSQL 16 + PostGIS 3.4 database on AWS RDS.
   * Execute DDL migrations for core entities (`parcels`, `cases`, `case_evidence`, `claims`, `findings`).
   * Configure private S3 Evidence Vault with pre-signed upload handlers.
2. **Sprint 2 (Weeks 3–4): Consistency Engine & Field Survey PWA**
   * Implement deterministic area delta and SPT Act Section 20 rules engines in Python.
   * Build Mobile PWA for Field Amins with GPS corner-pin capture and photo EXIF validation.
3. **Sprint 3 (Weeks 5–6): Workspace UI & Document Ingestion**
   * Build Next.js Case Workspace with split-pane PDF viewer and Reality Matrix.
   * Implement document extraction pipeline and claim generation.
4. **Sprint 4 (Weeks 7–8): Report Engine, AI Expert & Pilot Launch**
   * Implement tamper-evident Land Passport PDF compilation with QR verification.
   * Deploy grounded AI Land Expert service.
   * Conduct first 10 end-to-end field due diligence cases in Mohanpur, Deoghar.

---
**END OF BLUEPRINT — SYSTEM STOP CONDITION ACTIVE. PROCEED TO IMPLEMENTATION ONLY UPON FORMAL USER APPROVAL.**
