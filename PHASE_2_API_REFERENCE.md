# BHUMISETU — PHASE 2 REST API REFERENCE
**Document Code:** BS-API-REF-V1.1  
**Version:** 1.1.0  
**Base URL:** `/api/v1`  
**Authentication Scheme:** HTTP Bearer JWT  
**Format:** JSON (UTF-8)  
**Status:** IMPLEMENTED & PRODUCTION READY  

---

## 1. Global API Architecture & Contract

### 1.1 Authentication & Multi-Tenancy Headers
All endpoints (except `/api/v1/auth/token` and `/health`) require an `Authorization` header containing a valid signed JWT:
```http
Authorization: Bearer <access_token>
```
The token payload contains:
- `sub`: User UUID
- `tid`: Tenant/Organization UUID (`org_id`)
- `role`: User Role (`ADMIN`, `CASE_OPERATOR`, `FIELD_EXPERT`, `LEGAL_REVIEWER`, `REVIEWER`)
- `exp`: Expiry timestamp

**Strict Tenant Scoping:** The backend extracts `tid` from the token and verifies that every queried or modified domain object belongs to that tenant. Cross-tenant access attempts immediately yield HTTP 403.

### 1.2 Request Tracing & Audit Context
Every request is stamped with a UUID request ID:
- Client can optionally pass `X-Request-ID: <uuid>`
- If omitted, middleware generates a new UUID
- Response always includes `X-Request-ID: <uuid>` header

### 1.3 Uniform Error Contract
Errors never return raw Python tracebacks. Every error adheres strictly to:
```json
{
  "code": "STRING_ERROR_CODE",
  "message": "Human-readable description of error.",
  "details": {},
  "request_id": "b3e39074-d45a-4b08-b19b-6ebec647f123"
}
```

| HTTP Status | Error Code | Description |
| :--- | :--- | :--- |
| `400 Bad Request` | `STATE_TRANSITION_ERROR` | Case state machine transition violated or pre-conditions unmet |
| `400 Bad Request` | `DOMAIN_VALIDATION_ERROR`| Action does not belong to finding, or domain integrity failed |
| `401 Unauthorized` | `AUTHENTICATION_FAILED` | Missing, expired, or invalid credentials |
| `403 Forbidden` | `CROSS_TENANT_ACCESS_DENIED` | Request attempted to access another organization's records |
| `403 Forbidden` | `FORBIDDEN` | User role lacks sufficient permissions for operation |
| `404 Not Found` | `ENTITY_NOT_FOUND` | Specified entity ID does not exist |
| `422 Unprocessable` | `VALIDATION_ERROR` | Schema mismatch or invalid payload structure |
| `500 Server Error` | `INTERNAL_SERVER_ERROR` | Unexpected server condition |

---

## 2. API Endpoint Catalog

---

### 2.1 Authentication

#### `POST /auth/token`
Authenticate user credentials and receive JWT access token.
- **Access:** Public
- **Request Body:**
  ```json
  {
    "email": "operator@bhumisetu-demo.local",
    "password": "DemoPassword123!"
  }
  ```
- **Response `200 OK`:**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
    "token_type": "bearer",
    "expires_in_minutes": 1440,
    "user_id": "96b3f6ee-b258-4388-b27b-11740f82a889",
    "tenant_id": "df0dde78-b73e-4167-a9fa-0ccd5b914c5b",
    "role": "CASE_OPERATOR"
  }
  ```

#### `GET /auth/me`
Retrieve currently authenticated user profile.
- **Access:** Authenticated
- **Response `200 OK`:**
  ```json
  {
    "user_id": "96b3f6ee-b258-4388-b27b-11740f82a889",
    "org_id": "df0dde78-b73e-4167-a9fa-0ccd5b914c5b",
    "full_name": "DEMO_DATA: Case Desk Operator",
    "email": "operator@bhumisetu-demo.local",
    "phone_number": "9800000002",
    "role": "CASE_OPERATOR",
    "is_active": true
  }
  ```

---

### 2.2 Cases

#### `POST /cases`
Create a new land due-diligence verification case.
- **Access:** `ADMIN`, `CASE_OPERATOR`
- **Request Body:**
  ```json
  {
    "primary_client_party_id": "c138d6fc-31c3-4886-9a28-98e945c3d402",
    "target_transaction_type": "PURCHASE",
    "initial_parcel_id": "4029d20c-c76a-4ba4-9a67-9bf4070a2f7c"
  }
  ```
- **Response `201 Created`:**
  ```json
  {
    "case_id": "2249de60-706f-4cb1-8012-70b921319208",
    "org_id": "df0dde78-b73e-4167-a9fa-0ccd5b914c5b",
    "case_number": "BS-JH-2026-38291",
    "primary_client_party_id": "c138d6fc-31c3-4886-9a28-98e945c3d402",
    "assigned_amin_id": null,
    "assigned_advocate_id": null,
    "status": "DRAFT",
    "transaction_readiness_state": "NOT_READY",
    "target_transaction_id": null,
    "linked_parcel_ids": ["4029d20c-c76a-4ba4-9a67-9bf4070a2f7c"]
  }
  ```

#### `GET /cases`
List all verification cases for the authenticated tenant.
- **Access:** Authenticated
- **Response `200 OK`:** Array of `CaseResponse`

#### `GET /cases/{case_id}`
Retrieve detailed case file by ID. Enforces tenant barrier.
- **Access:** Authenticated (Tenant-scoped)
- **Response `200 OK`:** `CaseResponse`

#### `PATCH /cases/{case_id}`
Assign professional reviewers (Amin, Legal Advocate).
- **Access:** `ADMIN`, `CASE_OPERATOR`
- **Request Body:**
  ```json
  {
    "assigned_amin_id": "31b67e72-23c4-4b51-9bf5-1994b633017a",
    "assigned_advocate_id": "8902cd38-b74f-4a02-86ec-35d64234081c"
  }
  ```

#### `POST /cases/{case_id}/transition`
Execute an explicit, auditable state machine transition.
- **Access:** `ADMIN`, `CASE_OPERATOR`, `LEGAL_REVIEWER`
- **Allowed Graph Transitions:**
  - `DRAFT` → `PROPERTY_IDENTIFIED` (Requires at least 1 linked parcel)
  - `PROPERTY_IDENTIFIED` → `DATA_COLLECTION`, `BLOCKED`, `CANCELLED`
  - `DATA_COLLECTION` → `DOCUMENT_COLLECTION`, `DATA_UNAVAILABLE`, `CANCELLED`
  - `DOCUMENT_COLLECTION` → `PROCESSING`, `DATA_UNAVAILABLE`, `CANCELLED`
  - `PROCESSING` → `ANALYSIS`, `CONFLICTING_DATA`, `CANCELLED`
  - `ANALYSIS` → `VERIFICATION_REQUIRED`, `LEGAL_REVIEW`, `CONFLICTING_DATA`, `CANCELLED`
  - `VERIFICATION_REQUIRED` → `FIELD_VERIFICATION`, `BLOCKED`, `CANCELLED`
  - `FIELD_VERIFICATION` → `LEGAL_REVIEW`, `BLOCKED`, `CANCELLED`
  - `LEGAL_REVIEW` → `REPORT_DRAFT`, `BLOCKED`, `CANCELLED`
  - `REPORT_DRAFT` → `REPORT_REVIEW`, `CANCELLED`
  - `REPORT_REVIEW` → `FINAL`, `LEGAL_REVIEW`, `CANCELLED`
- **Request Body:**
  ```json
  {
    "next_status": "PROPERTY_IDENTIFIED",
    "transition_reason": "Parcel boundary and khesra verified."
  }
  ```

#### `POST /cases/{case_id}/parcels`
Associate an enduring Parcel with a Case.
- **Request Body:**
  ```json
  {
    "parcel_id": "4029d20c-c76a-4ba4-9a67-9bf4070a2f7c",
    "is_primary": true
  }
  ```

#### `POST /cases/{case_id}/evidence`
Attach an existing, reusable Evidence record from the Evidence Vault to the Case.
- **Request Body:**
  ```json
  {
    "evidence_id": "28f15865-bf1f-4eef-8956-fdc093d75c37"
  }
  ```

#### `GET /cases/{case_id}/claims`
Retrieve all epistemic claims generated for this case.
- **Response `200 OK`:** Array of `ClaimResponse`

#### `GET /cases/{case_id}/findings`
Retrieve all deterministic discrepancy findings and statutory hazards.
- **Response `200 OK`:** Array of `FindingResponse`

---

### 2.3 Parcels

#### `POST /parcels`
Register an enduring parcel into the tenant's land registry.
- **Request Body:**
  ```json
  {
    "state_code": "JH",
    "district_name": "Deoghar",
    "subdistrict_anchal_name": "Mohanpur",
    "halka_number": "04",
    "mauza_village_name": "Chopamo",
    "census_village_code": "364000",
    "khata_number": "12",
    "plot_khesra_number": "542",
    "subdivision_hissa_number": null,
    "recorded_area_acres": 1.5000,
    "land_nature": "AGRICULTURAL_RAIYATI"
  }
  ```
- **Response `201 Created`:**
  ```json
  {
    "parcel_id": "4029d20c-c76a-4ba4-9a67-9bf4070a2f7c",
    "org_id": "df0dde78-b73e-4167-a9fa-0ccd5b914c5b",
    "bhumi_id": "JH-DEO-364000-542-E7A1",
    "state_code": "JH",
    "district_name": "Deoghar",
    "subdistrict_anchal_name": "Mohanpur",
    "halka_number": "04",
    "mauza_village_name": "Chopamo",
    "census_village_code": "364000",
    "khata_number": "12",
    "plot_khesra_number": "542",
    "recorded_area_acres": 1.5,
    "land_nature": "AGRICULTURAL_RAIYATI",
    "centroid_point": null,
    "authoritative_boundary": null
  }
  ```

#### `GET /parcels/{parcel_id}`
Retrieve parcel by ID.

#### `GET /parcels/{parcel_id}/cases`
Get list of verification cases cross-referencing this parcel.

#### `POST /parcels/relationships`
Establish parcel lineage (subdivision, merger, renumbering, correction).
- **Request Body:**
  ```json
  {
    "parent_parcel_id": "4029d20c-c76a-4ba4-9a67-9bf4070a2f7c",
    "child_parcel_id": "59a8c174-8742-4f36-9b40-2092e0719812",
    "relationship_type": "SUBDIVIDED_TO",
    "effective_date": "2024-02-15",
    "mutation_order_reference": "MUT-DEO-2024-4091"
  }
  ```

---

### 2.4 Documents

#### `POST /cases/{case_id}/documents`
Upload physical document (PDF/TIFF/JPEG). Computes SHA-256 hash, creates immutable document record in vault, and automatically associates corresponding Evidence object to the case.
- **Content-Type:** `multipart/form-data`
- **Form Fields:**
  - `file`: Raw binary document
  - `document_type`: `REGISTERED_DOCUMENT` or `GOVERNMENT_RECORD`
- **Response `201 Created`:**
  ```json
  {
    "document_id": "5b4d75f2-959c-469b-b5d1-cc0cbdf138e4",
    "original_filename": "registered_deed_1985.pdf",
    "mime_type": "application/pdf",
    "file_size_bytes": 1048576,
    "storage_uri": "file:///storage/documents/e3b0c442...pdf",
    "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "processing_status": "UPLOADED"
  }
  ```

#### `GET /documents/{document_id}`
Retrieve immutable document metadata and cryptographic verification hash.

---

### 2.5 Evidence Vault

#### `POST /evidence`
Register a reusable evidence object directly in the vault.
- **Request Body:**
  ```json
  {
    "evidence_type": "GOVERNMENT_RECORD",
    "authority_tier": "REVENUE_RECORD",
    "source_name": "Certified Revenue Register Panji II",
    "storage_uri": "mock://documents/certified_panji_ii.pdf",
    "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "metadata": {"circle": "Mohanpur", "khatiyan": "Cadastral"}
  }
  ```

#### `GET /evidence/{evidence_id}`
Retrieve evidence record.

---

### 2.6 Claims

#### `POST /claims`
Assert an atomic Claim. Supports epistemic metrics and temporal validity.
- **Request Body:**
  ```json
  {
    "case_id": "2249de60-706f-4cb1-8012-70b921319208",
    "parcel_id": "4029d20c-c76a-4ba4-9a67-9bf4070a2f7c",
    "evidence_id": "28f15865-bf1f-4eef-8956-fdc093d75c37",
    "subject_entity_type": "PARCEL",
    "subject_id": "4029d20c-c76a-4ba4-9a67-9bf4070a2f7c",
    "predicate": "RECORDED_OWNER",
    "object_value": {
      "owner_name": "DEMO_DATA: Suresh Marandi",
      "khata_number": "12",
      "raiyati_nature": "Pradhani Raiyati"
    },
    "authority_tier": "REVENUE_RECORD",
    "confidence_score": 0.98,
    "recorded_at": "1985-06-12T00:00:00Z",
    "effective_from": "1985-06-12",
    "status": "ACTIVE"
  }
  ```

---

### 2.7 Findings, Actions & Resolutions

#### `POST /findings`
Register an automated or reviewer-identified finding.
- **Request Body:**
  ```json
  {
    "case_id": "2249de60-706f-4cb1-8012-70b921319208",
    "parcel_id": "4029d20c-c76a-4ba4-9a67-9bf4070a2f7c",
    "rule_id": "LEGAL_RULE_JH_SPT_SEC_20",
    "severity": "CRITICAL",
    "status": "OPEN",
    "observed_values": {"district": "Deoghar", "record_holder_caste": "ST"},
    "explanation": "Tribal Raiyati holding subject to Section 20 SPT Act 1949 statutory restriction.",
    "recommended_action": "Verify if Deputy Commissioner permission exists."
  }
  ```

#### `POST /findings/{finding_id}/actions`
Prescribe a concrete operational task to remediate or investigate a finding.
- **Request Body:**
  ```json
  {
    "action_type": "STATUTORY_CLEARANCE_VERIFICATION",
    "assigned_role": "LEGAL_ADVOCATE"
  }
  ```

#### `POST /findings/{finding_id}/resolve`
Resolve a finding with verifiable evidence proof.
- **Rule:** A finding cannot be resolved without specifying `action_id`, `resolving_evidence_id`, and `reviewer_party_id`.
- **Request Body:**
  ```json
  {
    "action_id": "119f9bd9-28a3-46e0-a97a-8a842268762e",
    "resolving_evidence_id": "28f15865-bf1f-4eef-8956-fdc093d75c37",
    "reviewer_party_id": "c138d6fc-31c3-4886-9a28-98e945c3d402",
    "resolution_outcome": "RESOLVED_STATUTORY_PERMISSION_VERIFIED",
    "notes": "Verified certified DC Revenue Permission Order No. 441/1985."
  }
  ```

---

### 2.8 Grounded AI Land Expert (Read-Only)

#### `POST /cases/{case_id}/ai/query`
Query the Grounded AI Land Expert on a specific case.
- **Contract:** Adheres strictly to the 6-point evidence grounding contract. Strictly read-only; canonical data mutation is prohibited.
- **Request Body:**
  ```json
  {
    "query": "Is there any active statutory title defect on this property?"
  }
  ```
- **Response `200 OK`:**
  ```json
  {
    "engine": "BHUMISETU_GROUNDED_AI_EXPERT_V1",
    "mode": "MOCK_AI",
    "case_id": "2249de60-706f-4cb1-8012-70b921319208",
    "query": "Is there any active statutory title defect on this property?",
    "answer": "[AI Land Expert Response - Mode: MOCK_AI]\nCase: BS-JH-2026-38291 (PROPERTY_IDENTIFIED)...",
    "grounding_contract": {
      "evidence_citations": [
        {
          "citation_source": "Certified Revenue Register Panji II",
          "evidence_type": "GOVERNMENT_RECORD",
          "authority_tier": "REVENUE_RECORD",
          "verbatim_excerpt": "Certified legal extract on record.",
          "date_of_record": "2026-09-22T18:05:00Z",
          "extraction_confidence": 0.95
        }
      ],
      "active_contradictions": [],
      "read_only": true,
      "canonical_mutation_permitted": false
    }
  }
  ```
