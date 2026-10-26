# 08 - Bhumi Setu System Architecture

**Project:** Bhumi Setu  
**Document:** System Architecture & Component Specification  
**Version:** 2.0 (Post-Landeed Reverse-Engineering Blueprint)  
**Date:** October 24, 2026  

---

## 1. Architectural Philosophy & Design Principles

Bhumi Setu is designed as an **independent, auditable, evidence-backed land intelligence system**. Unlike generic document scrapers, Bhumi Setu adheres to four foundational engineering tenets:

1. **Evidential Grounding:** Every finding, ownership claim, or risk flag must cite an exact issuing office, registered document number, volume, page, and extraction timestamp.
2. **Deterministic Precedence:** Raw official government documents always take precedence over AI extractions or heuristic inferences.
3. **Hybrid Verification Rails:** Pure digital scrapers fail when records are physically archived or contested. Bhumi Setu integrates digital source retrieval with on-ground **LandAmin** field-verification operations.
4. **Agentic Computability via MCP:** In addition to human web dashboards and REST APIs, Bhumi Setu exposes a standard Model Context Protocol (MCP) server so autonomous enterprise agents can safely query land intelligence.

---

## 2. High-Level Architecture Diagram

```mermaid
graph TB
    subgraph Client Layer
        WebUI[Bhumi Setu Web Portal - Next.js / Vanilla SPA]
        MobileAmin[LandAmin Field Mobile App - Offline First]
        EnterpriseAPI[B2B REST Clients - LOS / Banks / Developers]
        AIAgents[External AI Agents - MCP Streamable HTTP]
    end

    subgraph API Gateway & Security
        Gateway[FastAPI Gateway / Reverse Proxy - Port 8000]
        Auth[OAuth2 / JWT / Phone OTP Service]
        AuditMiddleware[Request ID & Audit Context Middleware]
    end

    subgraph Core Application Services
        ParcelService[Property & Parcel Resolution Service]
        DocService[Document Ingestion & Vault Service]
        ConsistencyService[Evidence & Discrepancy Engine]
        PassportService[Property Passport & Timeline Service]
        ReportingService[Land Intelligence Report Generator]
        AminDispatch[LandAmin Task Dispatcher & Field Manager]
        MCPAdapter[Bhumi Setu MCP Tool Provider]
    end

    subgraph Intelligence & Processing Pipeline
        OCRWorker[OCR & Extraction Engine - PyMuPDF / Vision LLM]
        KaithiModel[Kaithi & Hindi Script Translation Engine]
        ScraperPool[Asynchronous Source Ingestion Workers]
    end

    subgraph External Data Sources
        BiharLRC[Bihar Bhumi - Jamabandi Register-II]
        BhuNaksha[Bhu-Naksha - Cadastral Vector GIS]
        IGRSBihar[Bhumi Jankari - Registered Deeds & MVR]
        Parimarjan[Parimarjan Plus - Rectification Tracker]
        eCourts[District Courts & High Court Litigation]
        CERSAI[CERSAI Hypothecation Registry]
    end

    subgraph Persistence Layer
        PostgreSQL[(PostgreSQL Relational DB - Master Ledger)]
        PostGIS[(PostGIS Spatial DB - Cadastral Parcel Geometries)]
        DocStorage[(Encrypted Object Storage - Local / MinIO / S3)]
        RedisCache[(Redis - Session & Query Caching)]
    end

    Client Layer --> Gateway
    Gateway --> Auth
    Gateway --> AuditMiddleware
    AuditMiddleware --> Core Application Services

    Core Application Services --> Persistence Layer
    DocService --> OCRWorker
    OCRWorker --> KaithiModel
    ParcelService --> ScraperPool
    ScraperPool --> External Data Sources

    AminDispatch <--> MobileAmin
    AIAgents <--> MCPAdapter
```

---

## 3. Core Component Responsibilities

### 3.1 Property & Parcel Resolution Service (`ParcelService`)
* **Objective:** Disambiguate incomplete user queries into stable, canonical `property_id` entities.
* **Mechanism:**
  - Evaluates combinations of District, Circle, Halka, Mauza, Khata, Khesra (Plot), Jamabandi, or Deed Number.
  - Matches spatial coordinates (lat/long) against PostGIS cadastral polygon boundaries.
  - Returns a list of candidate parcels with matching confidence scores and basis of match (e.g. `Exact Khesra Match`, `Fuzzy Name Match`).
  - *Never* merges candidate properties automatically when ambiguity exists.

### 3.2 Document Intelligence & OCR Pipeline (`DocService` & `OCRWorker`)
* **Objective:** Ingest, classify, OCR, and parse land records into structured schema.
* **Key Capabilities:**
  - Ingests PDFs, TIFF scans, and camera uploads from users, scrapers, and field Amins.
  - Validates file integrity, calculates SHA-256 cryptographic digests, and assigns immutable `document_id`.
  - Employs specialized OCR pipelines for modern printed text, Hindi Devanagari, and historical **Kaithi script** (dominant in pre-1970 Bihar revenue records).
  - Preserves page-level bounding boxes linking every extracted field back to the source coordinate.

### 3.3 Evidence & Discrepancy Engine (`ConsistencyService`)
* **Objective:** Cross-examine extracted documents and highlight title inconsistencies.
* **Detection Categories:**
  1. *Name Variance:* Discrepancies between Deed buyer name and Jamabandi Rayat name.
  2. *Area Mismatch:* Discrepancy between Deed area (e.g. 10 Katha) and Jamabandi recorded Rakba (e.g. 8 Katha).
  3. *Plot Boundary Clashes:* Discrepancy between deed boundary descriptions (Chauhaddi) and Bhu-Naksha neighboring plots.
  4. *Broken Chain of Title:* Missing link between current seller and original recorded ancestor.
  5. *Unresolved Mortgage / MODT:* Active loan charge recorded on CERSAI with no registered release deed on record.
  6. *Pending Rectification:* Active dispute lodged on Parimarjan Plus.

### 3.4 Property Passport & Audit Ledger (`PassportService`)
* **Objective:** A persistent living workspace for each resolved parcel.
* **Contents:**
  - Complete history of verified deeds, mutations, tax receipts, and survey sketches.
  - Historical chronological timeline.
  - Active discrepancy ledger with review statuses (`Open`, `Under Field Verification`, `Resolved`).
  - Audit trail logging every retrieval, OCR pass, and manual reviewer decision.

### 3.5 LandAmin Field Verification Operations (`AminDispatch`)
* **Objective:** Bridge the gap between digital data and ground reality.
* **Workflow:**
  - When a discrepancy cannot be reconciled digitally (e.g. physical boundary encroachment or unregistered partition), a `VerificationTask` is generated.
  - Dispatches task to authorized local LandAmin.
  - Mobile client allows Amin to capture boundary GPS points, photograph physical possession markers, verify seller's identity with village elders, and upload signed Panchayati partition panchnamas.
  - Amin findings are linked as primary physical evidence in the Property Passport.

### 3.6 Agent MCP Server (`MCPAdapter`)
* **Objective:** Provide a secure, read-only AI agent integration layer compatible with Anthropic, Google, and OpenAI agent frameworks.
* **Exposed Tools:**
  - `resolve_property`: Resolve parcel candidates.
  - `get_ownership`: Fetch verified owner and mutation chain.
  - `get_encumbrances`: Query mortgages, liens, and charges.
  - `list_transactions`: Query registered sale/gift/partition transactions.
  - `search_litigation`: Query pending court matters on parcel/parties.
  - `get_land_classification`: Query agricultural vs. commercial zoning.
  - `get_source_document`: Download certified PDF of issued government record.
