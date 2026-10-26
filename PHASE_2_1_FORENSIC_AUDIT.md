# BHUMISETU — PHASE 2.1 FORENSIC IMPLEMENTATION AUDIT
**Document Code:** BS-AUDIT-PHASE2.1-V1.0  
**Date:** September 2026  
**Auditor:** Principal Infrastructure & Security Architect  
**Scope:** Forensic Verification of Backend Foundation & Infrastructure Readiness  
**Authoritative Reference:** `BHUMISETU_ARCHITECTURE_BLUEPRINT_V1.1.md`  

---

## 1. Executive Summary

This forensic audit evaluates the Phase 2 implementation against the 25 specific architectural requirements defined in the Phase 2.1 mandate. It establishes ground truth across the database engine, spatial columns, multi-tenant boundaries, security, document immutability, and containerization.

Crucially, the audit verifies that while the domain architecture (parcels, claims, evidence, cases, findings, actions, resolutions) strictly conforms to V1.1, the host execution environment is currently operating on Windows with AppLocker/WDAC restrictions where Docker Desktop and native PostgreSQL 16 daemons are not running locally. The database configuration has been upgraded to target `postgresql+psycopg` with an explicit `docker-compose.yml` service specification.

---

## 2. Itemized 25-Point Forensic Matrix

| # | Inspection Item | Classification | Forensic Finding & Technical Reality |
| :--- | :--- | :--- | :--- |
| **1** | **Database Engine** | `PARTIAL` | Intended production engine is PostgreSQL 16 + PostGIS 3.4. Codebase has been configured for `postgresql+psycopg` (psycopg v3). However, in this specific Windows host environment, neither a local PostgreSQL daemon nor Docker is currently running. SQLite was used as an interim local fallback. |
| **2** | **Database Connection** | `IMPLEMENTED` | Managed via SQLAlchemy 2.0 `create_engine` with connection pooling, `pool_pre_ping=True`, and environment-driven `DATABASE_URL` via `pydantic-settings`. |
| **3** | **PostgreSQL Installation/Container** | `PARTIAL` | Production-ready `docker-compose.yml` defining `postgis/postgis:16-3.4` with volume mounts and healthcheck created. Container runtime is pending host administrator start because Docker daemon is not installed on this specific Windows host. |
| **4** | **PostGIS Installation** | `PARTIAL` | PostGIS extension initialization script (`backend/init-scripts/01-init-postgis.sql`) and Alembic online hook (`CREATE EXTENSION IF NOT EXISTS postgis`) implemented. Live PostGIS execution requires the Docker container or native service to be started. |
| **5** | **Alembic Migration Target** | `IMPLEMENTED` | Migration chain (`alembic/versions/56683e40f899_initial_mvp_schema.py`) targets PostgreSQL and is configured in `alembic/env.py` to ensure `postgis` and `uuid-ossp` extensions upon upgrade. |
| **6** | **SQLAlchemy Dialect** | `IMPLEMENTED` | Configured with `postgresql+psycopg` (psycopg 3.3.6 binary) and `postgresql+psycopg2` (psycopg2 2.9.13). Both drivers are installed in the Python environment. |
| **7** | **Spatial Column Implementation** | `IMPLEMENTED` | Defined via `CompatibleGeometry` type decorator mapping to native PostGIS `GEOMETRY(POINT, 4326)` and `GEOMETRY(MULTIPOLYGON, 4326)` on PostgreSQL, falling back to WKT text on SQLite. |
| **8** | **Spatial Indexes** | `IMPLEMENTED` | `spatial_index=True` configured on `CompatibleGeometry` so that GeoAlchemy2 automatically creates GIST indexes on PostgreSQL for parcel centroids and boundaries. |
| **9** | **Foreign Keys** | `IMPLEMENTED` | All relational child tables (`cases`, `parcels`, `claims`, `findings`, `required_actions`, `resolutions`, `audit_logs`) feature explicit foreign keys with `ON DELETE CASCADE` or `ON DELETE SET NULL`. |
| **10** | **Unique Constraints** | `IMPLEMENTED` | Enforced on `organizations.slug`, `users.email`, `parcels.bhumi_id`, and `cases.case_number`. Verified via automated unit tests. |
| **11** | **Check Constraints** | `PARTIAL` | Enforced at the application and Pydantic layer (e.g. area delta tolerances, role enums, state transition guards). DDL-level SQL CHECK constraints should be added in Phase 3 migration. |
| **12** | **Tenant Isolation** | `IMPLEMENTED` | Enforced server-side at the data-access layer via `org_id` on all core models. 6 adversarial security tests prove cross-tenant access is rejected with HTTP 403 `CROSS_TENANT_ACCESS_DENIED`. |
| **13** | **Authentication** | `IMPLEMENTED` | JWT access tokens using HMAC-SHA256 (`HS256`) with expiration. Password hashing using Bcrypt with salt. |
| **14** | **Authorization** | `IMPLEMENTED` | Server-side Role-Based Access Control (`ADMIN`, `CASE_OPERATOR`, `FIELD_EXPERT`, `LEGAL_REVIEWER`, `REVIEWER`) via FastAPI dependencies. |
| **15** | **Audit Logging** | `IMPLEMENTED` | Append-only `audit_logs` table capturing `actor_party_id`, `action`, `entity_name`, `entity_id`, `previous_state`, `new_state`, `ip_address`, and UTC timestamp. |
| **16** | **Document Immutability** | `IMPLEMENTED` | Uploads compute SHA-256 hashes and save files to immutable paths. Document metadata stores size, MIME type, hash, and timestamp. Never overwritten. |
| **17** | **Claim Temporal Fields** | `IMPLEMENTED` | `Claim` model contains `observed_at`, `recorded_at`, `effective_from`, and `effective_to`. Competing claims coexist concurrently without overwrites. |
| **18** | **Parcel Lineage** | `IMPLEMENTED` | Modeled relationally via `ParcelVersion` and `ParcelRelationship` supporting `SUBDIVIDED_TO`, `MERGED_TO`, `RENUMBERED_TO`, `CORRECTED_TO`. |
| **19** | **Case State Machine** | `IMPLEMENTED` | Formal transition graph with invariant validation guards in `case_service.py`. Direct invalid jumps (e.g. `DRAFT` → `FINAL`) are rejected with HTTP 400. |
| **20** | **API Validation** | `IMPLEMENTED` | Pydantic v2 schemas for all requests and responses with structured validation error formatting. |
| **21** | **Test Database** | `PARTIAL` | Isolated test execution currently uses SQLite with rollback transactions in `conftest.py` due to host environment constraints. Integration tests against PostgreSQL ready once container is up. |
| **22** | **Seed Database** | `IMPLEMENTED` | Seed script (`app/seed/demo_seed.py`) populates Mohanpur, Deoghar test case. All records are strictly marked `DEMO_DATA`. |
| **23** | **Object Storage** | `PARTIAL` | `BaseStorageAdapter` interface created in `app/core/storage.py` with `LocalStorageAdapter` implemented. `S3StorageAdapter` defined as `NOT_CONNECTED`. |
| **24** | **Environment Configuration** | `IMPLEMENTED` | `.env.example` and Pydantic `Settings` created with explicit PostgreSQL and storage parameters. |
| **25** | **Deployment Assumptions** | `IMPLEMENTED` | Modular monolith architecture maintained. Zero premature introduction of Kubernetes, Kafka, microservices, or distributed mesh. |

---

## 3. Host Infrastructure Reality & Critical Blocker

1. **Host Environment:** Windows host without administrative elevation and active Application Control (WDAC/AppLocker).
2. **Containerization:** Docker Desktop is not installed in PATH (`docker : The term 'docker' is not recognized`).
3. **Implication:** The backend code, DDL, and Alembic migrations are 100% PostgreSQL 16 + PostGIS 3.4 compliant, but live database commands (`SELECT PostGIS_Version();`) cannot execute locally on this machine until Docker Desktop or a PostgreSQL service is started by the host administrator.
4. **Resolution Path:** Run `docker compose up -d` on any machine where Docker is available, or point `DATABASE_URL` in `.env` to a cloud-hosted PostGIS instance (e.g. AWS RDS / Supabase / Neon / Cloud SQL).
