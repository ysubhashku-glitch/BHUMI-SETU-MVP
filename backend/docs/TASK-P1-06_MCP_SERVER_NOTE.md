# Engineering Implementation Note: TASK-P1-06 Bhumi Setu Agent MCP Server & Governed AI Tool Interface

**Component:** `backend/app/mcp/` (`server.py`, `tools.py`, `auth.py`, `schemas.py`, `__init__.py`), `backend/app/routers/mcp_router.py`, `backend/app/config.py`  
**Status:** Completed & Tested (17/17 Dedicated Tests Passing, 124/124 Full Backend Regression Suite Passing)  
**Date:** October 2026  
**Parent Roadmap Milestone:** Phase 1 — MVP Core: Governed AI Model Context Protocol (MCP) Interface

---

## 1. Initial Repository Audit Findings

Prior to implementation, an exhaustive audit was performed across the Bhumi Setu platform and previous milestones:

1. **Existing Application Milestones & Backing Services:**
   - **P1-01 (Revenue Records):** `BiharJamabandiAdapter`, `Parcel`, `Evidence`, `Claim` (khata, khesra, jamabandi, recorded area, raiyat/tenant names, mutation history).
   - **P1-02 (Bhu-Naksha Cadastral Maps):** `BhuNakshaClient`, `Parcel.authoritative_boundary`, spatial cache, geometric area calculation, Bihar bounding envelope validation, revenue-to-map consistency checks.
   - **P1-03 (Document Intelligence & OCR):** `DocumentPipelineService`, `Document`, `DocumentVersion`, `ExtractedField`, line-level OCR with bounding boxes, 4-direction Chauhaddi extractor, human reviewer audit workflow.
   - **P1-04 (LandAmin Field Task Dispatcher):** `FieldVerificationTask`, `amin_service` state machine, GNSS point readings, reported accuracy, ground Chauhaddi, physical possessor observations, road frontage width, photo evidence SHA-256 hashes.
   - **P1-05 (Land Intelligence Report Generator):** `report_assembler.py`, `pdf_report_generator.py`, `report_service.py`, `LandIntelligenceReport`, 8-section report assembly, cryptographic SHA-256 sealing, public token-based verification endpoint.
   - **Security, Auth & Multi-Tenancy:** JWT-based user authentication, role-based access control (`ADMIN`, `CASE_OPERATOR`, `FIELD_SURVEYOR`, `LEGAL_REVIEWER`, `CLIENT_VIEWER`), tenant isolation via `org_id`, and immutable `audit_logs`.

2. **Audit Rule Determinations:**
   - **No Service Duplication:** The MCP layer acts strictly as an adapter. It delegates directly to existing services (`amin_service`, `report_service`, `report_assembler`, `DocumentPipelineService`, `ConsistencyEngine`) and does not re-implement area formulas, OCR parsers, or title logic.
   - **Governed AI Principle:** The MCP server never provides unrestricted access to the database, arbitrary shell commands, or SQL execution endpoints.
   - **Title Sovereignty:** No tool output claims or guarantees legal ownership or certified boundary demarcation. All tools return explicit disclaimers and distinguish source evidence from unreviewed extractions.

---

## 2. Architecture & Data Flow

The Model Context Protocol (MCP) adapter integrates with the existing FastAPI application and domain services without modifying core business rules:

```
+-------------------------------------------------------------+
|                     External AI Client                      |
|       (Claude Desktop, Cursor, Custom Agent Subagent)       |
+-------------------------------------------------------------+
                               |
               MCP Transport (stdio / SSE / HTTP)
                               v
+-------------------------------------------------------------+
|                  Bhumi Setu MCP Server                      |
|                  (`app/mcp/server.py`)                      |
+-------------------------------------------------------------+
                               |
               Authentication & Context Extraction
                 (`app/mcp/auth.py` Principal)
                               v
+-------------------------------------------------------------+
|                Input Validation & Sanitization              |
|        - Schema Validation (Pydantic models)                |
|        - Prompt Injection Sanitization (untrusted text)     |
|        - Tenant Isolation Enforcement (org_id verification) |
|        - RBAC Verification (Role permissions)               |
+-------------------------------------------------------------+
                               |
              Existing Domain Service Handlers
                               v
+-------------------------------------------------------------+
|  `report_service`  |  `amin_service`  |  `report_assembler` |
|  Revenue Records   |  Spatial Cache   |  Document Pipeline  |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|               Storage, Database & Audit Logs                |
|             (SQLAlchemy, SQLite/PostGIS, S3/Local)          |
+-------------------------------------------------------------+
```

---

## 3. SDK & Transport Selection

1. **Official Python MCP SDK (`mcp` 2.x):**
   - The platform uses `mcp==2.3.0` which is compatible with Python 3.10 through 3.14 on Windows and Linux.
   - Leverages `mcp.server.MCPServer` with standard asynchronous tool registration (`@server.tool()`).
2. **Dual Transport Support:**
   - **Local Standard Input/Output (`stdio`):** Ideal for desktop clients such as Claude Desktop or local IDE subagents. The client launches the server as a subprocess (`python -m app.mcp.server --transport stdio`).
   - **Remote HTTP / SSE (`streamable-http` / `sse`):** Designed for networked deployment behind an authenticated reverse proxy or API gateway.
   - **FastAPI HTTP Bridge (`/api/v1/mcp`):** A dedicated REST bridge is mounted directly on the existing FastAPI application (`GET /api/v1/mcp/tools` and `POST /api/v1/mcp/call/{tool_name}`) to allow standard REST-based AI clients to interact with the exact same MCP tool schemas and validation engine.

---

## 4. Governed MCP Tool Catalog (11 Tools)

Tools are organized into four distinct groups. Every tool is governed by strict input schemas, authenticated context, tenant isolation, structured outputs, and statutory disclaimers.

### Group A: Parcel Intelligence (Read-Only)

| Tool Name | Purpose | Required Roles | Key Inputs | Domain Service Delegated To |
|---|---|---|---|---|
| `get_parcel_summary` | Consolidated summary of parcel identity, administrative location, and data availability. | All Authenticated | `parcel_id` (UUID), `auth_token` | `Parcel`, `CaseParcel`, `Evidence`, `Finding`, `FieldVerificationTask` |
| `get_revenue_record_summary` | Persisted Register-II Jamabandi revenue records and khata/plot numbers. | All Authenticated | `parcel_id` (UUID), `auth_token` | `Evidence` (`GOVERNMENT_RECORD`), `Claim` |
| `get_spatial_summary` | Cadastral geometry boundaries, CRS metadata, and topology validation. | All Authenticated | `parcel_id` (UUID), `auth_token` | `Parcel.authoritative_boundary`, spatial calculations, P1-02 cache |
| `get_document_extraction_summary` | OCR extraction results, page bounding boxes, and Chauhaddi boundary schedules. | All Authenticated | `parcel_id` (UUID), `auth_token` | `Document`, `DocumentVersion`, `ExtractedField` (P1-03) |

### Group B: Evidence & Discrepancies (Read-Only)

| Tool Name | Purpose | Required Roles | Key Inputs | Domain Service Delegated To |
|---|---|---|---|---|
| `get_evidence_register` | Authoritative evidence dossier with cryptographic SHA-256 hashes. | All Authenticated | `case_id` (UUID), `parcel_id` (optional), `auth_token` | `Evidence`, `CaseEvidence`, `DocumentStorage` |
| `get_consistency_findings` | Multi-source discrepancies, severity ratings, and required follow-up actions. | All Authenticated | `case_id` (UUID), `parcel_id` (optional), `auth_token` | `Finding`, `RequiredAction`, `Resolution` |

### Group C: Field Verification (Read & State-Changing)

| Tool Name | Type | Purpose | Required Roles | Key Inputs | Domain Service Delegated To |
|---|---|---|---|---|---|
| `get_field_verification_status` | Read-Only | Status of field tasks, GNSS points, and reviewer evaluation. | All Authenticated | `parcel_id` or `case_id` or `task_id`, `auth_token` | `FieldVerificationTask` |
| `create_field_verification_request` | **State-Changing** | Dispatch a new field survey task to resolve land discrepancies. | `ADMIN`, `CASE_OPERATOR`, `LEGAL_REVIEWER` | `case_id`, `parcel_id`, `priority`, `activities`, `auth_token` | `amin_service.create_task()`, `AuditLog` |

### Group D: Land Intelligence Reports (Read & State-Changing)

| Tool Name | Type | Purpose | Required Roles | Key Inputs | Domain Service Delegated To |
|---|---|---|---|---|---|
| `get_report_metadata` | Read-Only | Retrieve report lifecycle status, versioning, and section summaries. | All Authenticated | `report_id` or `case_id`, `auth_token` | `LandIntelligenceReport` |
| `generate_land_intelligence_report` | **State-Changing** | Assemble and generate an immutable 8-section PDF report with SHA-256 seal. | `ADMIN`, `CASE_OPERATOR`, `LEGAL_REVIEWER` | `case_id`, `parcel_id`, `auth_token` | `report_service.generate_report()`, `report_assembler`, `AuditLog` |
| `verify_report_integrity` | Read-Only (Public) | Cryptographically verify report authenticity against stored disk artifact. | Public / Any | `verification_token` | `report_service.verify_report_by_token()` |

---

## 5. Security & Authentication Model

1. **Bearer Token Authentication:**
   - Every MCP tool (except the public `verify_report_integrity`) requires an authenticated JWT `auth_token`.
   - The token is cryptographically decoded using the application's `SECRET_KEY` and algorithm (`HS256`).
   - The subject UUID is verified against active `User` accounts in the database to prevent stale token reuse.
2. **Tenant Isolation:**
   - User identity contains a mandatory `org_id` (Organization ID).
   - Every database query in tool execution explicitly filters by `org_id == principal.org_id`.
   - If an AI client attempts to request a parcel, case, task, or report belonging to a different tenant, the server immediately raises `CrossTenantAccessError` and returns `PERMISSION_DENIED`.
3. **Role-Based Access Control (RBAC):**
   - Read-only tools permit access to any authorized tenant user (`CLIENT_VIEWER`, `FIELD_SURVEYOR`, `CASE_OPERATOR`, `LEGAL_REVIEWER`, `ADMIN`).
   - State-changing tools (`create_field_verification_request`, `generate_land_intelligence_report`) strictly require `CASE_OPERATOR`, `LEGAL_REVIEWER`, or `ADMIN`.
   - Unauthorized roles are denied with HTTP 403 / MCP `PERMISSION_DENIED`.
4. **Prompt Injection & Untrusted Content Defense:**
   - Scanned land deeds, OCR extractions, Khatiyans, and party statements are untrusted third-party inputs.
   - All extracted strings returned through the MCP layer are sanitized using `sanitize_untrusted_text()`:
     - Strips instruction overrides such as `<SYSTEM>`, `IGNORE PREVIOUS INSTRUCTIONS`, `SYSTEM PROMPT:`, and shell backticks.
     - Enforces max text length (4000 characters per field) to prevent context buffer overflow.
     - Output is encapsulated under structured JSON data fields with explicit provenance metadata.

---

## 6. Audit Trail & State Mutation Governance

1. **Audit Logging:**
   - State mutations (`create_field_verification_request` and `generate_land_intelligence_report`) automatically create immutable entries in the `audit_logs` table.
   - Audit entries record `user_id`, `org_id`, `action` (`MCP_CREATE_FIELD_TASK`, `MCP_GENERATE_REPORT`), `entity_type`, `entity_id`, and full operational metadata.
2. **Idempotency & Workflow Rules:**
   - Field task creation enforces task uniqueness: if an active task (`READY_FOR_ASSIGNMENT`, `ASSIGNED`, `IN_PROGRESS`) already exists for the same parcel and activities, duplicate dispatch is rejected.
   - Report generation respects versioning: generating a new report supersedes previous versions and logs the revision history.
3. **Feature Flag Control:**
   - Environment variable `MCP_ALLOW_STATE_MUTATIONS` (default: `true`) can be toggled to `false` in production to instantly put the entire MCP interface into read-only mode without code deployment.

---

## 7. Configuration & Environment Variables

| Variable | Default Value | Description |
|---|---|---|
| `MCP_ENABLED` | `true` | Enables or disables MCP server registration. |
| `MCP_SERVER_NAME` | `Bhumi-Setu-Intelligence-Server` | Protocol handshake name for MCP discovery. |
| `MCP_TRANSPORT` | `stdio` | Transport mechanism: `stdio`, `sse`, or `streamable-http`. |
| `MCP_HOST` | `127.0.0.1` | Remote transport bind address. |
| `MCP_PORT` | `8001` | Remote transport port. |
| `MCP_ALLOW_STATE_MUTATIONS` | `true` | Governs whether state-changing tools are exposed. |

---

## 8. Client Connection Guide

### A. Claude Desktop Integration (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "bhumi-setu": {
      "command": "C:\\Users\\ysubh\\OneDrive\\Desktop\\BHUMI SETU\\backend\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "app.mcp.server",
        "--transport",
        "stdio"
      ],
      "env": {
        "DATABASE_URL": "sqlite:///./bhumi_setu.db",
        "SECRET_KEY": "your-development-jwt-secret-key"
      }
    }
  }
}
```

### B. Python Subagent / AI Client Script

```python
import httpx

API_BASE = "http://127.0.0.1:8000/api/v1/mcp"
AUTH_TOKEN = "ey..."  # Valid Bhumi Setu JWT Bearer Token

# 1. Discover Available Tools
tools_resp = httpx.get(f"{API_BASE}/tools")
print("Available MCP Tools:", [t["name"] for t in tools_resp.json()["tools"]])

# 2. Query Parcel Intelligence
payload = {
    "tool_name": "get_parcel_summary",
    "arguments": {
        "parcel_id": "40aa8f7e-7c9b-4e68-98e1-582bb5105eb0",
        "auth_token": AUTH_TOKEN
    }
}
result = httpx.post(f"{API_BASE}/call/get_parcel_summary", json=payload)
print("Parcel Summary:", result.json())
```

---

## 9. Verification & Test Execution Results

A dedicated test suite was implemented in `backend/tests/test_mcp_server.py` containing 17 rigorous unit and integration tests:

| Test Case Name | Coverage Focus | Result |
|---|---|---|
| `test_mcp_server_initialization_and_tool_discovery` | Verifies MCP server startup, tool registry, and all 11 tool registrations. | **PASSED** |
| `test_mcp_tool_schema_validation` | Inspects JSON schemas, required properties, and enum constraints. | **PASSED** |
| `test_mcp_get_parcel_summary` | Validates parcel summary retrieval and legal title disclaimers. | **PASSED** |
| `test_mcp_get_revenue_record_summary` | Validates Jamabandi Register-II records, Khata/Khesra, and area. | **PASSED** |
| `test_mcp_get_spatial_summary` | Validates cadastral boundaries, WGS84 geometries, and CRS validation. | **PASSED** |
| `test_mcp_get_document_extraction_summary` | Validates OCR text, line bounding boxes, and Chauhaddi extraction. | **PASSED** |
| `test_mcp_get_evidence_register` | Validates evidence listing, SHA-256 hashes, and confidential data omission. | **PASSED** |
| `test_mcp_get_consistency_findings` | Validates cross-source discrepancies and severity levels. | **PASSED** |
| `test_mcp_get_field_verification_status` | Validates field survey status, GNSS accuracy, and ground observations. | **PASSED** |
| `test_mcp_state_changing_create_field_verification_request` | Validates field task creation, RBAC authorization, and audit logging. | **PASSED** |
| `test_mcp_state_changing_generate_and_verify_report` | Validates PDF generation, SHA-256 seal, and cryptographic verification. | **PASSED** |
| `test_mcp_unauthenticated_request_fails_closed` | Confirms missing/invalid tokens fail closed with 401 Unauthorized. | **PASSED** |
| `test_mcp_cross_tenant_access_denied` | Confirms cross-tenant parcel access is strictly forbidden (403). | **PASSED** |
| `test_mcp_unauthorized_role_denied_mutation` | Confirms viewer roles cannot trigger report generation or task creation. | **PASSED** |
| `test_mcp_prompt_injection_sanitization` | Confirms prompt injection attempts in OCR text are neutralized. | **PASSED** |
| `test_mcp_http_router_tools_list` | Tests FastAPI REST route `GET /api/v1/mcp/tools`. | **PASSED** |
| `test_mcp_http_router_call_tool` | Tests FastAPI REST route `POST /api/v1/mcp/call/{tool_name}`. | **PASSED** |

### Complete Backend Regression Execution

- **Command:** `.\.venv\Scripts\python -m pytest`
- **Result:** **124 passed in 46.28s** (107 existing upstream tests + 17 new MCP tests).
- **Regressions:** 0.

---

## 10. Deployment Checklist

- [x] Python MCP SDK installed (`mcp>=1.2.0,<=2.3.0`).
- [x] Configuration parameters bound in `app/config.py`.
- [x] All 11 tools registered with strictly typed Pydantic input/output schemas.
- [x] Authentication and principal resolution implemented in `app/mcp/auth.py`.
- [x] Multi-tenant isolation verified on all data access paths.
- [x] Role-based access control enforced on mutating actions.
- [x] Prompt injection defense and length sanitization applied.
- [x] Audit logs recorded for field task creation and report generation.
- [x] REST bridge mounted on FastAPI at `/api/v1/mcp`.
- [x] Stdio CLI entry point configured in `app/mcp/server.py`.
- [x] 100% test pass rate across the full 124-test backend test suite.
