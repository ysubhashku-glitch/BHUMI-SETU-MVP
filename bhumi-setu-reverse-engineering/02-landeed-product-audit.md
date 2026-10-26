# 02 - Landeed Product Audit

**Product:** Landeed  
**Audited Domains:** `https://www.landeed.com/`, `https://web.landeed.com/`  
**Date of Audit:** October 24, 2026  
**Auditor:** Bhumi Setu Engineering Intelligence  

---

## 1. Executive Summary & Value Proposition

Landeed positions itself as an infrastructure layer to make **"Indian property computable"**. Its primary commercial premise is that **77% of Indian household wealth is held in real estate**, yet ownership verification is fragmented across 28 states, hundreds of registration portals, municipal tax registries, and survey departments.

### 1.1 Core Value Proposition
1. **Unified Search & Disambiguation:** Replaces fragmented state government portals with a single search interface (by owner name, Khata, Khesra/plot, survey number, or deed registration details).
2. **Dual-Rail Fulfillment (At Source + At Counter):**
   - **At Source:** Automated retrieval where state systems are digital and public (e.g. Jamabandi in Bihar, Pahani/ROR-1B in Telangana, 7/12 in Maharashtra).
   - **At Counter:** Manual collection via physical field runners ("LeX" lounges and SRO agents across 15+ states) for legacy physical records, certified deed copies, and non-digitized years (e.g. pre-2004 deeds in Karnataka/Bihar).
3. **AI Reasoning Layer ("Terra" & "Terra Black"):** An LLM-orchestrated diligence assistant that plans record searches, reconciles discrepancies across documents, and outputs an evidence-backed title brief citing specific document numbers.

---

## 2. Product Line Breakdown

### 2.1 Retrieval & Procurement (`/products/retrieval-procurement`)
* **Observed Reality:** Delivers both digital downloads and physical certified copies.
* **Coverage Claim:** 28 states, 1,500+ registries, 20,000+ document types.
* **Document Taxonomy:**
  - Encumbrance Certificates (EC / Form 15 & 16)
  - Registered Deeds (Sale Deed, Gift Deed, Partition Deed, Release Deed)
  - Record of Rights (RoR, Jamabandi, RTC/Pahani, 7/12, Patta-Chitta, Khatauni)
  - Mutation Extracts (Dakhil Kharij, Ferfar, Intkal)
  - Cadastral / Survey Maps (Bhu-Naksha, FMB sketches, Aks Shajra)
  - Municipal Tax receipts, Khata certificates, and Sanction plans.

### 2.2 Land Intelligence (`/products/land-intelligence`)
* **Target Audience:** Real Estate Developers, Lenders (Banks & NBFCs), Retail Aggregators, Law Firms.
* **Features:**
  - Parcel Screening: Screen hundreds of survey numbers before physical field visits.
  - Risk Layers: Litigation status (eCourts matching), zoning classification (agricultural vs. residential/commercial conversion), acquisition notifications (Gazette checks).
  - Feasibility Score: Empirical 0–100 score indicating site feasibility and title clarity.

### 2.3 API & MCP Server (`/products/api-mcp`)
* **Observed Architecture:** Landeed maintains two distinct program interfaces:
  1. **REST API (`api.landeed.com/v1/`):** State-changing actions and document ordering (`POST /v1/orders`, `POST /v1/documents/retrieve`).
  2. **Terra MCP (`streamable-http`, OAuth 2.1):** Read-only reasoning interface for AI agents. Exposes 8 core query tools:
     - `resolve_property`
     - `check_coverage`
     - `get_ownership`
     - `get_encumbrances`
     - `list_transactions`
     - `search_litigation`
     - `get_land_classification`
     - `get_source_document`

### 2.4 Terra Black (`/labs/terra-black`)
* **Purpose:** Multi-step autonomous diligence agent.
* **Workflow Observed:**
  1. User inputs property query: *"Is Sy. No. 112/3 clear to buy? Check ownership since 1996."*
  2. Terra generates an **Editable Research Plan** (e.g., Step 1: Resolve parcel; Step 2: Pull ECs; Step 3: Trace mutations; Step 4: Search eCourts).
  3. Executes document retrieval and OCR extraction.
  4. Synthesizes a formal **Title Brief** categorized into three explicit evidential categories:
     - `Known` (e.g. *"No registered encumbrance since 1996 [EC Doc 3]"*)
     - `Unclear` (e.g. *"Civil suit OS-412/2021 matches co-owner name [eCourts]"*)
     - `Can't See / Missing` (e.g. *"Pre-1996 records unverified; physical SRO search required"*)

---

## 3. Discrepancy Between Marketing Claims and Observed Reality

| Marketing Claim | Observed Implementation | Engineering Takeaway for Bhumi Setu |
| :--- | :--- | :--- |
| **"Instant documents across 28 states"** | Instant retrieval is **only available for open, digital state records** (e.g., Bihar Jamabandi, Telangana Pahani). Pre-2004 records and certified copies take **3–7 business days** via physical counter runners. | Bhumi Setu must explicitly differentiate `Instant (Source API)` from `Field Required (LandAmin/SRO)`. Do not make false claims of instant automated title delivery. |
| **"Automated Title Clearance"** | Disclaimers explicitly state: *"Landeed is not a government entity... not a substitute for formal legal opinion"*. Reports provide factual findings, not statutory title certificates. | Bhumi Setu must generate **Land Intelligence Reports** with clear confidence tags, evidentiary citations, and legal disclaimers. |
| **"100% Comprehensive Litigation Check"** | eCourts matching is based on fuzzy party names and survey numbers. Revenue courts (Circle Officer / DCLR / Collector) are often disconnected. | Explicitly tag litigation sources: `District Court (eCourts)`, `High Court`, `Revenue Court (RCMS Bihar)`. Disclose search gaps. |
