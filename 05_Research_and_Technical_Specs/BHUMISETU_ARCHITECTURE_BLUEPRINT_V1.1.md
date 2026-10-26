# BHUMISETU ARCHITECTURE BLUEPRINT V1.1
**Document Code:** BS-ARCH-BLUEPRINT-2026-V1.1  
**Classification:** Hardened System Architecture, Red-Team Corrections & Implementation Gate Specification  
**Author:** Principal Product Architect, Property Data Systems Architect, GIS Architect & AI Systems Engineer  
**Date:** September 2026  
**Status:** Approved Pre-Implementation Hardened Specification — Implementation Gate Evaluated  

---

## A. Executive Architecture

### 1. Architectural Mission & Core Stance
BhumiSetu is an enterprise-grade platform for **Digital Land Intelligence, Physical Ground Verification, and Transaction Readiness**.

Its architectural thesis is simple and uncompromising:
> **Documentary evidence, physical ground measurement, and statutory legal validity are three distinct realities in Indian land administration. A software platform must never conflate them, must never overwrite conflicting evidence, and must never present algorithmic deductions as statutory legal title.**

BhumiSetu operates as an unbundled, verifiable truth-engine that answers four separate questions:
1. **"What is observed?"** $\implies$ Raw evidence and verbatim extractions from deeds, khatiyans, Jamabandis, and field observations.
2. **"What is asserted?"** $\implies$ Temporal, attributed claims derived from evidence, coexisting even when in direct conflict.
3. **"What is divergent?"** $\implies$ Deterministic, mathematically calculated findings and rule-based legal discrepancies.
4. **"What must be done next?"** $\implies$ Explicit operational actions assigned to human experts (Amins, title advocates) before transaction clearance.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        DIAGRAM 1: SYSTEM ARCHITECTURE TOPOLOGY                         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│                                  CLIENT CHANNELS                                       │
│          ┌──────────────────────────────┬──────────────────────────────┐               │
│          │  Next.js Case Workspace UI   │   Field Amin Mobile PWA      │               │
│          └──────────────┬───────────────┴──────────────┬───────────────┘               │
│                         │                              │                               │
│                         ▼                              ▼                               │
│  ═══════════════════════════════ CLOUDFLARE API GATEWAY ═════════════════════════════  │
│                   (WAF, DDoS Shield, JWT Auth, Org Scoping, TLS 1.3)                  │
│                                         │                                              │
│                                         ▼                                              │
│  ══════════════════════════ FASTAPI APPLICATION CORE (MODULAR) ═════════════════════  │
│  ┌───────────────────────┬─────────────────────────┬────────────────────────────────┐  │
│  │ Case & Workflow Svc   │ Parcel & Lineage Svc    │ Evidence & Document Svc        │  │
│  ├───────────────────────┼─────────────────────────┼────────────────────────────────┤  │
│  │ Party & Interest Svc  │ Consistency Engine (Det)│ Versioned Legal Rule Engine    │  │
│  ├───────────────────────┼─────────────────────────┼────────────────────────────────┤  │
│  │ Finding & Action Svc  │ Field Survey & GNSS Svc │ Grounded AI Land Expert (RAG)  │  │
│  └───────────────────────┴─────────────────────────┴────────────────────────────────┘  │
│                         │                              │                               │
│                         ▼                              ▼                               │
│  ══════════════════════════ DATA & STORAGE INFRASTRUCTURE ══════════════════════════  │
│  ┌───────────────────────────────────────────┬──────────────────────────────────────┐  │
│  │ PostgreSQL 16 + PostGIS 3.4 Relational    │ AWS S3 / Cloudflare R2 Vault         │  │
│  │ (Parcels, Parties, Cases, Evidence,       │ (Immutable Scans, Raw Geotagged      │  │
│  │  Claims, Findings, Actions, Audit Ledger) │  Photos, NMEA Logs, Sealed Passports)│  │
│  └───────────────────────────────────────────┴──────────────────────────────────────┘  │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## B. Domain Model

### 1. Conceptual Domain Topology
The architecture rejects the flawed linear lifecycle model (`PARCEL -> CASE -> TRANSACTION`). These are distinct, autonomous domain entities with many-to-many relationships.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          DIAGRAM 2: CORE DOMAIN MODEL ERD                              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│    ┌───────────────┐                  ┌───────────────┐                 ┌───────────┐  │
│    │     PARTY     │◄───M:N───────────┤  TRANSACTION  ├──────────M:N───►│  PARCEL   │  │
│    └───────┬───────┘ (Buyer/Seller/   └───────┬───────┘ (Conveyance/    └─────┬─────┘  │
│            │          Raiyat/Witness)         │          Mortgage)            │        │
│            │                                  │                               │        │
│           M:N (OwnershipInterests)           1:M (TransactionCases)          1:M       │
│            │                                  │                               │        │
│            ▼                                  ▼                               ▼        │
│    ┌───────────────┐                  ┌───────────────┐                 ┌───────────┐  │
│    │     CLAIM     │◄───────1:M───────┤     CASE      ├────────M:N─────►│  PARCEL   │  │
│    └───────▲───────┘ (Asserted Facts) └───────┬───────┘ (Investigation) │  VERSION  │  │
│            │                                  │                         └───────────┘  │
│           1:M (Derived From)                 1:M (Scope)                               │
│            │                                  │                                        │
│    ┌───────┴───────┐                  ┌───────┴───────┐                                │
│    │   EVIDENCE    │◄───────M:N───────┤    FINDING    │                                │
│    └───────▲───────┘ (CaseEvidence)   └───────┬───────┘ (Discrepancy)                  │
│            │                                  │                                        │
│           M:N (Attached To)                  1:M (Triggers)                            │
│            │                                  │                                        │
│    ┌───────┴───────┐                  ┌───────▼───────┐                                │
│    │   DOCUMENT    │                  │REQUIRED_ACTION│                                │
│    └───────────────┘                  └───────┬───────┘ (Remediation)                  │
│                                               │                                        │
│                                              1:M (Gated Into)                          │
│                                               │                                        │
│                                       ┌───────▼───────┐                                │
│                                       │   READINESS   │                                │
│                                       └───────────────┘                                │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2. Domain Relationship Cardinalities
* **`Case` $\longleftrightarrow$ `Parcel` (M:N)**: A Case can investigate multiple adjacent Parcels (e.g., a buyer purchasing three plots forming a consolidated farm). A Parcel accumulates multiple Cases over decades (pre-purchase due diligence in 2026, bank mortgage verification in 2028).
* **`Case` $\longleftrightarrow$ `Transaction` (M:N)**: A Case may exist without an active Transaction (e.g., an owner verifying boundaries or updating succession records). A Transaction can span multiple Cases across time.
* **`Transaction` $\longleftrightarrow$ `Parcel` (M:N)**: A Sale Deed or Partition Deed frequently conveys multiple distinct parcels under separate Khatas.
* **`Transaction` $\longleftrightarrow$ `Party` (M:N)**: Multiple transferors, transferees, legal guardians, and witnesses participate in a single transaction.
* **`Parcel` $\longleftrightarrow$ `Party` (M:N)**: Represented via `OwnershipInterest`, accommodating fractional undivided coparcenary co-shares (e.g., 3 heirs each holding an unpartitioned 1/3rd interest).
* **`Evidence` $\longleftrightarrow$ `Case` (M:N)**: Evidence exists independently in the vault. The join entity `CaseEvidence` associates an immutable evidence artifact with multiple operational cases.
* **`Evidence` $\longleftrightarrow$ `Claim` (1:M)**: A single document evidence item yields multiple atomic claims (owner, extent, boundaries, consideration).
* **`Claim` $\longleftrightarrow$ `Finding` (M:N)**: The Consistency Engine compares two or more conflicting claims (or evaluates a claim against a legal rule) to emit a `Finding`.
* **`Finding` $\longleftrightarrow$ `RequiredAction` (1:M)**: A Finding creates one or more actionable tasks (e.g., *"Amin must resurvey East ridge"*).

---

## C. Parcel Architecture

The `Parcel` entity models physical ground. It is canonically anchored to the official Local Government Directory (LGD) structure of India while accommodating heterogeneous historical state identifiers.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          DIAGRAM 3: CANONICAL PARCEL MODEL                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  PARCEL MASTER (Identity & Spatial Reference)                                          │
│  ├── parcel_id: UUID v4 (Immutable internal anchor)                                   │
│  ├── bhumi_id: "IN-JH-DEO-MOH-362910-K104-P542" (Deterministic composite key)         │
│  ├── administrative_hierarchy:                                                         │
│  │   ├── country_code: "IN"                                                            │
│  │   ├── state_code: "JH" (Jharkhand)                                                  │
│  │   ├── district_name: "Deoghar" (LGD: 326)                                           │
│  │   ├── subdistrict_name: "Mohanpur" (LGD: 02148)                                     │
│  │   ├── circle_anchal: "Mohanpur"                                                     │
│  │   ├── halka_number: "04"                                                            │
│  │   └── village_mauza: "Mohanpur" (Census LGD Code: 362910)                           │
│  ├── identifiers:                                                                      │
│  │   ├── primary_identifier: "542" (Plot / Khesra / Survey No / Dag / Gat)             │
│  │   ├── secondary_identifier: "104" (Khata / Holding / Patta / Khatian)               │
│  │   └── subdivision_identifier: "B" (Hissa / Bata / Surnoc / Sub-division)            │
│  ├── spatial_geometries:                                                               │
│  │   ├── centroid: Point(SRID 4326)                                                    │
│  │   └── authoritative_boundary: MultiPolygon(SRID 4326)                               │
│  └── active_version_id: UUID (Pointer to latest ParcelVersion)                         │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## D. Parcel Lineage

Land is continuously subdivided, consolidated, renumbered, and re-surveyed. The architecture implements an append-only relational lineage engine.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        DIAGRAM 4: PARCEL LINEAGE & VERSIONING                          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  1932 (CS Survey)              [Parcel 542 (Original)] - Extent: 4.00 Acres            │
│                                           │                                            │
│  1974 (Partition)              PARCEL_RELATIONSHIP: SUBDIVIDED_TO                      │
│                                ┌──────────┴──────────┐                                 │
│                                ▼                     ▼                                 │
│                    [Parcel 542/1 (2.00 Ac)]    [Parcel 542/2 (2.00 Ac)]                │
│                                │                                                       │
│  2018 (Sale & Mutation)        PARCEL_RELATIONSHIP: SUBDIVIDED_TO                      │
│                                ┌──────────┴──────────┐                                 │
│                                ▼                     ▼                                 │
│                    [Parcel 542/1A (1.20 Ac)]   [Parcel 542/1B (0.80 Ac)]               │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Parcel Lineage Entities
1. **`ParcelVersion`**: Represents a temporal epoch of a parcel's geometry, recorded area, and administrative metadata resulting from a survey or legal mutation.
2. **`ParcelRelationship`**: Stores directed edges between parcels:
   * `SUBDIVIDED_FROM` / `SUBDIVIDED_TO`: Partition of parent into daughter parcels.
   * `MERGED_FROM` / `MERGED_TO`: Consolidation of multiple parcels into one holding.
   * `RENUMBERED_FROM` / `RENUMBERED_TO`: Revisional survey or town-planning renumbering.
   * `CORRECTED_FROM` / `CORRECTED_TO`: Revenue court boundary or clerical area rectification.

---

## E. Case Architecture

A `Case` manages the operational lifecycle of investigating one or more parcels.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        DIAGRAM 5: CASE STATE MACHINE & GATES                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  [DRAFT]                                                                               │
│     │ (Intake: Client details, target parcel identifier)                               │
│     ▼                                                                                  │
│  [PARCEL_IDENTIFIED]                                                                   │
│     │ (Scope fixed: Parcels linked, LGD hierarchy confirmed)                           │
│     ▼                                                                                  │
│  [DOCUMENT_COLLECTION]                                                                 │
│     │ (Uploads: Deeds, Khatiyans, Jamabandis, Tax receipts)                            │
│     ▼                                                                                  │
│  [PROCESSING_AND_EXTRACTION]                                                           │
│     │ (OCR text binarization, field tokenization, candidate claims generated)          │
│     ▼                                                                                  │
│  [CONSISTENCY_ANALYSIS]                                                                │
│     │ (Deterministic rules evaluate discrepancies; Findings emitted)                   │
│     ▼                                                                                  │
│  [FIELD_VERIFICATION_REQUIRED] ──► [FIELD_VERIFICATION_IN_PROGRESS]                    │
│                                           │ (Amin conducts GNSS survey & photo audit)  │
│                                           ▼                                            │
│  [LEGAL_REVIEW] ◄────────────────── [FIELD_VERIFIED]                                   │
│     │ (Advocate reviews title lineage, SPT/CNT statutory bar, and findings)            │
│     ▼                                                                                  │
│  [REPORT_DRAFT] ──► [REPORT_REVIEW] ──► [FINAL] (Passport Sealed with SHA-256)         │
│                                                                                        │
│  EXCEPTIONAL ESCAPE STATES:                                                            │
│  ──► [BLOCKED_HAZARD] (Statutory bar detected; transaction legally void)               │
│  ──► [DATA_UNAVAILABLE] (State servers down / SRO archives burned or destroyed)        │
│  ──► [CANCELLED] (Client abandoned investigation)                                      │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## F. Transaction Architecture

A `Transaction` represents an economic or legal conveyance. It is decoupled from operational cases.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          DIAGRAM 6: TRANSACTION DOMAIN MODEL                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  TRANSACTION MASTER (Tx-2018-04122)                                                    │
│  ├── transaction_type: SALE | PARTITION | GIFT | INHERITANCE | MORTGAGE | LEASE       │
│  ├── execution_date: 2018-04-12                                                        │
│  ├── registration_date: 2018-04-14                                                      │
│  ├── registration_identifier: "Book 1, Volume 42, Deed #4122/2018"                    │
│  ├── registration_sro_code: "SRO-DEO-01" (Mohanpur SRO)                                │
│  ├── stated_consideration_inr: 18,50,000.00                                            │
│  │                                                                                     │
│  ├── INVOLVED PARCELS (M:N):                                                           │
│  │   ├── Parcel A: IN-JH-DEO-MOH-362910-K104-P542 (Transferred Extent: 1.20 Ac)        │
│  │   └── Parcel B: IN-JH-DEO-MOH-362910-K104-P543 (Transferred Extent: 0.80 Ac)        │
│  │                                                                                     │
│  └── PARTICIPATING PARTIES (M:N via TransactionParty):                                 │
│      ├── Party 1: Person "Gopal Yadav" (Role: EXECUTANT / SELLER, Share: 100%)         │
│      ├── Party 2: Person "Ramesh Yadav" (Role: CLAIMANT / BUYER, Share: 100%)          │
│      ├── Party 3: Person "Binod Paswan" (Role: WITNESS)                                │
│      └── Party 4: Person "Madan Jha" (Role: IDENTIFIER)                                │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## G. Party Architecture

Parties are modeled as first-class, independent entities. They are not merely transient strings in entity-resolution tables.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                            DIAGRAM 7: PARTY DOMAIN MODEL                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  PARTY (Abstract Root Entity)                                                          │
│  ├── party_id: UUID v4                                                                 │
│  ├── party_type: PERSON | ORGANIZATION | GOVERNMENT_ENTITY | TRUST | HUF | OTHER       │
│  ├── legal_name: "रघुनाथ यादव" (Primary Script Name)                                   │
│  ├── canonical_transliterated_name: "Raghunath Yadav"                                  │
│  ├── community_caste_category: "GENERAL" | "OBC" | "SC" | "ST" (Crucial for SPT/CNT)   │
│  │                                                                                     │
│  ├── SPECIALIZED PROFILES:                                                             │
│  │   ├── PersonProfile:                                                                │
│  │   │   ├── father_or_husband_name: "Late Ram Prasad Yadav"                           │
│  │   │   ├── relationship_type: "SON_OF" | "WIFE_OF" | "DAUGHTER_OF"                   │
│  │   │   ├── date_of_birth: Date                                                       │
│  │   │   └── is_minor: Boolean                                                         │
│  │   └── OrganizationProfile:                                                          │
│  │       ├── registration_number: "CIN/LLPIN/Society No"                               │
│  │       └── authorized_signatory_id: UUID                                             │
│  │                                                                                     │
│  └── ROLES & INTERESTS:                                                                │
│      ├── OwnershipInterests: (Parcel P-542, Share: 50%, Status: DISPUTED)              │
│      └── TransactionRoles: (Deed #4122, Role: VENDOR)                                  │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## H. Evidence Architecture

Evidence items are autonomous, immutable records stored in an encrypted object vault.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        DIAGRAM 8: DECOUPLED EVIDENCE MODEL                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  EVIDENCE VAULT RECORD (EV-2026-JH-00912)                                              │
│  ├── evidence_id: UUID v4                                                              │
│  ├── evidence_type: GOVERNMENT_RECORD | REGISTERED_DOCUMENT | USER_DOCUMENT |          │
│  │                  MAP | GIS_RECORD | FIELD_PHOTO | GPS_OBSERVATION |                 │
│  │                  EXPERT_OBSERVATION | LEGAL_REVIEW | AI_DERIVATION                  │
│  ├── storage_uri: "s3://bhumisetu-vault/artifacts/2026/09/ev_00912.pdf"                │
│  ├── sha256_checksum: "a4f89b12c..." (Immutable verification hash)                    │
│  ├── captured_at: 2026-09-12 10:14:22 UTC                                              │
│  ├── captured_by_party_id: UUID (Uploader / Surveyor / Officer)                        │
│  │                                                                                     │
│  ├── EVIDENCE RELATIONSHIPS (M:N Cross-Linking):                                       │
│  │   ├── CaseEvidence: Links EV-00912 to Case CAS-001 AND Case CAS-042                 │
│  │   ├── ParcelEvidence: Links EV-00912 directly to Parcel P-542                       │
│  │   └── PartyEvidence: Links EV-00912 to Party "Ramesh Yadav"                         │
│  │                                                                                     │
│  └── CLAIMS GENERATED (1:M):                                                           │
│      ├── Claim 1: "Owner is Ramesh Yadav" (Authority: STATUTORY_REGISTRY)              │
│      └── Claim 2: "Extent is 1.20 Acres" (Authority: STATUTORY_REGISTRY)               │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## I. Claim Architecture & Temporality

Claims represent structured, temporal assertions extracted from evidence.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        DIAGRAM 9: TEMPORAL CLAIM MODEL                                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  CLAIM: CLM-2026-00412                                                                 │
│  ├── subject_id: Parcel P-542                                                          │
│  ├── predicate: RECORDED_OWNER                                                         │
│  ├── object_value: Party "Ramesh Yadav" (JSONB: {"share": 1.0, "nature": "RAIYAT"})   │
│  ├── evidence_id: EV-2026-JH-00912 (Registered Deed #4122/2018)                        │
│  ├── evidence_span: {"page": 3, "bbox": [120, 450, 480, 520]}                         │
│  │                                                                                     │
│  ├── TEMPORAL ANCHORS:                                                                 │
│  │   ├── observed_at: 2026-09-15 08:30:00 UTC (When BhumiSetu ingested the record)    │
│  │   ├── recorded_at: 2018-04-14 11:20:00 UTC (When SRO registered the instrument)     │
│  │   ├── effective_from: 2018-04-12 (Date of deed execution under Sec 47 Reg Act)     │
│  │   └── effective_to: NULL (Still actively asserted by this evidence)                 │
│  │                                                                                     │
│  └── EPISTEMIC METRICS:                                                                │
│      ├── authority_tier: STATUTORY_REGISTRY (High statutory standing)                  │
│      ├── extraction_confidence: 0.96 (High OCR token confidence)                       │
│      └── status: ACTIVE (Not superseded by newer deed)                                 │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Competing Claims Coexistence
The system guarantees that conflicting historical and administrative claims are stored concurrently. A revenue claim from Jamabandi Register II asserting `Owner = Gopal Yadav (1974)` exists side-by-side with a registration claim asserting `Owner = Ramesh Yadav (2018)`. The Consistency Engine flags the delta as an `UNMUTATED_DEED_GAP` without overwriting historical revenue data.

---

## J. Property Event Architecture

`PropertyEvent` records model the longitudinal lifecycle of conveyances, mutations, liens, and court decrees.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     DIAGRAM 10: PROPERTY EVENT CHRONOLOGY                              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  Event 1: CS SURVEY SETTLEMENT (1932-02-14)                                            │
│  ├── Event Date: 1932-02-14 | Recorded Date: 1932-03-01 | Effective Date: 1932-02-14  │
│  └── Parties: British Crown ──► Raiyat A (Khatian #104)                                │
│                                                                                        │
│  Event 2: ANCESTRAL PARTITION (1974-06-11)                                             │
│  ├── Event Date: 1974-06-11 | Recorded Date: 1974-06-15                                │
│  └── Parties: Raiyat A Heirs ──► Co-sharer B1 & Co-sharer B2                            │
│                                                                                        │
│  Event 3: REGISTERED SALE CONVEYANCE (2018-04-12)                                      │
│  ├── Event Date: 2018-04-12 | Recorded Date: 2018-04-14                                │
│  └── Parties: Co-sharer B1 ──► Buyer C (Deed #4122)                                    │
│                                                                                        │
│  Event 4: REVENUE MUTATION ATTEMPT (2019-08-20)                                        │
│  ├── Event Date: 2019-08-20 | Status: REJECTED_BY_TAHSILDAR (Lacks NOC)                 │
│  └── Implication: Title legally transferred; revenue record unmutated.                 │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## K. Source Architecture & Provenance Pipeline

Every extracted fact is anchored through an unbroken provenance chain down to the exact optical bounding box and web retrieval execution.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                  DIAGRAM 11: SOURCE PROVENANCE PIPELINE                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  SOURCE ENTITY (JharBhoomi Revenue Web Portal)                                         │
│    │                                                                                   │
│    ▼                                                                                   │
│  DATA RETRIEVAL EVENT                                                                  │
│  ├── retrieval_id: "ret_9921b01"                                                       │
│  ├── timestamp: 2026-09-12 14:10:02 UTC                                                │
│  ├── raw_content_hash: SHA-256 (64 hex characters)                                     │
│  └── parser_version: "jh_khatiyan_parser_v2.1"                                         │
│    │                                                                                   │
│    ▼                                                                                   │
│  DOCUMENT VAULT ARTIFACT (PDF / Scanned TIFF)                                          │
│    │                                                                                   │
│    ▼                                                                                   │
│  DOCUMENT PAGE (Page 3, 300 DPI Render)                                                │
│    │                                                                                   │
│    ▼                                                                                   │
│  EVIDENCE SPAN (Bounding Box: [x0: 140, y0: 820, x1: 520, y1: 860])                    │
│    │                                                                                   │
│    ▼                                                                                   │
│  STRUCTURED CLAIM (Subject: P-542, Predicate: AREA, Value: 1.20 Acres)                 │
│    │                                                                                   │
│    ▼                                                                                   │
│  ANALYTICAL FINDING (Area Discrepancy: Measured Ground Area is 1.08 Acres)             │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## L. Document Architecture

Original documents uploaded by users or retrieved from government repositories are immutable.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        DIAGRAM 12: DOCUMENT PROCESSING STACK                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  [Incoming Binary PDF Stream]                                                          │
│         │                                                                              │
│         ▼                                                                              │
│  [SHA-256 Hashing & Magic Byte Verification] ──► Fails? ──► [REJECT_CORRUPT]           │
│         │                                                                              │
│         ▼ (Pass)                                                                       │
│  [S3 Private Storage: AES-256 Encryption at Rest]                                      │
│         │                                                                              │
│         ▼                                                                              │
│  [Document Decomposition: Multi-page PDF to 300 DPI PNG Canvas]                        │
│         │                                                                              │
│         ▼                                                                              │
│  [OCR Preprocessing: Deskewing, Contrast Normalization, Otsu Binarization]             │
│         │                                                                              │
│         ▼                                                                              │
│  [Vision Transformer Extraction: Layout Analysis & Table Segmentation]                 │
│         │                                                                              │
│         ▼                                                                              │
│  [Tokenized Field Extraction with Bounding Boxes]                                      │
│         │                                                                              │
│         ▼                                                                              │
│  [EvidenceSpan Linking & Candidate Claim Generation]                                   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## M. Entity Resolution

Entity resolution reconciles party names across diverse historical scripts and spellings without silent data destruction.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     DIAGRAM 13: ENTITY RESOLUTION PIPELINE                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  Incoming Document Name: "Ramesh Chandra Sharma"                                       │
│  Existing Master Party:  "R. C. Sharma, S/o Late K. L. Sharma"                         │
│         │                                                                              │
│         ▼                                                                              │
│  [Step 1: Unicode Normalization & Diacritic Stripping]                                 │
│         │                                                                              │
│         ▼                                                                              │
│  [Step 2: Indic Phonetic Encoding (Double Metaphone / Soundex Variant)]                │
│         │                                                                              │
│         ▼                                                                              │
│  [Step 3: Patronymic Anchor Verification (Father's Name Comparison)]                   │
│         │                                                                              │
│         ▼                                                                              │
│  [Step 4: Composite Scoring (Jaro-Winkler + Address + Patronymic)]                     │
│         │                                                                              │
│         ├── Score >= 0.92 + Patronymic Match ──► [MATCHED: Linked to Party UUID]        │
│         ├── Score 0.80 - 0.91               ──► [PROBABLE_MATCH: Soft Flag]            │
│         ├── Score 0.65 - 0.79               ──► [POSSIBLE_MATCH: Task for Advocate]    │
│         ├── Conflicting Father / Residence  ──► [CONFLICT: Hard Entity Discrepancy]    │
│         └── Score < 0.65                    ──► [UNMATCHED: Create New Party Record]   │
│                                                                                        │
│  MANDATORY INVARIANT: Never silently merge uncertain parties. Ambiguities trigger a    │
│  human review action.                                                                  │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## N. Consistency Engine

The Consistency Engine is a deterministic comparator that executes automated reconciliation rules across coexisting claims.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   DIAGRAM 14: DETERMINISTIC CONSISTENCY ENGINE                         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  INPUT: Active Claims for Parcel P-542                                                 │
│    ├── Claim A (Deed 2018): Area = 2.40 Acres                                          │
│    ├── Claim B (Field GNSS): Measured Area = 2.112 Acres                               │
│    ├── Claim C (Deed 2018): North Boundary = "Suresh Yadav (Plot 541)"                 │
│    └── Claim D (Field Visit): North Cultivator = "Manoj Singh (Unrecorded Tenant)"     │
│                                                                                        │
│  DETERMINISTIC EVALUATION RULES:                                                       │
│    ├── Rule 1 (Area Delta): |2.112 - 2.40| / 2.40 = 12.0% variance (>5.0% threshold)   │
│    │     └── EMITS: Finding FND-001 (Severity: CRITICAL, Type: AREA_DISCREPANCY)       │
│    │                                                                                   │
│    └── Rule 2 (Chauhadri Neighbor Audit): "Suresh Yadav" != "Manoj Singh"              │
│          └── EMITS: Finding FND-002 (Severity: HIGH, Type: BOUNDARY_POSSESSION_CONFLICT)│
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## O. Finding / Action / Resolution Workflow

Findings must never exist as dead-end alerts. Every finding enters a managed remediation workflow.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                DIAGRAM 15: FINDING TO RESOLUTION WORKFLOW                              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  FINDING DETECTED                                                                      │
│  (FND-001: 12.0% Measured Area Shortfall on Parcel P-542)                              │
│         │                                                                              │
│         ▼                                                                              │
│  AUTOMATIC TASK GENERATION (RequiredAction ACT-042)                                    │
│  ├── Action Type: FIELD_RESURVEY_BOUNDARY_RIDGE                                        │
│  ├── Assigned Role: FIELD_AMIN (Assigned to: Amin U-104)                               │
│  ├── Status: OPEN ──► IN_PROGRESS                                                      │
│  │                                                                                     │
│  ▼ (Amin conducts targeted field inspection on East boundary ridge)                    │
│  NEW EVIDENCE ATTACHED                                                                 │
│  (EV-00940: Geotagged Photo of Encroached Ridge + Adjoining Cultivator Statement)      │
│         │                                                                              │
│         ▼                                                                              │
│  RESOLUTION EVALUATION BY LEGAL ADVOCATE:                                              │
│  ├── RESOLVED: Encroachment confirmed; buyer renegotiates deed extent to 2.112 Ac.     │
│  ├── ACCEPTED_WITH_REVIEW: Buyer acknowledges 0.288 Ac loss in writing; proceeds.      │
│  └── BLOCKED: Seller refuses boundary rectification; case halts.                       │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## P. Risk Engine

The Risk Engine consumes `Findings` and structures them into actionable risk categories. It **does not** emit a single, opaque numerical risk score (e.g. "82/100 Safe").

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             DIAGRAM 16: RISK TAXONOMY                                  │
├───────────────┬──────────────────────────────────┬─────────────────────────────────────┤
│ Severity Tier │ Trigger Condition / Defect Type  │ Required Remediation                │
├───────────────┼──────────────────────────────────┼─────────────────────────────────────┤
│ CRITICAL      │ • SPT Act Section 20 Tribal Bar  │ Immediate transaction abort. Sale   │
│               │ • Section 22-A Government Land   │ is void ab initio under state law.  │
│               │ • Ground Area Deficit > 10.0%    │ Criminal & financial loss hazard.   │
│               │ • Active Undischarged Mortgage   │                                     │
├───────────────┼──────────────────────────────────┼─────────────────────────────────────┤
│ HIGH          │ • Unmutated Registered Deed      │ Mandatory Dakhil Kharij mutation    │
│               │ • Adverse Physical Possessor     │ or seller indemnity bond required   │
│               │ • Pending Title Suit in eCourts  │ prior to financial closing.         │
├───────────────┼──────────────────────────────────┼─────────────────────────────────────┤
│ MEDIUM        │ • Ground Area Deficit 3.0%–10.0% │ Price adjustment per square foot or │
│               │ • Chauhadri Neighbor Name Drift  │ boundary monument rectification     │
│               │ • GPA Executed > 1 Year Prior    │ affidavit required from seller.     │
├───────────────┼──────────────────────────────────┼─────────────────────────────────────┤
│ LOW           │ • Unpaid Land Cess (1-2 Years)   │ Clear e-Lagan arrears at Anchal     │
│               │ • Minor Phonetic Transliteration │ revenue counter prior to registry.  │
├───────────────┼──────────────────────────────────┼─────────────────────────────────────┤
│ INFORMATIONAL │ • Land Classified as Agricultural│ Informational disclosure regarding  │
│               │ • PWD Road Frontage Width 14 ft  │ conversion permissions needed.      │
└───────────────┴──────────────────────────────────┴─────────────────────────────────────┘
```

---

## Q. Human Review Layer

Software detects discrepancies; certified human professionals take legal and operational accountability.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        DIAGRAM 17: HUMAN REVIEW GATES                                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  GATE 1: FIELD SURVEY PROFESSIONAL (AMIN)                                              │
│  ├── Credentials Verified: State Revenue License / Polytechnic Survey Diploma          │
│  ├── Actions: Certifies GPS corner pin locations, confirms boundary ridge monument     │
│  │   alignment, signs physical possession inspection statement.                        │
│  └── Output: Signed Field Verification Certificate (Evidence EV-SURVEY-01)             │
│                                                                                        │
│  GATE 2: EMPANELLED TITLE ADVOCATE                                                     │
│  ├── Credentials Verified: Bar Council of India Enrollment Number                      │
│  ├── Actions: Reviews 30-year longitudinal chain of title, certifies personal law      │
│  │   inheritance coparcenary validity, validates SPT/CNT statutory transfer compliance. │
│  └── Output: Formal Title Due Diligence Legal Sign-off (Evidence EV-LEGAL-01)          │
│                                                                                        │
│  DISCLAIMER ENFORCEMENT: BhumiSetu software facilitates fact discovery; the licensed   │
│  advocate assumes legal professional responsibility under the Advocates Act 1961.      │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## R. Field Verification Layer

The field verification protocol translates physical ground reality into mathematically auditable spatial evidence.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   DIAGRAM 18: FIELD AMIN INSPECTION PROTOCOL                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  [Step 1: Calibration]                                                                 │
│  Amin pairs Bluetooth RTK-GNSS receiver with PWA; verifies HDOP < 1.5, Fix = RTK-FIX   │
│         │                                                                              │
│         ▼                                                                              │
│  [Step 2: Corner Pinning]                                                              │
│  Amin walks perimeter; captures 4 to 8 boundary corner pins (Lat, Lon, Elevation, Acc) │
│         │                                                                              │
│         ▼                                                                              │
│  [Step 3: Geodesic Polygon Synthesis]                                                  │
│  PostGIS computes geodesic area; compares against deed stated extent                   │
│         │                                                                              │
│         ▼                                                                              │
│  [Step 4: Photographic Ridge Audit]                                                    │
│  Amin captures 4 directional photos (N, S, E, W ridges) with embedded compass azimuth  │
│         │                                                                              │
│         ▼                                                                              │
│  [Step 5: Social Ground Inquest]                                                       │
│  Amin interviews adjoining cultivators on all 4 borders; records physical occupants    │
│         │                                                                              │
│         ▼                                                                              │
│  [Step 6: PWA Cryptographic Sync]                                                      │
│  Data packaged with device integrity token, hashed, and synced to Evidence Vault       │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## S. GIS Architecture & Area Calculations

### 1. The Strict Geometry Hierarchy
The architecture mandates that field measurements do not constitute statutory legal boundaries.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        DIAGRAM 19: SPATIAL GEOMETRY TAXONOMY                           │
├─────────────────────────┬──────────────────────────────────────────────────────────────┤
│ Geometry Class          │ Legal & Technical Standing                                   │
├─────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Authoritative Geometry  │ State DILRMP officially notified Cadastral Survey vector    │
│                         │ shapefile (EPSG:4326). Represents official revenue map.     │
├─────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Source Geometry         │ Raw, unprojected colonial village map sheet scan (BhuNaksha  │
│                         │ raster / CAD). Lacks real-world geodetic projection.         │
├─────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Derived Geometry        │ Algorithmic approximations (bounding boxes, village centroid)│
├─────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Field-Measured Geometry │ Closed polygon computed from Amin GNSS corner pins.          │
│                         │ **Represents physical boundary, NOT legal title.**           │
├─────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Legally Determined Bndy │ Boundary fixed by Revenue Court decree or Consolidation Act. │
└─────────────────────────┴──────────────────────────────────────────────────────────────┘
```

### 2. Area Calculation Rigor
* **Projection & Coordinate Reference System (CRS)**: Raw GPS coordinates are collected in **WGS84 (EPSG:4326)**. Before computing area, coordinates must be projected to the appropriate regional UTM zone (**UTM Zone 45N / EPSG:32645** for Jharkhand and Bihar) or computed using PostGIS spheroidal geodesic algorithms:
  ```sql
  -- Geodesic Area Calculation on Spheroid (WGS84)
  SELECT ST_Area(geography(measured_polygon)) * 0.000247105 AS measured_area_acres;
  ```
* **Area Taxonomy**:
  * `RECORDED_AREA`: Extent stated in the registered deed or Jamabandi.
  * `MEASURED_AREA`: Surface area calculated from ground GNSS corner pins.
  * `AUTHORITATIVE_AREA`: Extent recorded in the original 1932 Cadastral Survey Khatiyan.
  * `LEGAL_AREA`: Area adjudicated by a competent civil court or revenue settlement officer.

---

## T. Legal Rule Engine

The Legal Rule Engine models statutory land restrictions as versioned, deterministic logic rules rather than simplistic hardcoded booleans.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                 DIAGRAM 20: VERSIONED LEGAL RULE ENGINE ARCHITECTURE                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  RULE DEFINITION: RULE-JH-SPT-SEC20 (Version: 2026.1)                                  │
│  ├── Statutory Basis: Section 20, Santhal Parganas Tenancy (Supplementary Provisions)  │
│  │   Act 1949 (Bihar Act XIV of 1949)                                                  │
│  ├── Jurisdiction Scope: State = "JH", Districts = ["Deoghar", "Dumka", "Godda",       │
│  │   "Jamtara", "Sahibganj", "Pakur"]                                                  │
│  │                                                                                     │
│  ├── EVALUATION LOGIC:                                                                 │
│  │   IF parcel.district IN scope                                                       │
│  │   AND parcel.land_nature == 'AGRICULTURAL_RAIYATI'                                  │
│  │   THEN:                                                                             │
│  │     IF transferor.community_caste_category == 'SCHEDULED_TRIBE'                     │
│  │     THEN:                                                                           │
│  │       CHECK transferee.community_caste_category == 'SCHEDULED_TRIBE'                │
│  │       CHECK transferee.residence_village == parcel.village                          │
│  │       CHECK statutory_permission_dc_attached == TRUE                                │
│  │       IF ANY CHECK FAILS:                                                           │
│  │         EMIT Finding(Severity: CRITICAL, Action: ABORT_TRANSACTION_STATUTORY_BAR)   │
│  │                                                                                     │
│  └── EXPLICIT PROVENANCE & REVIEW:                                                     │
│      ├── Rule Author: Senior Advocate Panel, Jharkhand High Court                      │
│      ├── Last Verified Against Case Law: 2026-01-10                                    │
│      └── Status: ACTIVE_STATUTORY_RULE                                                 │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

The system strictly distinguishes:
1. `SOURCE_STATUTORY_TEXT`: The verbatim wording of the act/gazette.
2. `DERIVED_RULE`: The executable code logic checking input variables.
3. `HUMAN_LEGAL_REVIEW`: The advocate's confirmation that the rule applies to this case.

---

## U. AI Land Expert

The AI Land Expert is a read-only intelligence layer. It interacts with the case through a strict RAG boundary over structured evidence and claims.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                      DIAGRAM 21: AI LAND EXPERT RAG BOUNDARY                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  USER PROMPT: "Does the seller have the right to sell the entire 2.40 acres?"          │
│         │                                                                              │
│         ▼                                                                              │
│  [Security & Injection Filter: Strips prompt injection & malicious tokens]             │
│         │                                                                              │
│         ▼                                                                              │
│  [Context Retrieval Service: Fetches Active Claims, Findings & Evidence Spans]         │
│    ├── Ingested: Claim 1 (Deed #4122 states 2.40 Acres)                                │
│    ├── Ingested: Finding 1 (Measured Ground Area is only 2.112 Acres)                  │
│    └── Ingested: Claim 2 (Jamabandi records co-sharer Suresh Yadav holds 50% share)     │
│         │                                                                              │
│         ▼                                                                              │
│  [LLM Synthesis with Strict 6-Point Grounding Contract]                                │
│         │                                                                              │
│         ▼                                                                              │
│  OUTPUT PAYLOAD:                                                                       │
│  1. ANSWER: No. The seller does not appear to possess clear unencumbered title to      │
│     2.40 acres based on the retrieved evidence.                                        │
│  2. EVIDENCE: Deed #4122/2018 (Page 3) and Jamabandi Register II (Khata #104).         │
│  3. SOURCE: SRO Mohanpur & Department of Revenue, Jharkhand.                           │
│  4. CONFIDENCE: HIGH (Supported by registered deed and revenue records).               │
│  5. UNCERTAINTY: Whether an unrecorded private family partition occurred between       │
│     Ramesh Yadav and Suresh Yadav after 2018 is unverified.                            │
│  6. NEXT ACTION: Advocate must demand a registered partition deed or require Suresh    │
│     Yadav to join as a co-vendor in the conveyance.                                    │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## V. Report / Digital Land Passport

The deliverable is a comprehensive, client-facing **Land Verification Report & Digital Land Passport**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                  DIAGRAM 22: DIGITAL LAND PASSPORT INTEGRITY ARCHITECTURE              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  DIGITAL LAND PASSPORT (PDF Artifact)                                                  │
│  ├── Document Header: Bhumi ID: IN-JH-DEO-MOH-362910-K104-P542                         │
│  ├── QR Integrity Seal: Encodes verification URL + Cryptographic Hash                   │
│  │                                                                                     │
│  ├── WHAT THE QR VERIFICATION PROVES:                                                  │
│  │   ✔ Proves this PDF was generated by BhumiSetu on 2026-09-18.                       │
│  │   ✔ Proves the findings, area deltas, and risk flags match the immutable database.  │
│  │   ✔ Proves the report has not been altered or tampered with since issuance.         │
│  │                                                                                     │
│  ├── WHAT THE QR VERIFICATION DOES NOT PROVE:                                          │
│  │   ✖ DOES NOT constitute government statutory title authentication.                  │
│  │   ✖ DOES NOT replace the Sub-Registrar's conveyance registration.                   │
│  │   ✖ DOES NOT guarantee immunity from unrecorded judicial litigation.               │
│  │                                                                                     │
│  └── Content Sections: Executive Summary, Record vs Ground Reality Matrix,             │
│      SPT/CNT Tenancy Audit, Cadastral Map Overlay, Itemized Findings & Actions,         │
│      Field Amin & Title Advocate Sign-Offs, Complete Evidence Appendix.                │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## W. Transaction Readiness

Transaction readiness is evaluated through a deterministic checklist state machine.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                    DIAGRAM 23: TRANSACTION READINESS GATEWAY                           │
├──────────────────────────────────────────────────────────────────────┬─────────────────┤
│ Verification Gate                                                    │ Status Required │
├──────────────────────────────────────────────────────────────────────┼─────────────────┤
│ Gate 1: Parcel Identity Unambiguously Anchored to Mauza & LGD Code   │ PASS            │
│ Gate 2: Registered Chain of Conveyance Ingested & Parsed             │ PASS            │
│ Gate 3: Revenue Record (Jamabandi) Verified                          │ PASS            │
│ Gate 4: Mutation Discrepancy Resolved (Deed matches Jamabandi)       │ PASS            │
│ Gate 5: Statutory Tenancy Audit (SPT / CNT Act Tribal Bar)           │ PASS (CLEAR)    │
│ Gate 6: Physical Ground Survey Completed by Certified Amin           │ PASS            │
│ Gate 7: Ground Measured Area Deficit $\le 5.0\%$                    │ PASS            │
│ Gate 8: Physical Possession Confirmed Without Adverse Occupants      │ PASS            │
│ Gate 9: Zero Open CRITICAL Severity Findings                         │ PASS            │
│ Gate 10: Licensed Title Advocate Sign-Off Completed                  │ PASS            │
├──────────────────────────────────────────────────────────────────────┴─────────────────┤
│ COMPOSITE READINESS STATE:                                                             │
│ • READY_FOR_LEGAL_CLOSING: All 10 Gates PASS.                                          │
│ • REQUIRES_CONDITIONAL_RESOLUTION: Gates 1-6 PASS, Gate 7 or 8 requires client waiver.│
│ • BLOCKED_STATUTORY_HAZARD: Gate 5 FAILS (Tribal tenancy bar detected).                │
│ • NOT_READY: Gates 1-4 or 6 PENDING.                                                   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## X. Database Architecture (Hardened Schema)

The database schema is implemented in **PostgreSQL 16 + PostGIS 3.4**. It enforces complete normalization, foreign key constraints, and multi-tenancy isolation.

```sql
-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- 1. Organizations (Multi-Tenancy) [MVP]
CREATE TABLE organizations (
    org_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) NOT NULL,
    slug VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Parties Master (First-Class Domain Object) [MVP]
CREATE TABLE parties (
    party_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(org_id),
    party_type VARCHAR(32) NOT NULL, -- 'PERSON', 'ORGANIZATION', 'GOVERNMENT_ENTITY', 'TRUST', 'HUF'
    primary_name VARCHAR(128) NOT NULL,
    canonical_transliterated_name VARCHAR(128),
    father_or_husband_name VARCHAR(128),
    relationship_type VARCHAR(16), -- 'SON_OF', 'DAUGHTER_OF', 'WIFE_OF'
    community_caste_category VARCHAR(32) NOT NULL DEFAULT 'GENERAL', -- 'GENERAL', 'OBC', 'SC', 'ST'
    is_tribal BOOLEAN GENERATED ALWAYS AS (community_caste_category = 'ST') STORED,
    phone_number VARCHAR(20),
    residence_village_lgd VARCHAR(32),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_parties_lookup ON parties(canonical_transliterated_name, father_or_husband_name);

-- 3. Canonical Parcels [MVP]
CREATE TABLE parcels (
    parcel_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(org_id),
    bhumi_id VARCHAR(64) UNIQUE NOT NULL, -- 'IN-JH-DEO-MOH-362910-K104-P542'
    state_code VARCHAR(4) NOT NULL,
    district_name VARCHAR(64) NOT NULL,
    subdistrict_anchal_name VARCHAR(64) NOT NULL,
    halka_number VARCHAR(16),
    mauza_village_name VARCHAR(128) NOT NULL,
    census_village_code VARCHAR(32) NOT NULL,
    khata_number VARCHAR(32) NOT NULL,
    plot_khesra_number VARCHAR(32) NOT NULL,
    subdivision_hissa_number VARCHAR(32),
    recorded_area_acres NUMERIC(10, 4) NOT NULL,
    land_nature VARCHAR(32) DEFAULT 'AGRICULTURAL_RAIYATI',
    centroid_point GEOMETRY(Point, 4326),
    authoritative_boundary GEOMETRY(MultiPolygon, 4326),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_parcels_lookup ON parcels(state_code, district_name, subdistrict_anchal_name, mauza_village_name, plot_khesra_number);
CREATE INDEX idx_parcels_geometry ON parcels USING GIST(authoritative_boundary);

-- 4. Parcel Lineage & Relationships [MVP]
CREATE TABLE parcel_relationships (
    relationship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_parcel_id UUID REFERENCES parcels(parcel_id),
    child_parcel_id UUID REFERENCES parcels(parcel_id),
    relationship_type VARCHAR(32) NOT NULL, -- 'SUBDIVIDED_TO', 'MERGED_TO', 'RENUMBERED_TO', 'CORRECTED_TO'
    effective_date DATE NOT NULL,
    mutation_order_reference VARCHAR(128),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Transactions Master [MVP]
CREATE TABLE transactions (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(org_id),
    transaction_type VARCHAR(32) NOT NULL, -- 'SALE', 'PARTITION', 'GIFT', 'INHERITANCE', 'MORTGAGE'
    execution_date DATE,
    registration_date DATE,
    registration_identifier VARCHAR(128), -- 'Book 1, Vol 42, Deed 4122/2018'
    sro_code VARCHAR(32),
    stated_consideration_inr NUMERIC(14, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Transaction to Parcel Join (M:N) [MVP]
CREATE TABLE transaction_parcels (
    transaction_id UUID REFERENCES transactions(transaction_id),
    parcel_id UUID REFERENCES parcels(parcel_id),
    transferred_area_acres NUMERIC(10, 4) NOT NULL,
    PRIMARY KEY (transaction_id, parcel_id)
);

-- 7. Transaction to Party Join (M:N) [MVP]
CREATE TABLE transaction_parties (
    transaction_id UUID REFERENCES transactions(transaction_id),
    party_id UUID REFERENCES parties(party_id),
    party_role VARCHAR(32) NOT NULL, -- 'EXECUTANT_VENDOR', 'CLAIMANT_BUYER', 'WITNESS', 'IDENTIFIER'
    share_percentage NUMERIC(5, 2) DEFAULT 100.00,
    PRIMARY KEY (transaction_id, party_id, party_role)
);

-- 8. Cases Master [MVP]
CREATE TABLE cases (
    case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(org_id),
    case_number VARCHAR(32) UNIQUE NOT NULL, -- 'CAS-2026-0001'
    primary_client_party_id UUID REFERENCES parties(party_id),
    assigned_amin_id UUID,
    assigned_advocate_id UUID,
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    transaction_readiness_status VARCHAR(32) NOT NULL DEFAULT 'NOT_READY',
    target_transaction_id UUID REFERENCES transactions(transaction_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 9. Case to Parcel Join (M:N) [MVP]
CREATE TABLE case_parcels (
    case_id UUID REFERENCES cases(case_id),
    parcel_id UUID REFERENCES parcels(parcel_id),
    PRIMARY KEY (case_id, parcel_id)
);

-- 10. Evidence Vault [MVP]
CREATE TABLE evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_type VARCHAR(32) NOT NULL, -- 'GOVERNMENT_RECORD', 'REGISTERED_DOCUMENT', 'FIELD_PHOTO', 'GPS_OBSERVATION'
    authority_tier VARCHAR(32) NOT NULL, -- 'STATUTORY_REGISTRY', 'REVENUE_RECORD', 'FIELD_OBSERVATION'
    source_name VARCHAR(128) NOT NULL,
    storage_uri VARCHAR(512) NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    captured_by_party_id UUID REFERENCES parties(party_id),
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 11. Case to Evidence Join (M:N) [MVP]
CREATE TABLE case_evidence (
    case_id UUID REFERENCES cases(case_id),
    evidence_id UUID REFERENCES evidence(evidence_id),
    attached_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (case_id, evidence_id)
);

-- 12. Structured Temporal Claims [MVP]
CREATE TABLE claims (
    claim_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id UUID REFERENCES evidence(evidence_id),
    parcel_id UUID REFERENCES parcels(parcel_id),
    subject_entity_type VARCHAR(32) NOT NULL, -- 'PARCEL', 'PARTY'
    subject_id UUID NOT NULL,
    predicate VARCHAR(64) NOT NULL, -- 'RECORDED_OWNER', 'RECORDED_AREA', 'BOUNDARY_NORTH'
    object_value JSONB NOT NULL,
    authority_tier VARCHAR(32) NOT NULL,
    confidence_score NUMERIC(5, 2) NOT NULL,
    observed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE,
    effective_from DATE,
    effective_to DATE,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'DISPUTED', 'SUPERSEDED'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 13. Analytical Findings [MVP]
CREATE TABLE findings (
    finding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(case_id),
    parcel_id UUID REFERENCES parcels(parcel_id),
    rule_id VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL, -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFORMATIONAL'
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN', -- 'OPEN', 'IN_PROGRESS', 'RESOLVED', 'ACCEPTED_WITH_REVIEW'
    observed_values JSONB NOT NULL,
    explanation TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 14. Required Actions (Remediation Workflow) [MVP]
CREATE TABLE required_actions (
    action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id UUID REFERENCES findings(finding_id),
    case_id UUID REFERENCES cases(case_id),
    action_type VARCHAR(64) NOT NULL, -- 'FIELD_RESURVEY', 'OBTAIN_MUTATION_ORDER', 'ADVOCATE_LEGAL_INQUEST'
    assigned_role VARCHAR(32) NOT NULL, -- 'FIELD_AMIN', 'LEGAL_ADVOCATE', 'OPERATIONS_DESK'
    assigned_to_party_id UUID REFERENCES parties(party_id),
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN', -- 'OPEN', 'IN_PROGRESS', 'RESOLVED', 'BLOCKED'
    resolution_notes TEXT,
    resolved_by_party_id UUID REFERENCES parties(party_id),
    resolving_evidence_id UUID REFERENCES evidence(evidence_id),
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 15. Field Surveys (Amin Ground Measurements) [MVP]
CREATE TABLE field_surveys (
    survey_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(case_id),
    parcel_id UUID REFERENCES parcels(parcel_id),
    surveyor_party_id UUID REFERENCES parties(party_id),
    gnss_receiver_model VARCHAR(64),
    measured_area_acres NUMERIC(10, 4) NOT NULL,
    measured_boundary_geometry GEOMETRY(Polygon, 4326) NOT NULL,
    north_ground_neighbor VARCHAR(128),
    south_ground_neighbor VARCHAR(128),
    east_ground_neighbor VARCHAR(128),
    west_ground_neighbor VARCHAR(128),
    road_access_type VARCHAR(32), -- 'PUCCA_ROAD', 'KACHA_RASTA', 'LANDLOCKED'
    road_frontage_feet NUMERIC(8, 2),
    physical_possessor_name VARCHAR(128),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_surveys_geometry ON field_surveys USING GIST(measured_boundary_geometry);

-- 16. Land Passports (Compiled Sealed Reports) [MVP]
CREATE TABLE land_passports (
    passport_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID UNIQUE REFERENCES cases(case_id),
    passport_number VARCHAR(32) UNIQUE NOT NULL, -- 'LP-2026-JH-0041'
    transaction_readiness_state VARCHAR(32) NOT NULL,
    statutory_tenancy_status VARCHAR(32) NOT NULL,
    area_variance_percentage NUMERIC(6, 2),
    sha256_sealed_hash VARCHAR(64) NOT NULL,
    pdf_storage_uri VARCHAR(512) NOT NULL,
    issued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 17. Immutable System Audit Trail [MVP]
CREATE TABLE audit_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(org_id),
    actor_party_id UUID REFERENCES parties(party_id),
    action VARCHAR(64) NOT NULL,
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

## Y. API Architecture (MVP Endpoints)

FastAPI endpoints enforce strict authentication, organization multi-tenancy scoping, and request validation via Pydantic schemas.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                MVP API SPECIFICATION                                   │
├───────────────────────────────────┬────────────────────────────────────────────────────┤
│ Endpoint                          │ Purpose, Request & Response Contract               │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ POST   /api/v1/cases              │ Init Case: {"client_party_id": "...", "type": "..."│
│ GET    /api/v1/cases/:id          │ Full Case detail, linked parcels, and state badge  │
│ PATCH  /api/v1/cases/:id/status   │ Validated transition: {"next_status": "..."}       │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ POST   /api/v1/cases/:id/parcels  │ Link Parcel to Case: {"parcel_id": "..."}          │
│ POST   /api/v1/parcels            │ Create Canonical Parcel with Mauza & LGD anchors   │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ POST   /api/v1/evidence/upload    │ Upload raw artifact (Pre-signed URL generation)    │
│ POST   /api/v1/cases/:id/evidence │ Link Evidence to Case: {"evidence_id": "..."}      │
│ GET    /api/v1/cases/:id/evidence │ Fetch Case Evidence Ledger & download URLs         │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ GET    /api/v1/cases/:id/claims   │ Retrieve extracted atomic claims with time anchors │
│ GET    /api/v1/cases/:id/findings │ Retrieve detected discrepancies & risk severity    │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ POST   /api/v1/actions/:id/resolve│ Mark Action resolved with resolving evidence ID    │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ POST   /api/v1/cases/:id/surveys  │ Field Amin uploads GNSS pins & photo survey payload│
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ POST   /api/v1/cases/:id/reports  │ Trigger Land Passport compilation & SHA-256 seal   │
│ GET    /api/v1/cases/:id/reports  │ Retrieve signed Land Passport PDF & verification QR│
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ POST   /api/v1/cases/:id/ai/query │ Query AI Land Expert over grounded case evidence   │
└───────────────────────────────────┴────────────────────────────────────────────────────┘
```

---

## Z. UI Architecture

The frontend is implemented as a **Next.js + TypeScript** single-page web workspace and an offline-first **Mobile PWA** for Field Amins.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                UI WORKSPACE TOPOLOGY                                   │
├───────────────────┬────────────────────────────────────────────────────────────────────┤
│ View              │ Functional Purpose & Core Components                               │
├───────────────────┼────────────────────────────────────────────────────────────────────┤
│ 1. Case Queue     │ Operational dashboard tracking cases by state, SLA, and blockers.  │
│ 2. Case Creator   │ Property identification modal: Cascading District ──► Anchal       │
│                   │ ──► Mauza ──► Khata ──► Plot input with LGD validation.            │
│ 3. Case Workspace │ Split-pane command center:                                         │
│                   │ • Left: Document Viewer (PDF canvas with evidence bounding boxes)  │
│                   │ • Center: Reality Matrix (Deed vs Revenue vs Ground Survey)        │
│                   │ • Right: Action Queue, Finding Resolvers, and AI Chat Drawer.      │
│ 4. Evidence Vault │ Tabular ledger displaying file hashes, uploaders, and source URIs. │
│ 5. Amin Field PWA │ Mobile survey mode: Bluetooth GNSS pairing, corner pin plotter,    │
│                   │ compass azimuth camera, and Chauhadri interview voice memos.       │
│ 6. Map Studio     │ Leaflet/Mapbox split-map: Cadastral map vs Measured GPS polygon.   │
│ 7. Passport View  │ Official print-ready Land Passport preview with verification QR.   │
└───────────────────┴────────────────────────────────────────────────────────────────────┘
```

---

## AA. Security, Privacy & Compliance

1. **Tenant Isolation**: Every database query filters by `org_id`. Cross-tenant data leaks are structurally prevented.
2. **Encrypted Evidence Vault**: All uploaded documents and field photos are stored with **AES-256 server-side encryption** in private S3 buckets. Browser access is governed strictly by temporary **Pre-Signed URLs** expiring after 15 minutes.
3. **DPDP Act 2023 PII Redaction**: Scanned deeds containing Aadhaar numbers, private PAN details, or bank account numbers undergo automatic client-side or ingestion-time masking before document display.
4. **Advocates Act 1961 Compliance**: Software outputs are formally categorized as **"Factual Due Diligence & Discrepancy Audits"**. Final title sign-offs require an independent licensed advocate's certified enrollment signature.

---

## AB. Auditability & Provenance

Every state modification emits an immutable, append-only row into `audit_logs`:
* Actor identity (`actor_party_id`).
* Target entity (`entity_name`, `entity_id`).
* Action signature (`CASE_STATUS_TRANSITION`, `ACTION_RESOLVED`, `EVIDENCE_ATTACHED`).
* Before/after state snapshot stored as JSONB diffs.
* Client IP address and timestamp.

The **Land Passport** verification QR code resolves to a public endpoint:
`https://verify.bhumisetu.com/passport/:passport_number?hash=:sha256`
The server fetches the canonical passport record, recalculates the SHA-256 hash over all sealed findings and evidence hashes, and confirms whether the document is pristine or altered.

---

## AC. Data-Moat Architecture

BhumiSetu converts every completed field verification into an enduring proprietary data asset:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        DIAGRAM 24: THE GROUND-TRUTH FLYWHEEL                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│               [Client Commissions Case on Plot 542 in Mohanpur]                        │
│                                       │                                                │
│                                       ▼                                                │
│                 [Field Amin Captures 6 High-Precision GPS Pins]                        │
│                                       │                                                │
│                                       ▼                                                │
│           [True Geodesic Polygon Plotted + 4 Neighbor Boundaries Audited]              │
│                                       │                                                │
│                                       ▼                                                │
│            [Plot 541 (North) and Plot 543 (East) Boundaries Fixed in Graph]            │
│                                       │                                                │
│                                       ▼                                                │
│          [Future Inquiries on Adjoining Plots 541 or 543 Resolve Instantly]            │
│                                       │                                                │
│                                       ▼                                                │
│          [BhumiSetu Builds a Proprietary Cadastral Ground Graph That No]               │
│          [Web Scraper or Cloud Document Platform Can Ever Replicate]                   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## AD. MVP Boundary

The MVP is strictly bounded to the capabilities required to deliver the first paid **Land Verification Case** in Deoghar, Jharkhand:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                         MVP VERTICAL SLICE BOUNDARY                                    │
├───────────────────────────────────┬────────────────────────────────────────────────────┤
│ INCLUDED IN MVP                   │ EXCLUDED FROM MVP (DEFERRED)                       │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ • Geographic Focus: Deoghar, JH   │ • Nationwide property search engine                │
│ • Core Entities: Parcel, Case,    │ • Automated scrapers for 26 states                 │
│   Tx, Party, Evidence, Claim,     │ • Real estate classifieds marketplace              │
│   Finding, Action, Survey, Report │ • Lending / escrow fund transfers                  │
│ • Registered Deed + RoR Ingestion │ • Unsupervised automated legal opinions            │
│ • Amin Mobile Survey PWA          │ • Automated Indic OCR training clusters            │
│ • Area Delta + SPT Sec 20 Engine  │ • Blockchain / tokenized smart contracts           │
│ • Land Passport PDF with QR seal  │ • Public developer API gateway                     │
│ • Grounded AI Land Expert         │ • Enterprise multi-branch billing systems          │
└───────────────────────────────────┴────────────────────────────────────────────────────┘
```

---

## AE. Build Now / Next / Later / Future

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             BUILD PHASING MATRIX                                       │
├─────────────────┬──────────────────────────────────────────────────────────────────────┤
│ Tier            │ Modules & Engineering Scope                                          │
├─────────────────┼──────────────────────────────────────────────────────────────────────┤
│ BUILD NOW       │ • PostgreSQL 16 + PostGIS 3.4 Schema (17 core MVP tables)            │
│ (MVP)           │ • FastAPI Modular Backend & Next.js Case Workspace UI                │
│                 │ • S3 Private Evidence Vault with Pre-Signed URL Uploads              │
│                 │ • Field Amin Survey PWA with GPS Pinning & Azimuth Photos            │
│                 │ • Deterministic Consistency Engine (Area Delta & SPT Sec 20 Rule)    │
│                 │ • Finding ──► RequiredAction ──► Resolution Workflow Engine          │
│                 │ • Land Passport PDF Generator with SHA-256 QR Integrity Verification │
│                 │ • Grounded AI Land Expert (Read-only RAG over case evidence)         │
├─────────────────┼──────────────────────────────────────────────────────────────────────┤
│ BUILD NEXT      │ • Expansion to Banka (Bihar) and Dumka (Jharkhand)                   │
│ (Phase 2)       │ • Automated web connectors for JharBhoomi & BiharBhumi               │
│                 │ • Bluetooth RTK-GNSS hardware auto-sync integration                  │
│                 │ • Cadastral BhuNaksha vector map overlay viewer                      │
│                 │ • eCourts litigation sync for title suits                            │
├─────────────────┼──────────────────────────────────────────────────────────────────────┤
│ BUILD LATER     │ • B2B Title Due Diligence API for Mortgage Banks & HFCs              │
│ (Phase 3)       │ • Automated Indic OCR LayoutLM Pipeline for Devanagari deeds         │
│                 │ • CERSAI Mortgage Registry Integration                               │
│                 │ • Expansion to Uttar Pradesh and Maharashtra                         │
├─────────────────┼──────────────────────────────────────────────────────────────────────┤
│ FUTURE          │ • Machine-learning satellite boundary change detection               │
│                 │ • Large-scale infrastructure land acquisition due diligence suite    │
│                 │ • Institutional title risk insurance underwriting protocol           │
└─────────────────┴──────────────────────────────────────────────────────────────────────┘
```

---

## AF. Architecture Decision Records (ADRs)

### ADR-01: Modular Relational Monolith over Microservices
* **Context**: The team requires rapid execution speed, ACID consistency across Cases and Evidence, and operational simplicity.
* **Decision**: Adopt a modular monolith (FastAPI backend + Next.js frontend + PostgreSQL/PostGIS database).
* **Consequences**: Zero distributed network latency, immediate transactional integrity, and trivial deployment.

### ADR-02: PostgreSQL + PostGIS as Unified Relational and Spatial Store
* **Context**: Parcels require geospatial polygon math alongside relational business workflows.
* **Decision**: Use PostgreSQL 16 with PostGIS 3.4 rather than separate spatial or graph databases.
* **Consequences**: Native spatial joins (`ST_Area`, `ST_Intersects`) executed in the same transaction as claims and findings.

### ADR-03: Decoupled Claim & Evidence Model with Temporal Coexistence
* **Context**: Conflicting ownership assertions from disparate records must not overwrite each other.
* **Decision**: Facts are modeled as atomic, attributed, temporal `Claims` referencing raw `Evidence`. Parcels never store flat ownership strings.
* **Consequences**: Complete auditability of conflicting historical records without schema corruption.

### ADR-04: Strict AI Boundary (Read-Only Assistance)
* **Context**: LLMs can hallucinate title validity and mathematical calculations, exposing clients to catastrophic loss.
* **Decision**: AI is restricted to candidate extraction, document summarization, and grounded Q&A. AI cannot modify canonical database records or certify title.
* **Consequences**: Zero risk of AI-induced title fraud or hallucinated clearance.

### ADR-05: Finding ──► RequiredAction ──► Resolution Workflow
* **Context**: Identified property defects must not remain static warnings; they require managed operational resolution.
* **Decision**: Every Finding automatically spawns an actionable task with an assigned role and resolution verification requirement.
* **Consequences**: Clear operational ownership for field Amins and title advocates.

---

## AG. Risk Register

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             ARCHITECTURAL RISK REGISTER                                │
├──────────────────────────────┬──────┬──────┬───────────────────────────────────────────┤
│ Risk Description             │ Prob │ Imp  │ Actionable Mitigation Strategy            │
├──────────────────────────────┼──────┼──────┼───────────────────────────────────────────┤
│ 1. JharBhoomi Portal Outage  │ HIGH │ MED  │ Asynchronous queue with exponential retry;│
│                              │      │      │ fallback to manual SRO document runners.  │
├──────────────────────────────┼──────┼──────┼───────────────────────────────────────────┤
│ 2. GNSS Multipath Drift in   │ MED  │ HIGH │ Enforce HDOP < 1.5, minimum 12 satellites,│
│    Remote Forest Pockets     │      │      │ and 30-second multi-point averaging.      │
├──────────────────────────────┼──────┼──────┼───────────────────────────────────────────┤
│ 3. Advocates Act Legal Bar   │ MED  │ HIGH │ Position platform strictly as technical   │
│                              │      │      │ fact audit; mandate independent advocate  │
│                              │      │      │ digital enrollment sign-off on reports.   │
├──────────────────────────────┼──────┼──────┼───────────────────────────────────────────┤
│ 4. Amin Vernacular Friction  │ MED  │ MED  │ Build offline-first PWA with Hindi UI,    │
│                              │      │      │ voice note support, and large buttons.    │
├──────────────────────────────┼──────┼──────┼───────────────────────────────────────────┤
│ 5. Degraded Deed OCR Failure │ HIGH │ MED  │ Hybrid OCR: automated candidate extraction│
│                              │      │      │ with manual operator verification fallback│
└──────────────────────────────┴──────┴──────┴───────────────────────────────────────────┘
```

---

## AH. Unknowns

1. **Deoghar Cadastral Vector Availability**: What exact percentage of revenue villages in Mohanpur and Sarwan have digitized, rectified DILRMP GIS shapefiles versus colonial paper scans?
2. **CORS Network Baselines in Santhal Pargana**: What is the real-world baseline distance to the nearest Survey of India CORS reference station for centimeter-level RTK corrections?
3. **Institutional CERSAI Query Gateways**: Can a non-banking technology firm obtain direct programmatic API read access to the CERSAI mortgage database without a sponsor bank?

---

## AI. Open Decisions

1. **Field Hardware Receiver**: Selection of the standardized pilot GNSS hardware receiver (Emlid Reach RX vs. Bad Elf Surveyor vs. high-accuracy dual-frequency smartphone GNSS).
2. **Deed Procurement Operational Sourcing**: Choosing between licensing Landeed’s B2B Document Procurement API for certified copies versus maintaining a dedicated local deed runner at Mohanpur SRO.

---

## AJ. MVP Vertical Slice

The following scenario details the complete end-to-end execution of a real land verification case:

```text
1. Client Intake:
   Buyer walks into BhumiSetu office in Deoghar considering purchasing 1.20 Acres in Mohanpur Mauza.
   Operator initializes Case: CAS-2026-0001.

2. Parcel Identification:
   Operator inputs State: JH, District: Deoghar, Anchal: Mohanpur, Mauza: Mohanpur (LGD: 362910),
   Khata: 104, Plot: 542. System anchors canonical Bhumi ID: IN-JH-DEO-MOH-362910-K104-P542.

3. Document Ingestion:
   Buyer uploads scanned Registered Sale Deed #4122/2018. Operator uploads online JharBhoomi Jamabandi.
   Files stored in S3 Evidence Vault with SHA-256 hashes: EV-001, EV-002.

4. Extraction & Claims:
   Deed text extracted: Stated Area = 2.40 Acres, Transferee = Ramesh Yadav, North = Suresh Yadav.
   Jamabandi text extracted: Recorded Raiyat = Gopal Yadav (Unmutated!), Area = 2.40 Acres.
   Claims CLM-01, CLM-02, CLM-03 created.

5. Consistency Analysis:
   Rule RULE_MUTATION_GAP evaluates Deed vs Jamabandi.
   EMITS Finding FND-001: Registered deed unmutated in revenue records (Severity: HIGH).
   Generates RequiredAction ACT-01: "Verify if mutation case was filed or rejected at Anchal office."

6. Field Verification Task:
   Case moves to FIELD_VERIFICATION_REQUIRED. Dispatched to Field Amin U-104.
   Amin visits Plot 542 with Bluetooth GNSS receiver; pins 6 perimeter corners.
   PostGIS computes Geodesic Measured Area = 2.112 Acres.
   Delta calculated: -12.0% shortfall compared to deed stated extent.
   EMITS Finding FND-002: Area Shortfall > 10% (Severity: CRITICAL).
   Generates RequiredAction ACT-02: "Resurvey East boundary ridge adjoining Plot 543."

7. Statutory Tenancy Evaluation:
   Rule RULE-JH-SPT-SEC20 evaluates seller background.
   Seller is verified non-tribal (OBC/Yadav) on raiyati agricultural land.
   Gate 5 (SPT Act) PASSES.

8. Field Action Resolution:
   Amin interviews East boundary neighbor (Plot 543); discovers neighbor pushed boundary ridge by 15 feet.
   Amin takes geotagged photos with compass azimuth (EV-003); uploads to PWA.
   Action ACT-02 marked RESOLVED with evidence.

9. Legal Review & Remediation:
   Empanelled advocate reviews findings: requires seller to file mutation and rectify boundary ridge
   prior to deed execution. Client signs acceptance of conditional terms.
   Action ACT-01 marked RESOLVED.

10. Passport Generation:
    Case transitions to FINAL. Report Engine compiles Digital Land Passport LP-2026-JH-0001.
    Calculates SHA-256 seal: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.
    Generates print-ready PDF with QR seal linking to public verification endpoint.
    Client receives definitive Land Passport and successfully renegotiates purchase price.
```

---

## AK. Phase 2 Implementation Gate

### Gate Evaluation Checklist
* [x] **Domain Model Unambiguous**: Parcel, Case, and Transaction decoupled with documented cardinalities.
* [x] **Evidence Ownership Decoupled**: Evidence belongs to vault; linked to Cases via join table.
* [x] **Claims are Temporal**: Explicit `observed_at`, `recorded_at`, `effective_from`, and `effective_to` fields.
* [x] **First-Class Party Model**: Persons, Organizations, and roles defined independently of entity resolution.
* [x] **Parcel Lineage Defined**: Subdivision, consolidation, and renumbering modeled relationally.
* [x] **Legal Boundary vs Measured Boundary Separated**: Clear distinction between GNSS observations and statutory boundaries.
* [x] **Area Calculation Rigor Established**: WGS84 geodesic / UTM Zone 45N projection requirements documented.
* [x] **Expert Credentials Modeled**: Professional standing stored without claiming software-created statutory authority.
* [x] **Versioned Legal Rules**: SPT Act Section 20 modeled with provenance, jurisdiction scope, and human advocate review.
* [x] **Finding ──► Action ──► Resolution Workflow Specified**: Managed remediation cycle with explicit statuses.
* [x] **Opaque Scores Eliminated**: Descriptive severity tiers and deterministic readiness checklist enforced.
* [x] **Passport Authority Boundaries Clarified**: QR seal strictly proves document integrity, not government authentication.
* [x] **Field-Level Provenance Established**: Unbroken trace from extracted value down to page bounding box.
* [x] **AI Boundaries Enforced**: Read-only, grounded RAG assistant prohibited from canonical data commits.
* [x] **Seven Unknown States Implemented**: Consistent absence-of-evidence handling.
* [x] **Relational Schema Specified**: Production-ready PostgreSQL 16 + PostGIS 3.4 DDL (17 core MVP tables).
* [x] **Security & Privacy Defined**: Org isolation, pre-signed URLs, DPDP Act PII redaction, Advocates Act compliance.

---

### FINAL GATE VERDICT:

# **GO**

**Phase 1.1 Architecture Hardening is complete. All red-team defects, overengineering, and legal language ambiguities have been resolved. The architecture is locked and approved for Phase 2 implementation.**

---
**END OF SPECIFICATION — STOP CONDITION ACTIVE. AWAIT FORMAL USER AUTHORIZATION TO COMMENCE PHASE 2 IMPLEMENTATION.**
