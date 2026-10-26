# Bhumi Setu — Reverse-Engineering Landeed & Implementation Blueprint

**Project:** Bhumi Setu (India-Focused Land Intelligence Platform)  
**Investigation Scope:** Deep Empirical Reverse-Engineering of Landeed (`landeed.com`, `web.landeed.com`, `backend.landeed.com`, `bedrock.landeed.com`) and Design of Implementation-Ready Architecture for Bihar  
**Author:** Bhumi Setu Engineering Intelligence  
**Date:** October 24, 2026  
**Status:** Completed & Implementation-Ready  

---

## 1. Directory Structure and Deliverables Index

```
bhumi-setu-reverse-engineering/
├── README.md                                  # Master index and executive synthesis
├── 01-environment-and-rea-audit.md            # REA installation, runtime, tools, and repo audit
├── 02-landeed-product-audit.md                # Comprehensive Landeed product catalog audit
├── 03-observed-user-workflows.md              # Empirical user workflows observed via DevTools
├── 04-ui-and-interaction-inventory.md         # Complete screen, route, form, and component inventory
├── 05-observed-routes-and-integrations.md     # Observed API endpoints, payloads, headers, and MCP spec
├── 06-bihar-land-data-source-registry.md      # Bihar government portal registry and access methods
├── 07-feature-parity-matrix.csv               # Complete CSV parity matrix with evidence citations
├── 08-bhumi-setu-system-architecture.md       # Target system architecture and component blueprints
├── 09-property-data-model.md                  # Entity-relationship diagram & PostGIS DDL schema
├── 10-document-intelligence-design.md         # Document OCR, Kaithi translation, and extraction specs
├── 11-evidence-and-risk-engine.md             # Discrepancy taxonomy, cross-examination, and risk rules
├── 12-property-passport-and-report-design.md  # Property Passport & Land Intelligence Report designs
├── 13-landamin-workflow.md                    # LandAmin field-verification operations & mobile specs
├── 14-mvp-implementation-plan.md              # 11-step Bihar MVP plan and prioritized backlog
├── 15-security-and-privacy-review.md          # DPDP Act 2023 compliance, SSRF, and prompt-injection defense
└── evidence/
    ├── screenshots/                           # 7 High-resolution empirical screenshots
    │   ├── 01_landeed_web_home.png            # Web app home & Mapbox explorer
    │   ├── 02_landeed_bihar_services.png      # Bihar legal opinion, survey & consultation catalog
    │   ├── 03_landeed_bihar_docs_tools.png    # Bihar Jamabandi, Plot Map, Mutation & MVR catalog
    │   ├── 04_landeed_bihar_jamabandi.png     # Bihar Jamabandi search form and location hierarchy
    │   ├── 05_landeed_land_intelligence.png   # Enterprise Land Intelligence product page
    │   ├── 06_landeed_api_mcp.png             # Landeed API & Terra MCP server specification
    │   └── 07_bihar_bhumi_official_portal.png # Bihar Bhumi government portal homepage
    ├── observations/                          # Raw captured JSON API payloads
    │   ├── landeed_categories_bihar.json      # Dynamic prompt categories for Bihar
    │   └── landeed_feature_flags.json         # Client build and feature configuration flags
    ├── exported-evidence/                     # Traced network payloads and DOM snapshots
    └── diagrams/                              # Rendered architectural and ERD diagrams
```

---

## 2. Key Investigation Breakthroughs

1. **Dual-Rail Fulfillment Reality:** Landeed's "instant" automation applies solely to state databases that are already digital and public (such as Bihar Jamabandi). For non-digitized records, historical deeds (pre-2004), and certified copies, Landeed relies on physical field runners operating out of **LeX lounges and SRO counters across 15 states**.
2. **Terra MCP Server Discovery:** Landeed's enterprise AI architecture exposes an official **Model Context Protocol (MCP)** server with 8 read-only tools (`resolve_property`, `check_coverage`, `get_ownership`, `get_encumbrances`, `list_transactions`, `search_litigation`, `get_land_classification`, `get_source_document`), strictly isolating reasoning from state-changing procurement APIs.
3. **Bihar Government Portal Verification:** Empirical HTTP/TLS testing confirmed that 5 out of 6 official Bihar portals (`biharbhumi.bihar.gov.in`, `bhunaksha.bihar.gov.in`, `bhuabhilekh.bihar.gov.in`, `parimarjanplus.bihar.gov.in`, `emapi.bihar.gov.in`) are 100% active and accessible for automated integration. The registration deed portal (`bhumijankari.bihar.gov.in`) suffers from legacy SSL handshake resets, necessitating Bhumi Setu's LandAmin SRO runner network for pre-2006 deed inspection.
4. **Bhumi Setu's Competitive Advantage:** By combining automated revenue ingestion with an institutional **LandAmin** field-verification network and specialized **Kaithi historical script translation**, Bhumi Setu delivers ground-truth verification that purely digital scrapers cannot match.
