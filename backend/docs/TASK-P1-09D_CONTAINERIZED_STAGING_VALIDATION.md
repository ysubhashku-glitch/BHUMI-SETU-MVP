# TASK-P1-09D: Containerized Staging Integration Validation Report

**Document Code:** AGY-P1-09D-CONTAINERIZED-STAGING-VALIDATION-2026-V1  
**Classification:** DevOps / DevSecOps Staging Integration & Pipeline Specification  
**Date:** October 26, 2026  
**Status:** Canonical P1-09D Milestone Deliverable  
**Final Verdict:** `INTEGRATION WORKFLOW IMPLEMENTED — LIVE RUN NOT VERIFIED`

---

## 1. Executive Summary

Previous milestone TASK-P1-09C resolved critical credential desynchronization risks, enforced overwrite protection for `backend/.env`, introduced preflight verification (`verify_config.py`), and established 22 automated configuration tests and 198 backend regression tests. However, a significant validation gap remained: live container execution had not occurred because the local Windows development workstation lacks Docker Desktop and WSL2.

**TASK-P1-09D** bridges this validation gap by implementing a complete, automated containerized staging integration pipeline:
1. **CI/CD Integration Pipeline:** Created `.github/workflows/staging-integration.yml`, a 16-stage GitHub Actions workflow executing on Docker-capable `ubuntu-latest` runners with ephemeral, cryptographically secure non-production credentials, bounded health waits, migration execution, and automatic teardown.
2. **Real-Service Integration Test Suite:** Created `backend/tests/test_containerized_staging_integration.py`, an end-to-end integration test suite specifically designed to validate real container services (PostgreSQL 16 with PostGIS 3.4 spatial queries, Celery background worker consuming from Redis queues, MinIO S3 API put/get with SHA-256 integrity, unauthorized request rejection, and deep application `/health/ready` probe dependencies).
3. **Least-Privilege Identity Architecture:** Documented and evaluated MinIO identity models, implemented `MINIO_DEDICATED_APP_IDENTITY` in `backend/app/config.py` and `scripts/verify_config.py`, and authored `backend/scripts/provision_minio_app_user.sh` for provisioning scoped application users with bucket-restricted readwrite policies.
4. **Deterministic Worker Task:** Added `health_ping_task` and `health_ping_task_logic` in `backend/app/worker.py` to allow live asynchronous task execution and verification through Redis without requiring database mock dependencies.
5. **Idempotent Bucket Provisioning:** Added `ensure_bucket_exists()` in `backend/app/core/storage.py` to prevent `NoSuchBucket` startup exceptions in fresh staging environments.
6. **Persistence & Disaster Recovery Runbooks:** Expanded deployment runbooks to cover live failure diagnosis, in-database SQL user password rotation (`ALTER USER`), PostGIS logical backups (`pg_dump`), MinIO mirroring (`mc mirror`), and Redis snapshots.
7. **Production Readiness Distinction:** Formally defined the boundary between staging integration verification and production enterprise readiness.

---

## 2. Repository Files Inspected

The following repository assets were audited prior to changes:

| Path | Component | Audit Findings |
|---|---|---|
| `docker-compose.staging.yml` | Multi-container Staging Stack | Declares `db` (PostGIS 16-3.4), `redis` (7-alpine), `minio` (RELEASE.2024-05-10), `app` (FastAPI), `worker` (Celery). All administrative ports bound to `127.0.0.1`. |
| `backend/Dockerfile` | Application Container Image | Multi-stage build (`python:3.14-slim`), Astral `uv:0.12.5`, system shared libraries (`libpq5`, `libgeos-c1v5`, `tesseract-ocr`), unprivileged UID 10001 user `bhumisetu`. |
| `backend/app/config.py` | Configuration & Security Gates | Strict secret entropy verification, exposed key blacklisting, database/MinIO parity checks, placeholder rejection. |
| `backend/app/worker.py` | Celery Background Processing | Configures queues `default`, `ocr_queue`, `report_queue`. Supports late acks and structured failure callbacks. |
| `backend/app/core/storage.py` | Document Storage Adapters | Abstract `DocumentStorage` interface with `LocalDocumentStorage`, `S3DocumentStorage`, and `MinioDocumentStorage`. |
| `backend/app/routers/health.py` | Health & Observability Probes | Independent `/health/live` (lightweight process check) and `/health/ready` (evaluates DB, schema, PostGIS, storage, Redis, Celery, and OCR engines). |
| `backend/scripts/migrate.py` | Migration Runner | Programmatic Alembic runner with database wait loops, `upgrade`, `downgrade`, and `check` commands. |
| `backend/init-scripts/01-init-postgis.sql` | PostgreSQL Init | Mounted to `/docker-entrypoint-initdb.d:ro`; initializes `postgis`, `postgis_topology`, and `uuid-ossp`. |
| `backend/tests/test_staging_smoke.py` | E2E Staging Smoke Test | 18-step synthetic workflow currently evaluated using TestClient and SQLite fixtures. |
| `backend/tests/test_storage_s3_minio.py` | Storage Unit Tests | Unit tests using in-memory `MockS3Client`. Did not test real S3 HTTP network calls. |
| `backend/tests/test_celery_worker.py` | Worker Unit Tests | Tested via eager `.apply()` execution. Did not test real background Celery daemon queue consumption. |

---

## 3. Architecture and Dependency Startup Diagram

The diagram below illustrates service dependencies, initialization order, and verification barriers:

```
+-----------------------------------------------------------------------------------+
| STAGE 1: Infrastructure Container Initialization                                  |
|                                                                                   |
|  +-------------------+       +-------------------+       +---------------------+  |
|  |   PostgreSQL 16   |       |      Redis 7      |       |     MinIO Vault     |  |
|  |   + PostGIS 3.4   |       |   (Port 6379)     |       |     (Port 9000)     |  |
|  +---------+---------+       +---------+---------+       +----------+----------+  |
|            |                           |                            |             |
|            | pg_isready                | redis-cli ping             | /health/live|             |
|            v                           v                            v             |
|  [DB Health Gate: OK]         [Redis Health: OK]          [MinIO Health: OK]      |
+------------+---------------------------+----------------------------+-------------+
             |                           |                            |
             v                           |                            |
+--------------------------------+       |                            |
| STAGE 2: Database Migration    |       |                            |
|                                |       |                            |
|  scripts/migrate.py upgrade    |       |                            |
|  (Alembic Head: 001_initial)   |       |                            |
|  Schema & PostGIS Extensions   |       |                            |
+------------+-------------------+       |                            |
             |                           |                            |
             v                           v                            v
+-----------------------------------------------------------------------------------+
| STAGE 3: Application & Background Worker Launch                                    |
|                                                                                   |
|  +-------------------------------------+   +-----------------------------------+  |
|  |     FastAPI Web Gateway ('app')     |   |      Celery Worker ('worker')     |  |
|  |     - SQLAlchemy Connection Pool    |   |      - Listens: default, ocr,     |  |
|  |     - MinIO S3 Evidence Client      |   |        report_queue               |  |
|  |     - Redis Session Cache           |   |      - Executes async OCR/reports |  |
|  +------------------+------------------+   +-----------------+-----------------+  |
|                     |                                        |                    |
|                     v                                        v                    |
|         [GET /health/ready Gate: 200]             [Queue Subscription: Ready]     |
+---------------------+----------------------------------------+--------------------+
                      |                                        |
                      +-------------------+--------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| STAGE 4: Real Container Integration Tests                                         |
|                                                                                   |
|  1. PostgreSQL CRUD & PostGIS Polygon Intersection Queries                        |
|  2. Celery Worker Asynchronous Task Consumption (health_ping_task via Redis)      |
|  3. MinIO S3 Object Upload, Retrieval & SHA-256 Digest Integrity Verification      |
|  4. MinIO Unauthorized Request Rejection (403 Forbidden Gate)                     |
|  5. 18-Step Staging End-to-End Smoke Test                                         |
|  6. Container Restart Volume Persistence Check (staging_pgdata, staging_miniodata)|
+-----------------------------------------------------------------------------------+
```

### Uncovered Dependencies Identified & Resolved

1. **Real PostGIS Extension Execution:** Previously, all migration tests ran on SQLite with mocked geometry. Resolved by `test_live_postgresql_connection_and_postgis_version` querying real PostGIS.
2. **Real Redis Message Queueing & Worker Consumption:** Previously, worker tests ran synchronously in-process via Celery `.apply()`. Resolved by `test_live_celery_worker_task_consumption_and_completion` testing cross-process queue dispatch via Redis broker to Celery worker daemon.
3. **Real MinIO HTTP S3 API Protocol:** Previously, storage tests used `MockS3Client`. Resolved by `test_live_minio_bucket_and_object_lifecycle` performing real HTTP Boto3 requests against MinIO.
4. **Volume Persistence Across Container Restarts:** Previously untested. Resolved by CI stage 14 restarting `db`, `minio`, and `app` containers and verifying volume durability.

---

## 4. CI Integration Workflow Design

The dedicated workflow is located at:
[`.github/workflows/staging-integration.yml`](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/.github/workflows/staging-integration.yml)

### Workflow Pipeline Stages

```yaml
name: Staging Container Integration & Readiness Validation
on: [push, pull_request, workflow_dispatch]
jobs:
  staging-integration-validation:
    runs-on: ubuntu-latest
    timeout-minutes: 25
```

1. **Checkout Repository:** Fetches repository via `actions/checkout@v4`.
2. **Install Astral uv & Python 3.14:** Sets up uv 0.12.5 and pins Python 3.14 runtime.
3. **Host Unit Regression Gate:** Executes `uv run pytest tests -q` on host (all 198 tests must pass).
4. **Generate Ephemeral CI Credentials:** Generates 32-byte hex `SECRET_KEY`, 24-byte hex `POSTGRES_PASSWORD`, and 24-byte hex `MINIO_ROOT_PASSWORD`. Masks them via `::add-mask::` and writes `backend/.env` with `chmod 600`.
5. **Render & Validate Compose Config:** Runs `docker compose -f docker-compose.staging.yml --env-file backend/.env config --quiet`.
6. **Build Container Images:** Executes `docker compose build` for `app` and `worker`.
7. **Start Infrastructure Services:** Boots `db`, `redis`, and `minio` in detached mode.
8. **Bounded Health Verification:** Polls container health status up to 60s timeout until all 3 are `healthy`.
9. **Apply Database Migrations:** Runs `python -m scripts.migrate upgrade` inside the container network.
10. **Start Application & Worker:** Boots `app` and `worker` against migrated schema.
11. **Application Readiness Gate:** Polls `http://127.0.0.1:8000/health/ready` until HTTP 200 is returned.
12. **Execute Live Integration Tests:** Runs `pytest tests/test_containerized_staging_integration.py -v` with `TEST_LIVE_STAGING=1`.
13. **Execute E2E Staging Smoke Test:** Runs 18-step smoke test `pytest tests/test_staging_smoke.py -v`.
14. **Verify Restart Persistence:** Restarts `db`, `minio`, `app`, and re-verifies readiness probe.
15. **Failure Log Harvesting:** On failure, captures sanitized logs (`--tail=50`) from all containers.
16. **Disposable Resource Teardown:** Executes `docker compose down -v --remove-orphans` and deletes ephemeral `backend/.env`.

---

## 5. Security & Least-Privilege Identity Findings

### MinIO Identity Evaluation

In local staging:
- Currently, `app` and `worker` authenticate to MinIO using root credentials (`MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`).
- While acceptable for single-tenant local sandboxes, running applications with storage root credentials violates the principle of least privilege.
- **Remediation Implemented:**
  - Added `MINIO_DEDICATED_APP_IDENTITY` flag to `backend/app/config.py` and `scripts/verify_config.py`.
  - When `MINIO_DEDICATED_APP_IDENTITY=false` (default local staging), root parity is validated to prevent desynchronization.
  - When `MINIO_DEDICATED_APP_IDENTITY=true` (hardened staging/production), the app accepts dedicated scoped credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).
  - Created idempotent provisioning script [backend/scripts/provision_minio_app_user.sh](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/backend/scripts/provision_minio_app_user.sh) using `mc` to configure a dedicated user (`bhumisetu_app`) with a scoped readwrite policy restricted to `arn:aws:s3:::bhumisetu-staging-evidence-vault/*`.

### PostgreSQL Credential Lifecycle

- PostgreSQL container reads `POSTGRES_PASSWORD` only upon initial cluster creation in an empty volume (`staging_pgdata`).
- Subsequent restarts **ignore** changes to `POSTGRES_PASSWORD`.
- Documented live password rotation using `ALTER USER bhumisetu_user WITH PASSWORD '...'` inside the database, followed by synchronizing `.env` and restarting application containers.
- Enforced strict rule: **Persistent volumes must never be deleted to fix credential desynchronization.**

---

## 6. Commands and Tests Actually Executed

All commands were executed using CPython 3.14.7 on the Windows workstation:

### Test Suite 1: Celery Worker & Deterministic Task Verification
Command:
```powershell
$env:PYTHONPATH="backend;.venv\Lib\site-packages"
& "C:\Users\ysubh\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe" -m pytest tests/test_celery_worker.py -v
```
Output:
- `test_celery_app_configuration`: PASSED
- `test_ocr_task_idempotency_skip_already_completed`: PASSED
- `test_ocr_task_missing_version`: PASSED
- `test_report_task_missing_user`: PASSED
- `test_celery_task_apply_eager`: PASSED
- `test_health_ping_task_logic_and_eager`: PASSED
**Result:** **6 passed, 1 warning in 1.26s.**

### Test Suite 2: Staging Configuration & Security Validation Gate
Command:
```powershell
$env:PYTHONPATH="backend;.venv\Lib\site-packages"
& "C:\Users\ysubh\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe" -m pytest tests/test_staging_configuration.py -v
```
**Result:** **22 passed, 0 failed in 0.96s.**

### Test Suite 3: Containerized Staging Integration Test Suite (Offline Fallback Gate)
Command:
```powershell
$env:PYTHONPATH="backend;.venv\Lib\site-packages"
& "C:\Users\ysubh\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe" -m pytest tests/test_containerized_staging_integration.py -v
```
Output:
- `test_live_postgresql_connection_and_postgis_version`: SKIPPED (Live container services unavailable on host)
- `test_live_database_schema_and_alembic_head`: SKIPPED
- `test_live_database_crud_and_transaction_isolation`: SKIPPED
- `test_live_redis_ping_and_key_expiration`: SKIPPED
- `test_live_celery_worker_task_consumption_and_completion`: SKIPPED
- `test_live_minio_bucket_and_object_lifecycle`: SKIPPED
- `test_live_minio_unauthorized_access_rejected`: SKIPPED
- `test_live_application_liveness_probe`: SKIPPED
- `test_live_application_readiness_probe_dependencies`: SKIPPED
**Result:** **9 skipped in 0.06s** (Tests skip cleanly in offline environment; execute fully in containerized CI pipeline).

### Test Suite 4: Full Backend Regression Suite
Command:
```powershell
$env:PYTHONPATH="backend;.venv\Lib\site-packages"
& "C:\Users\ysubh\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe" -m pytest tests -q
```
**Result:** **199 passed, 9 skipped, 1 warning in 75.80s.** (Expanded from 198 tests with zero regressions).

---

## 7. Evidence Distinguishing Mocked Tests from Real-Service Tests

To maintain complete audit integrity, the table below documents the boundary between unit test simulations and container integration tests:

| Component | In-Process Unit Test Simulation (Offline) | Real Container Integration Test (CI / Live Staging) |
|---|---|---|
| **PostgreSQL & Schema** | SQLite in-memory / temporary file via `Base.metadata.create_all()` | Real PostgreSQL 16 server + PostGIS 3.4 extensions initialized via official Docker entrypoint |
| **Migrations** | Alembic executed on SQLite database file | `python -m scripts.migrate upgrade` applied against live PostgreSQL container |
| **Redis Broker** | Mock dictionary / bypassed when `ASYNC_PROCESSING=false` | Real Redis 7 alpine container listening on port 6379 with AOF persistence |
| **Celery Worker** | Eager execution via `task.apply()` in the test process | Dedicated `worker` container daemon polling `default,ocr_queue,report_queue` |
| **Object Storage** | `MockS3Client` storing bytes in Python dictionary | Real MinIO server handling S3 HTTP REST API calls via Boto3 |
| **Application Probes** | FastAPI `TestClient` invoking router functions directly | Live Uvicorn HTTP server responding to container network requests on port 8000 |
| **Data Persistence** | Scoped SQLite transaction rollback | Container restart (`docker compose restart db minio app`) verifying durable named volumes |

---

## 8. Remaining Blockers

1. **Host-Level Container Engine Absence:**
   - The local development workstation does not have Docker Desktop or WSL2 installed (`Get-Command docker` and `wsl.exe -l -v` confirm absence). Local live container execution remains blocked until installed by the operator.
2. **Remote GitHub Actions Runner Execution:**
   - The CI integration workflow [`.github/workflows/staging-integration.yml`](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/.github/workflows/staging-integration.yml) is fully authored and checked into the repository. Live execution on a GitHub-hosted runner requires pushing the branch to a remote GitHub repository.

---

## 9. Final Readiness Verdict

### **Verdict:** `INTEGRATION WORKFLOW IMPLEMENTED — LIVE RUN NOT VERIFIED`

**Rationale:**  
All components required to close the containerized staging validation gap have been implemented:
- A 16-stage GitHub Actions workflow ([`.github/workflows/staging-integration.yml`](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/.github/workflows/staging-integration.yml)) running on Docker-capable runners.
- A dedicated real-service integration test suite ([`backend/tests/test_containerized_staging_integration.py`](file:///c:/Users/ysubh/OneDrive/Desktop/BHUMI%20SETU/backend/tests/test_containerized_staging_integration.py)) covering PostgreSQL/PostGIS, Redis, Celery worker, MinIO S3, and application probes.
- Least-privilege MinIO provisioning scripts and configuration support.
- Idempotent S3 bucket initialization and Celery health ping task.
- Updated 16-section operator runbooks covering troubleshooting, rotation, and backups.

However, per Acceptance Criteria and Non-Negotiable Constraint 7, `LIVE STAGING INTEGRATION VALIDATED` cannot be claimed because the workflow has not yet been executed on a remote GitHub-hosted runner or local Docker daemon. The status is honestly reported as `INTEGRATION WORKFLOW IMPLEMENTED — LIVE RUN NOT VERIFIED`.
