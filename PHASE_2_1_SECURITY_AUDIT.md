# BHUMISETU — PHASE 2.1 SECURITY & DATA MINIMIZATION AUDIT
**Document Code:** BS-AUDIT-SEC-V1.1  
**Date:** September 2026  
**Auditor:** Principal Security & Compliance Architect  
**Authoritative Reference:** `BHUMISETU_ARCHITECTURE_BLUEPRINT_V1.1.md`  

---

## 1. Adversarial Tenant Isolation Verification

Multi-tenancy in BhumiSetu is enforced server-side at the data-access layer. The backend never relies on client-side or frontend filtering. Every API endpoint extracts the tenant identifier (`tid`) from the cryptographically verified JWT token and validates that the requested resource belongs to that organization.

### Adversarial Test Matrix (Validated in `tests/test_security.py`)

| Adversarial Attack Scenario | Endpoint Target | Attacker Context | Result | HTTP Status | Error Code |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Cross-Tenant Case Read** | `GET /api/v1/cases/{case_b_id}` | User from Tenant A | **REJECTED** | `403 Forbidden` | `CROSS_TENANT_ACCESS_DENIED` |
| **Cross-Tenant Parcel Read** | `GET /api/v1/parcels/{parcel_b_id}`| User from Tenant A | **REJECTED** | `403 Forbidden` | `CROSS_TENANT_ACCESS_DENIED` |
| **Cross-Tenant Document Injection** | `POST /api/v1/cases/{case_b_id}/documents` | User from Tenant A | **REJECTED** | `403 Forbidden` | `CROSS_TENANT_ACCESS_DENIED` |
| **Cross-Tenant Claim Forgery** | `POST /api/v1/claims` (on Case B) | User from Tenant A | **REJECTED** | `403 Forbidden` | `CROSS_TENANT_ACCESS_DENIED` |
| **Cross-Tenant Evidence Linking** | `POST /api/v1/cases/{case_b_id}/evidence` | User from Tenant A | **REJECTED** | `403 Forbidden` | `CROSS_TENANT_ACCESS_DENIED` |
| **Unauthenticated Request** | `GET /api/v1/cases` | Anonymous (No Token) | **REJECTED** | `401 Unauthorized` | `AUTHENTICATION_FAILED` |

---

## 2. Security Controls & Vulnerability Defenses

| Security Dimension | Implemented Defense Mechanism | Verification & Hardening Status |
| :--- | :--- | :--- |
| **Password Hashing** | Bcrypt with dynamic salting (`bcrypt.gensalt()`). Plaintext passwords are never stored or logged. | **VERIFIED** |
| **JWT Session Security** | HMAC-SHA256 (`HS256`) tokens with explicit expiration timestamps (`exp`), issued timestamp (`iat`), user UUID (`sub`), and tenant UUID (`tid`). | **VERIFIED** |
| **SQL Injection Defense** | 100% of queries execute via SQLAlchemy 2.0 ORM using parameterized bind values. Zero string interpolation in SQL statements. | **VERIFIED** |
| **Input Validation** | Pydantic v2 typed models validate all incoming request bodies. Schema mismatches return structured HTTP 422 errors. | **VERIFIED** |
| **Mass Assignment Protection** | Request schemas strictly separate updateable fields from protected identifiers (`org_id`, `created_at`, `status`). | **VERIFIED** |
| **Path Traversal Protection** | Uploaded documents are stored using their content-derived SHA-256 hex string as the filename (`<sha256>.ext`). User-supplied filenames are never used in local filesystem paths. | **VERIFIED** |
| **Document Immutability** | Storage paths are append-only. Once written, files are never overwritten. Hashes are verified upon retrieval. | **VERIFIED** |
| **Private Object Access** | Document storage is restricted. Public S3 bucket access is explicitly prohibited; time-limited signed URLs are mandated for all downloads. | **VERIFIED** |
| **Audit Log Integrity** | Append-only `audit_logs` table records actor identity, action type, entity mutated, previous state, new state, client IP, and UTC timestamp. | **VERIFIED** |

---

## 3. Party Data Minimization & Statutory Compliance Audit

### 3.1 Mandate & Finding
The Phase 2.1 mandate strictly prohibits creating a broad caste or community profiling engine. Sensitive attributes may only be retained where legally necessary for a defined statutory land-rule workflow.

### 3.2 Lawful Statutory Purpose Analysis
In Jharkhand and Bihar, specific land tenancy legislation imposes absolute restrictions on land transfers:
1. **Santhal Parganas Tenancy (SPT) Act, 1949 — Section 20:**
   - Prohibits transfer of Raiyati holdings belonging to an **aboriginal / Scheduled Tribe (ST)** by sale, gift, mortgage, or lease. Any such transfer is legally void *ab initio*.
2. **Chota Nagpur Tenancy (CNT) Act, 1908 — Section 46:**
   - Restricts transfer of land by members of **Scheduled Tribes** (only to another ST member within the same police station) and **Scheduled Castes (SC)**.

### 3.3 Data Minimization Policy Enforced in BhumiSetu
- **Removed from Active Scope:** Generic caste categories such as `OBC`, sub-castes, gotras, or community profiling for marketing, recommendations, or ranking are **PROHIBITED**.
- **Minimized Attribute:** Retained only `is_tribal: bool` and `community_caste_category` strictly restricted to `GENERAL`, `SC`, and `ST`.
- **Purpose Limitation:** This attribute is exclusively consumed by the versioned legal rule engine (`evaluate_spt_act_section_20`).
- **Access Control:** Restricted to certified Legal Reviewers and System Administrators.
- **Retention & Provenance:** Grounded strictly in certified Khatiyan records or revenue Jamabandi extracts; never inferred by AI or demographic estimation.

---

## 4. Append-Only Audit Logging Audit

All state-changing operations trigger an immutable record in `audit_logs`:
1. `CASE_STATUS_TRANSITION`: Logs previous case status, new case status, reason, actor, and IP address.
2. `CREATE_FINDING`: Logs rule identifier, severity, and triggering telemetry.
3. `CREATE_REQUIRED_ACTION`: Logs assigned professional role and action type.
4. `RESOLVE_FINDING`: Logs resolving evidence identifier, sign-off reviewer, outcome, and explanatory notes.

The audit log is append-only with no API endpoints exposed for modification or deletion.
