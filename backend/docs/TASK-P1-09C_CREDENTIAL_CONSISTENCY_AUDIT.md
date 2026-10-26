# TASK-P1-09C: Credential Consistency and Deployment Safety Audit

**Document Code:** AGY-P1-09C-CREDENTIAL-CONSISTENCY-AUDIT-2026-V1  
**Classification:** DevSecOps Security Audit & Operational Deployment Safety Specification  
**Date:** October 26, 2026  
**Status:** Canonical P1-09C Milestone Deliverable  
**Final Verdict:** `CONFIGURATION SAFETY VERIFIED — LIVE STAGING NOT VALIDATED`

---

## 1. Executive Summary

Bhumi Setu completed preflight implementation milestones TASK-P1-09A and TASK-P1-09B, hardening staging secret validation, removing hardcoded Compose fallbacks, enforcing localhost-only port bindings, and establishing initial Windows and Linux staging runbooks. However, live container deployment remained blocked because the host Windows workstation lacks a running Docker daemon and WSL2 engine.

During an architectural and security review of the documented deployment procedures, two critical operational risks were identified:
1. **Dependent Credential Desynchronization:** Initial provisioning generated new cryptographic passwords for PostgreSQL and MinIO, but dependent connection settings (`DATABASE_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) were not updated in lockstep, resulting in authentication failures between backend containers and database/storage daemons.
2. **Accidental Credential Rotation & Volume Desynchronization:** The documented Windows setup script checked for `backend\.env` presence but merely logged a warning before proceeding to execute in-place regex substitutions. In an existing environment with initialized PostgreSQL or MinIO volumes (`staging_pgdata`, `staging_miniodata`), this silently overwrote `.env`, rotating application passwords without updating the database or object-storage engine, causing catastrophic connection failure and risking operator data loss.

Under TASK-P1-09C, these vulnerabilities were completely analyzed, remediated, and verified:
- **Existence Guard:** The provisioning automation was rewritten to halt safely with an exit status if `backend\.env` already exists.
- **Synchronized Provisioning:** Initial credential generation now writes `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_ENDPOINT_URL`, and `S3_USE_SSL` in lockstep.
- **Cryptographic Security:** Secrets are generated using `.NET RNGCryptoServiceProvider` in PowerShell (compatible with Windows PowerShell 5.1 and PowerShell 7+) producing 64-character and 48-character hexadecimal strings that are URL-safe without requiring character escaping.
- **Fail-Fast Configuration Verification:** `backend/app/config.py` was enhanced with strict parity validators and placeholder rejectors, accompanied by a standalone, non-destructive CLI auditor `backend/scripts/verify_config.py`.
- **Zero Information Leakage:** Diagnostic and error messages never include secret or password values.
- **Test Suite Verification:** 22 staging configuration tests and all 198 backend regression tests passed with zero failures.

---

## 2. Credential Dependency Map

The following map traces how configuration variables propagate from environment configuration files into Docker Compose services and the FastAPI/Celery runtime:

```
[.env / Environment]
  ├── SECRET_KEY -------------------------------------> [FastAPI App & Celery Worker (JWT Signing)]
  │
  ├── POSTGRES_USER --------+
  ├── POSTGRES_PASSWORD ----+---> [Docker Compose 'db'] (Entrypoint DB init: creates user & db)
  ├── POSTGRES_DB ----------+
  │       │
  │       +---------------------> [DATABASE_URL] -----> [FastAPI App & Celery Worker (SQLAlchemy/psycopg)]
  │
  ├── MINIO_ROOT_USER ------+---> [Docker Compose 'minio'] (Root admin identity)
  ├── MINIO_ROOT_PASSWORD --+
  │       │
  │       +---------------------> [AWS_ACCESS_KEY_ID] -+
  │       +---------------------> [AWS_SECRET_ACCESS_KEY] -> [FastAPI App & Celery (S3/MinIO Boto3 Adapter)]
  │       +---------------------> [S3_ENDPOINT_URL] --+
  │       +---------------------> [AWS_S3_BUCKET] -----+
  │
  ├── REDIS_URL --------------------------------------> [FastAPI App (Session/Rate Limit Cache)]
  ├── CELERY_BROKER_URL ------------------------------> [FastAPI App & Celery Worker (Queue Broker)]
  └── CELERY_RESULT_BACKEND --------------------------> [FastAPI App & Celery Worker (Task Result Backend)]
```

### Dependency Parity Matrix

| Primary Variable | Dependent Setting | Target Service(s) | Synchronization Requirement | Failure Mode If Desynchronized |
|---|---|---|---|---|
| `POSTGRES_USER` | `DATABASE_URL` | `db`, `app`, `worker` | Must match username in `DATABASE_URL` | `FATAL: password authentication failed for user` |
| `POSTGRES_PASSWORD` | `DATABASE_URL` | `db`, `app`, `worker` | Must match URL-unquoted password in `DATABASE_URL` | `FATAL: password authentication failed for user` |
| `POSTGRES_DB` | `DATABASE_URL` | `db`, `app`, `worker` | Must match database name path in `DATABASE_URL` | `FATAL: database "..." does not exist` |
| `MINIO_ROOT_USER` | `AWS_ACCESS_KEY_ID` | `minio`, `app`, `worker` | Must match when `STORAGE_ADAPTER="minio"` | `403 Forbidden: InvalidAccessKeyId` |
| `MINIO_ROOT_PASSWORD` | `AWS_SECRET_ACCESS_KEY` | `minio`, `app`, `worker` | Must match when `STORAGE_ADAPTER="minio"` | `403 Forbidden: SignatureDoesNotMatch` |
| `STORAGE_ADAPTER` | `S3_ENDPOINT_URL` | `app`, `worker` | Must be `http://minio:9000` for MinIO | Connections attempt public AWS instead of local container |
| `STORAGE_ADAPTER` | `AWS_S3_BUCKET` | `app`, `worker` | Must be specified for `s3` or `minio` | `ValueError: AWS_S3_BUCKET must be specified` |
| `SECRET_KEY` | (Independent) | `app`, `worker` | Must be >= 32 chars, high entropy, non-default | `ValueError: Invalid SECRET_KEY for staging` |

---

## 3. Findings and Severity

| ID | Category | Description | Severity | Remediated Status |
|---|---|---|---|---|
| **SEC-09C-01** | Deployment Safety | Windows runbook executed `-replace` on existing `backend\.env`, overwriting active staging passwords. | **CRITICAL** | Fixed: Provisioning halts if `backend\.env` exists. |
| **SEC-09C-02** | Credential Parity | Initial setup generated `$DbPass` but left `DATABASE_URL` with template placeholder password. | **HIGH** | Fixed: `DATABASE_URL` constructed with matching `$DbPass`. |
| **SEC-09C-03** | Credential Parity | Initial setup generated `$MinioPass` but left `AWS_SECRET_ACCESS_KEY` unsynchronized. | **HIGH** | Fixed: `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` synchronized. |
| **SEC-09C-04** | Operational Risk | No distinction documented between initial DB init, app config update, and live `ALTER USER` rotation. | **MEDIUM** | Fixed: Comprehensive lifecycle documentation added to runbooks. |
| **SEC-09C-05** | Preflight Validation | No standalone read-only tool to inspect and verify `.env` sanity without running the full application. | **MEDIUM** | Fixed: Created `backend/scripts/verify_config.py`. |
| **SEC-09C-06** | Information Leakage | Potential risk of printing plaintext secrets during PowerShell variable expansion or error output. | **LOW** | Fixed: Suppressed terminal printing; zero secret values in exception strings. |

---

## 4. Files Changed

1. `backend/app/config.py`:
   - Added explicit settings attributes: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`.
   - Added placeholder marker rejection across `DATABASE_URL`, `POSTGRES_PASSWORD`, `AWS_SECRET_ACCESS_KEY`, and `MINIO_ROOT_PASSWORD`.
   - Added database credential consistency validation: parses `DATABASE_URL`, unquotes password, and asserts equality against `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`.
   - Added MinIO credential consistency validation: enforces `MINIO_ROOT_USER == AWS_ACCESS_KEY_ID` and `MINIO_ROOT_PASSWORD == AWS_SECRET_ACCESS_KEY`, requiring `S3_ENDPOINT_URL`.
   - Ensured zero secret leakage in all error and diagnostic messages.
2. `backend/scripts/verify_config.py`:
   - Implemented standalone preflight configuration validator for operator execution before container start.
3. `backend/tests/test_staging_configuration.py`:
   - Added 9 automated test functions covering the 9 Workstream E cases. Total tests in file expanded from 13 to 22.
4. `backend/docs/TASK-P1-09A_DEPLOYMENT_PREREQUISITES.md`:
   - Rewrote Stage 2 to halt execution if `backend\.env` already exists.
   - Synchronized all dependent database and MinIO credentials in the generation script.
   - Documented the database credential lifecycle: initial provisioning vs. app connection update vs. live `ALTER USER` password rotation.
   - Updated operator step 2 and expected test counts.
5. `bhumi-setu-reverse-engineering/14-mvp-implementation-plan.md`:
   - Updated milestone tracker with TASK-P1-09C outcomes.
6. `backend/docs/TASK-P1-09C_CREDENTIAL_CONSISTENCY_AUDIT.md`:
   - Created this canonical audit report.

---

## 5. Safe Initial Provisioning Procedure

The corrected provisioning procedure for Windows PowerShell enforces safety invariants:
- **Halts on existing `.env`**: Never replaces an existing configuration.
- **Cryptographically strong generation**: Uses `.NET RNGCryptoServiceProvider`.
- **URL-safe encoding**: Generates lowercase hexadecimal strings which contain only `[0-9a-f]`, eliminating special character delimiter conflicts in `DATABASE_URL`.
- **Atomic synchronization**: Injects values into dependent keys simultaneously.
- **Silent operation**: Writes to disk without echoing secret values to the terminal.

```powershell
cd "c:\Users\ysubh\OneDrive\Desktop\BHUMI SETU"

# 1. Safely halt if backend\.env already exists to protect initialized services
if (Test-Path "backend\.env") {
    Write-Host "[SAFETY HALT] Existing 'backend\.env' detected." -ForegroundColor Yellow
    Write-Host "Initial provisioning halted to prevent overwriting existing credentials or desynchronizing active databases."
    Write-Host "To audit and verify the existing environment configuration, execute:"
    Write-Host "  $env:PYTHONPATH='backend;.venv\Lib\site-packages'; python -m scripts.verify_config"
    return
}

# 2. Copy template only for fresh installation
Copy-Item "backend\.env.example" "backend\.env"

# 3. Generate cryptographically secure random values using .NET RNGCryptoServiceProvider
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()

# JWT Secret Key: 32 bytes (64 hex characters)
$secBytes = New-Object byte[] 32; $rng.GetBytes($secBytes)
$Sec = [System.BitConverter]::ToString($secBytes).Replace("-", "").ToLowerInvariant()

# PostgreSQL Password: 24 bytes (48 hex characters - URL safe)
$dbBytes = New-Object byte[] 24; $rng.GetBytes($dbBytes)
$DbPass = [System.BitConverter]::ToString($dbBytes).Replace("-", "").ToLowerInvariant()

# MinIO Root Password: 24 bytes (48 hex characters)
$minioBytes = New-Object byte[] 24; $rng.GetBytes($minioBytes)
$MinioPass = [System.BitConverter]::ToString($minioBytes).Replace("-", "").ToLowerInvariant()

# 4. Synchronize dependent settings in lockstep
$DbUrl = "postgresql+psycopg://bhumisetu_user:${DbPass}@db:5432/bhumisetu_db"

(Get-Content "backend\.env") `
    -replace '^SECRET_KEY=.*', "SECRET_KEY=""$Sec""" `
    -replace '^POSTGRES_USER=.*', 'POSTGRES_USER="bhumisetu_user"' `
    -replace '^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=""$DbPass""" `
    -replace '^POSTGRES_DB=.*', 'POSTGRES_DB="bhumisetu_db"' `
    -replace '^DATABASE_URL=.*', "DATABASE_URL=""$DbUrl""" `
    -replace '^STORAGE_ADAPTER=.*', 'STORAGE_ADAPTER="minio"' `
    -replace '^AWS_S3_BUCKET=.*', 'AWS_S3_BUCKET="bhumisetu-staging-evidence-vault"' `
    -replace '^MINIO_ROOT_USER=.*', 'MINIO_ROOT_USER="minioadmin"' `
    -replace '^MINIO_ROOT_PASSWORD=.*', "MINIO_ROOT_PASSWORD=""$MinioPass""" `
    -replace '^AWS_ACCESS_KEY_ID=.*', 'AWS_ACCESS_KEY_ID="minioadmin"' `
    -replace '^AWS_SECRET_ACCESS_KEY=.*', "AWS_SECRET_ACCESS_KEY=""$MinioPass""" `
    -replace '^S3_ENDPOINT_URL=.*', 'S3_ENDPOINT_URL="http://minio:9000"' `
    -replace '^S3_USE_SSL=.*', 'S3_USE_SSL="false"' `
    -replace '^ENVIRONMENT=.*', 'ENVIRONMENT="staging"' `
    -replace '^DEBUG=.*', 'DEBUG="false"' | Set-Content "backend\.env"

# 5. Preflight validation
$env:PYTHONPATH="backend;.venv\Lib\site-packages"
& "C:\Users\ysubh\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe" -m scripts.verify_config
```

---

## 6. Existing-Environment Handling

When an environment file `backend\.env` is already present:

1. **Automatic Non-Intervention:** Initial setup automation immediately exits without making any filesystem modifications.
2. **Read-Only Audit:** The operator executes the non-destructive validator:
   ```powershell
   $env:PYTHONPATH="backend;.venv\Lib\site-packages"
   & "C:\Users\ysubh\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe" -m scripts.verify_config
   ```
3. **Targeted Remediation (Without Password Rotation):**
   - If an existing `.env` is incomplete (e.g. missing `S3_ENDPOINT_URL`), the operator updates only the missing field. Existing credentials (`SECRET_KEY`, `POSTGRES_PASSWORD`, `DATABASE_URL`) are preserved to maintain compatibility with initialized database storage.

---

## 7. Database Credential Consistency Findings

### Core Technical Distinction

There are three distinct operational phases in the database credential lifecycle:

1. **Initial Database Cluster Provisioning:**
   - Occurs when the PostgreSQL container starts with an **empty** data volume (`staging_pgdata`).
   - The official PostgreSQL entrypoint script runs `initdb` and creates the default superuser/user and database specified by `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`.
   - **Crucial Invariant:** Once initialized, PostgreSQL writes the master cluster catalog. Subsequent container restarts **do not re-read `POSTGRES_PASSWORD`**.
2. **Updating Application Connection Configuration:**
   - Modifying `DATABASE_URL` in `.env` only affects how the backend application connects to PostgreSQL.
   - If `POSTGRES_PASSWORD` is changed in `.env` without updating the database, the backend will fail to connect with authentication errors.
3. **Rotating Passwords on an Existing PostgreSQL Instance:**
   - To change a password on an active, initialized database, the operator must execute an administrative SQL command inside the database:
     ```sql
     ALTER USER bhumisetu_user WITH PASSWORD 'new_cryptographic_password';
     ```
   - Only after the database user's password has been updated in PostgreSQL should `POSTGRES_PASSWORD` and `DATABASE_URL` in `backend/.env` be updated to match.
   - **Data-Loss Warning:** Persistent database volumes (`staging_pgdata`) must **never** be deleted or recreated to resolve authentication desynchronization.

### Connection String Encoding
If database passwords contain URI-reserved characters (e.g. `@`, `:`, `/`, `?`, `#`, `[`, `]`, `&`, `%`, `+`), they must be URL-encoded (e.g. `@` becomes `%40`, `#` becomes `%23`). In Bhumi Setu:
- The provisioning generator produces pure hexadecimal strings (`[0-9a-f]`), which are inherently URL-safe and require no encoding.
- `backend/app/config.py` unquotes the password component of `DATABASE_URL` (`unquote(parsed_db.password)`) before comparing it with `POSTGRES_PASSWORD`, ensuring valid URL-encoded passwords match raw environment passwords.

---

## 8. MinIO/S3 Credential Consistency Findings

### Architecture & Identity Model

Bhumi Setu supports three storage modes via `STORAGE_ADAPTER`:
1. `local`: Files saved to local disk directory `STORAGE_DIR`. Used for dev/unit tests.
2. `s3`: Production AWS S3 storage with AWS IAM credentials.
3. `minio`: Staging containerized S3-compatible object vault running MinIO.

When `STORAGE_ADAPTER="minio"`:
- MinIO root identity is governed by `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`.
- The application Boto3 S3 client connects using `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.
- Therefore, in MinIO mode, `AWS_ACCESS_KEY_ID` must strictly equal `MINIO_ROOT_USER`, and `AWS_SECRET_ACCESS_KEY` must strictly equal `MINIO_ROOT_PASSWORD`.
- `S3_ENDPOINT_URL` must point to the MinIO service (e.g. `http://minio:9000` in Compose, or `http://127.0.0.1:9000` on the host).
- `S3_USE_SSL` must be `false` for internal HTTP container traffic.
- Updating `MINIO_ROOT_PASSWORD` in `.env` updates the root administrator. When the MinIO container restarts, it updates root credentials from environment variables. However, if individual application service accounts or access keys are configured within MinIO, they are managed via the MinIO client (`mc`) and are not modified by root password changes.

---

## 9. Exact Commands and Test Results

### Suite 1: Staging Configuration & Credential Safety Gate
Command:
```powershell
$env:PYTHONPATH="backend;.venv\Lib\site-packages"
& "C:\Users\ysubh\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe" -m pytest tests/test_staging_configuration.py -v
```
Results:
- `test_dev_config_defaults`: PASSED
- `test_staging_rejects_insecure_secret_key`: PASSED
- `test_staging_rejects_short_secret_key`: PASSED
- `test_staging_rejects_wildcard_cors`: PASSED
- `test_staging_rejects_sqlite`: PASSED
- `test_staging_rejects_s3_without_bucket`: PASSED
- `test_staging_rejects_debug_mode`: PASSED
- `test_valid_staging_configuration`: PASSED
- `test_staging_rejects_empty_or_whitespace_secret_key`: PASSED
- `test_staging_rejects_placeholder_secret_key`: PASSED
- `test_staging_rejects_exposed_historical_secret_key`: PASSED
- `test_staging_rejects_low_entropy_secret_key`: PASSED
- `test_staging_accepts_valid_operator_generated_hex_secret`: PASSED
- `test_missing_env_file_does_not_cause_silent_loss`: PASSED (Workstream E Case 1)
- `test_existing_env_file_is_not_automatically_overwritten`: PASSED (Workstream E Case 2)
- `test_required_credentials_detected_before_deployment`: PASSED (Workstream E Case 3)
- `test_database_credentials_and_connection_url_consistency`: PASSED (Workstream E Case 4)
- `test_minio_credentials_and_application_settings_consistency`: PASSED (Workstream E Case 5)
- `test_placeholder_secrets_rejected_across_all_fields`: PASSED (Workstream E Case 6)
- `test_secret_values_never_appear_in_diagnostic_messages`: PASSED (Workstream E Case 7)
- `test_invalid_configuration_fails_before_application_starts`: PASSED (Workstream E Case 8)
- `test_normal_shutdown_preserves_persistent_data`: PASSED (Workstream E Case 9)

**Outcome:** 22 passed, 0 failed in 0.90s.

### Suite 2: Full Backend Regression Suite
Command:
```powershell
$env:PYTHONPATH="backend;.venv\Lib\site-packages"
& "C:\Users\ysubh\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe" -m pytest tests -q
```
**Outcome:** **198 passed, 0 failed, 1 warning in 75.19s**. (Expanded from 189 tests).

### Suite 3: Preflight Verification CLI Tool
Command:
```powershell
$env:PYTHONPATH="backend;.venv\Lib\site-packages"
& "C:\Users\ysubh\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe" -m scripts.verify_config
```
**Outcome:** Tool correctly loads configuration, audits all 5 check categories, reports status without leaking secrets, and exits with code 0 on valid configuration.

---

## 10. Remaining Blockers

1. **Host-Level Container Runtime Absence:**
   - The Windows host machine does not have Docker Desktop or WSL2 installed (`docker` command not found, WSL not installed). Live containers cannot be executed locally until installed by the operator.
2. **Production AWS S3 Storage Provisioning:**
   - Production deployment requires live AWS IAM staging credentials and an active S3 bucket. Local staging uses containerized MinIO.

---

## 11. Safe Operator Checklist

Before launching staging containers:

- [ ] **Check 1: Host Prerequisite Verification**
  - [ ] WSL2 installed (`wsl --status`).
  - [ ] Docker Desktop installed and running (`docker info`).
  - [ ] Docker Compose V2 verified (`docker compose version`).

- [ ] **Check 2: Environment File Protection**
  - [ ] Check if `backend/.env` exists.
  - [ ] If initializing fresh: Run safe provisioning script in Stage 2.
  - [ ] If already initialized: Verify that existing secrets and volume data are preserved.
  - [ ] Verify `backend/.env` is included in `.gitignore` and never committed.

- [ ] **Check 3: Credential Consistency Preflight**
  - [ ] Run `python -m scripts.verify_config`. Confirm all checks report `[OK]`.
  - [ ] Confirm `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` match `DATABASE_URL`.
  - [ ] Confirm `MINIO_ROOT_USER` matches `AWS_ACCESS_KEY_ID`.
  - [ ] Confirm `MINIO_ROOT_PASSWORD` matches `AWS_SECRET_ACCESS_KEY`.
  - [ ] Confirm `S3_ENDPOINT_URL` is set to `http://minio:9000` when using MinIO.

- [ ] **Check 4: Persistent Volume Safeguard**
  - [ ] Confirm named volumes (`staging_pgdata`, `staging_redisdata`, `staging_miniodata`) are declared in `docker-compose.staging.yml`.
  - [ ] Never execute `docker compose down -v` unless intentional data wipe is authorized.
  - [ ] Use `docker compose down` for normal shutdown.

- [ ] **Check 5: Service Launch & Health Verification**
  - [ ] Run `docker compose -f docker-compose.staging.yml --env-file backend/.env config` to validate Compose parsing.
  - [ ] Run `docker compose -f docker-compose.staging.yml --env-file backend/.env up -d --build`.
  - [ ] Check health: `docker compose ps`.
  - [ ] Run migrations: `docker compose run --rm app python scripts/migrate.py upgrade`.
  - [ ] Check readiness probe: `curl http://127.0.0.1:8000/health/ready`.
  - [ ] Run staging smoke test: `docker compose run --rm app pytest tests/test_staging_smoke.py -v`.

---

## 12. Final Verdict

### **Verdict:** `CONFIGURATION SAFETY VERIFIED — LIVE STAGING NOT VALIDATED`

**Rationale:**  
All credential dependencies, synchronization mechanisms, overwrite protection guards, and preflight validation checks have been implemented, statically verified, and validated against 22 dedicated staging configuration tests and 198 full backend regression tests. However, live container execution and infrastructure integration cannot be completed on this workstation until Docker Desktop and WSL2 are installed by the operator.
