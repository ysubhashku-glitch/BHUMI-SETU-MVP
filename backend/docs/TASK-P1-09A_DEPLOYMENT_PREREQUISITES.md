# TASK-P1-09A: Deployment Prerequisite Resolution and Staging Security Hardening

**Document Code:** AGY-P1-09A-DEPLOYMENT-PREREQUISITES-2026-V1  
**Classification:** Operational DevSecOps Audit & Live Staging Deployment Runbook  
**Date:** October 25, 2026  
**Status:** Canonical P1-09A Milestone Deliverable  
**Final Verdict:** `BLOCKED — CONTAINER RUNTIME UNAVAILABLE`

---

## 1. Environment Inspection Results

A comprehensive audit of the local development workstation host was conducted prior to configuration and security changes:

| Environment Attribute | Observed Value | Operational Interpretation |
|---|---|---|
| **Host Operating System** | Windows 11 Pro (`win32`, `x86_64`, NT `10.0.26100`) | Local development workstation |
| **Python Runtime** | CPython 3.14.7 (`cpython-3.14-windows-x86_64-none`) | Managed via Astral `uv` |
| **Container Engine CLI** | **NOT INSTALLED / NOT FOUND** | `Get-Command docker` returned nothing; `where.exe docker` exit 1 |
| **Podman CLI** | **NOT INSTALLED** | `Get-Command podman` returned nothing |
| **WSL Subsystem** | **NOT INSTALLED** | `wsl.exe -l -v` returned: *"The Windows Subsystem for Linux is not installed. You can install by running 'wsl.exe --install'."* |
| **Active Port Bindings** | None on `5432`, `6379`, `9000`, `8000`, `5433` | No conflicting or running database, broker, or storage daemons |
| **Local Background Services** | No Windows services for Docker, WSL, PostgreSQL, Redis, or MinIO | Clean slate, zero daemon collisions |

---

## 2. Configuration Defects Discovered & Remediated

### Defect 1: Insecure Hardcoded Fallback for `SECRET_KEY` in Compose
- **Issue:** In `docker-compose.staging.yml`, `SECRET_KEY` utilized a fallback expression `${SECRET_KEY:-<hex_key>}`. While 64 characters long, committing a fixed literal secret string into source control compromises deployment security and allows staging instances to run with a shared, leaked key if an operator omits environment configuration.
- **Remediation:** Removed the fallback default entirely. Replaced with Docker Compose mandatory variable syntax:
  ```yaml
  SECRET_KEY: "${SECRET_KEY:?SECRET_KEY must be provided by the operator and must be a cryptographically random secret of at least 32 characters}"
  ```
  If `SECRET_KEY` is absent or empty, Docker Compose now immediately halts with a descriptive error message before any containers or networks are instantiated.

### Defect 2: Latent Pydantic Settings String Parsing Bug in `config.py`
- **Issue:** `ALLOWED_ORIGINS` was typed as `List[str]`. In Pydantic Settings, `EnvSettingsSource` parses list fields with `json.loads()` *before* custom before-validators execute. Consequently, passing comma-delimited strings (`ALLOWED_ORIGINS="http://localhost:3000,https://staging.bhumisetu.gov.in"`) via environment variables crashed application startup with `json.decoder.JSONDecodeError`.
- **Remediation:** Updated type signature to `ALLOWED_ORIGINS: Union[str, List[str]]` and added an `@field_validator("ALLOWED_ORIGINS", mode="after")` that seamlessly handles both comma-delimited strings and JSON array strings.

### Defect 3: Incomplete Environment Documentation in `.env.example`
- **Issue:** `.env.example` omitted explicit declarations for `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `MINIO_ROOT_USER`, and `MINIO_ROOT_PASSWORD`, forcing Compose to rely on implicit fallback values.
- **Remediation:** Added explicit, sanitized documentation placeholders for all database and object storage credentials in `backend/.env.example`.

---

## 3. Secret-Management Hardening

The secret validation gate in `backend/app/config.py` (`validate_staging_production_security()`) was significantly strengthened to enforce cryptographic hygiene across staging and production environments:

1. **Mandatory Operator Provisioning:** `SECRET_KEY` must be explicitly injected via the environment or `.env`.
2. **Rejection of Historical Compromised Keys:** The historical key (`c8b7a6d5e4f3a2b10987654321fedcba0123456789abcdef0123456789abcdef`) previously committed during testing has been marked as compromised and is explicitly blacklisted. Attempting to start staging with this key raises:
   `ValueError: Invalid SECRET_KEY for staging environment: The supplied secret matches an exposed historical key that has been compromised and must be rotated.`
3. **Rejection of Empty and Whitespace Secrets:** Empty strings, spaces, and tabs are rejected with clear error messages.
4. **Rejection of Template Placeholders:** Tokens containing `"replace_with"`, `"placeholder"`, `"changeme"`, `"your_secret"`, `"secret_key"`, `"bhumisetu-insecure"`, `"insecure-dev"`, or `"change-in-prod"` are rejected.
5. **Entropy & Repetition Check:** Secrets with fewer than 8 unique characters (e.g. repeated characters `"0"*64` or `"a"*64`) are rejected for lacking sufficient cryptographic entropy.
6. **Zero-Leakage Logging:** `backend/app/core/logging_config.py` uses `StructuredJsonFormatter` to automatically redact any keys matching `password`, `secret`, `token`, `bearer`, `authorization`, `private_key`, `api_key`, `access_key`, `secret_key`, and `jwt` to `[REDACTED]`.

---

## 4. Exact Files Changed

1. `c:/Users/ysubh/OneDrive/Desktop/BHUMI SETU/docker-compose.staging.yml`:
   - Enforced required `SECRET_KEY` via Compose interpolation error syntax in both `app` and `worker` services.
2. `c:/Users/ysubh/OneDrive/Desktop/BHUMI SETU/backend/app/config.py`:
   - Hardened `validate_staging_production_security()` with historical key blacklist, empty/whitespace rejection, expanded placeholder markers, and entropy verification.
3. `c:/Users/ysubh/OneDrive/Desktop/BHUMI SETU/backend/.env.example`:
   - Added documentation placeholders for `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `MINIO_ROOT_USER`, and `MINIO_ROOT_PASSWORD`.
4. `c:/Users/ysubh/OneDrive/Desktop/BHUMI SETU/backend/tests/test_staging_configuration.py`:
   - Added 5 new automated tests validating rejection of empty secrets, template placeholders, exposed historical keys, low-entropy keys, and acceptance of valid operator-generated hex secrets (13/13 passing).
5. `c:/Users/ysubh/OneDrive/Desktop/BHUMI SETU/backend/docs/TASK-P1-09A_DEPLOYMENT_PREREQUISITES.md`:
   - Created this canonical deployment runbook and readiness document.
6. `c:/Users/ysubh/OneDrive/Desktop/BHUMI SETU/bhumi-setu-reverse-engineering/14-mvp-implementation-plan.md`:
   - Updated backlog with TASK-P1-09A progress and test outcomes.

---

## 5. Tests Executed and Outcomes

All automated suites were executed using the pinned CPython 3.14 runtime:

| Test Scope | Command | Tests Run | Exit Code | Outcome |
|---|---|---|---|---|
| **Staging Config Security** | `pytest tests/test_staging_configuration.py -v` | 13 | `0` | **13 passed in 0.86s** |
| **Object Storage Adapter** | `pytest tests/test_storage_s3_minio.py -v` | 6 | `0` | **6 passed in 0.50s** |
| **Celery Worker Pipeline** | `pytest tests/test_celery_worker.py -v` | 5 | `0` | **5 passed in 0.54s** |
| **Health, Observability & Recovery** | `pytest tests/test_health_and_observability.py -v` | 9 | `0` | **9 passed in 0.72s** |
| **Staging End-to-End Smoke Test** | `pytest tests/test_staging_smoke.py -v` | 1 (18 steps) | `0` | **1 passed in 6.70s** |
| **Full Backend Regression Suite** | `pytest tests -q` | 189 | `0` | **189 passed, 0 failed in 75.95s** |

---

## 6. Container-Runtime Availability

- **Status:** **UNAVAILABLE**
- **Findings:**
  - Neither Docker Desktop nor Docker Engine is installed on the host operating system.
  - WSL2 is not installed (`The Windows Subsystem for Linux is not installed`).
- **Policy Enforcement:** Per Rule 10 and Rule 11 of the engineering charter, live container execution cannot be claimed, simulated, or marked complete until the operator provisions the required container runtime.

---

## 7. Steps Required to Launch Staging (Operator Runbooks)

## 7. Steps Required to Launch Staging (Operator Runbooks)

### Option A: Windows Local Staging Runbook

The deployment workflow is organized into 12 structured operational stages:

#### Stage 1: Prerequisite Installation
1. Open an elevated PowerShell terminal (Run as Administrator).
2. Install WSL2 (Windows Subsystem for Linux):
   ```powershell
   wsl --install
   ```
3. Restart the workstation when prompted by Windows.
4. Download and install **Docker Desktop for Windows** from [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/).
5. In Docker Desktop Settings:
   - Enable **Use the WSL 2 based engine**.
   - Start the Docker Desktop application and confirm the daemon is running:
     ```powershell
     docker info
     ```
   - Verify that Docker Compose V2 is active:
     ```powershell
     docker compose version
     ```

#### Stage 2: Secure Environment Configuration
Navigate to the project root in PowerShell. Do **not** overwrite an existing `.env`. The procedure halts safely if `backend\.env` exists to protect initialized database and storage volumes. Generate secrets cryptographically and synchronize all dependent settings without printing secret values to the terminal:

```powershell
cd "c:\Users\ysubh\OneDrive\Desktop\BHUMI SETU"

# 1. Safely halt if backend\.env already exists
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
# (Compatible with Windows PowerShell 5.1 and PowerShell 7+)
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()

# JWT Secret Key: 32 bytes (64 hex characters)
$secBytes = New-Object byte[] 32; $rng.GetBytes($secBytes)
$Sec = [System.BitConverter]::ToString($secBytes).Replace("-", "").ToLowerInvariant()

# PostgreSQL Password: 24 bytes (48 hex characters - guaranteed URL-safe)
$dbBytes = New-Object byte[] 24; $rng.GetBytes($dbBytes)
$DbPass = [System.BitConverter]::ToString($dbBytes).Replace("-", "").ToLowerInvariant()

# MinIO Root Password: 24 bytes (48 hex characters)
$minioBytes = New-Object byte[] 24; $rng.GetBytes($minioBytes)
$MinioPass = [System.BitConverter]::ToString($minioBytes).Replace("-", "").ToLowerInvariant()

# 4. Synchronize dependent settings in lockstep (DATABASE_URL, AWS_SECRET_ACCESS_KEY, etc.)
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

# 5. Silently verify configuration consistency before starting services
$env:PYTHONPATH="backend;.venv\Lib\site-packages"
& "C:\Users\ysubh\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe" -m scripts.verify_config
Write-Host "[OK] backend\.env provisioned and validated with synchronized database and storage credentials."
```

> [!IMPORTANT]
> **Source Control Protection:** Ensure `backend\.env` is never committed to Git. Verify that `.gitignore` includes `.env`, `.env.*`, and `backend/.env`.

#### Stage 3: Compose Configuration Validation
Validate that Docker Compose parses all variables and that no mandatory secrets are missing:
```powershell
docker compose -f docker-compose.staging.yml --env-file backend\.env config
```
*If any required variable (`SECRET_KEY`, `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`) is missing, Compose will immediately halt with an error.*

#### Stage 4: Container Image Build
Build the multi-stage, non-root application and worker container image:
```powershell
docker compose -f docker-compose.staging.yml --env-file backend\.env build
```

#### Stage 5: Service Startup
Launch all required infrastructure services (PostgreSQL/PostGIS, Redis, MinIO, API Gateway, Celery Worker) in detached mode:
```powershell
docker compose -f docker-compose.staging.yml --env-file backend\.env up -d
```

#### Stage 6: Database Migration
Run the single controlled migration runner inside the application container network:
```powershell
docker compose -f docker-compose.staging.yml --env-file backend\.env run --rm app python scripts/migrate.py upgrade
```

#### Stage 7: Database Readiness Verification
Confirm that PostgreSQL is accepting connections and PostGIS spatial extensions are enabled:
```powershell
# Check container health status
docker compose -f docker-compose.staging.yml ps db

# Query PostGIS version via migration script check
docker compose -f docker-compose.staging.yml --env-file backend\.env run --rm app python scripts/migrate.py check
```

#### Stage 8: Redis and Worker Verification
Confirm that Redis is answering pings and the Celery worker has connected to queues `default`, `ocr_queue`, and `report_queue`:
```powershell
# Verify Redis container health
docker compose -f docker-compose.staging.yml ps redis

# Inspect worker logs for successful queue subscription
docker compose -f docker-compose.staging.yml logs worker --tail=20
```

#### Stage 9: Object-Storage Verification
Confirm that the MinIO container is healthy and responding to liveness probes:
```powershell
docker compose -f docker-compose.staging.yml ps minio
curl -f http://127.0.0.1:9000/minio/health/live
```

#### Stage 10: End-to-End Smoke Testing
Execute the complete 18-step synthetic staging smoke test against the live running container network:
```powershell
docker compose -f docker-compose.staging.yml --env-file backend\.env run --rm app pytest tests/test_staging_smoke.py -v
```

#### Stage 11: Regression Testing
Execute the full backend test suite inside the container environment:
```powershell
docker compose -f docker-compose.staging.yml --env-file backend\.env run --rm app pytest tests -q
```

#### Stage 12: Non-Destructive Shutdown
Stop and remove containers and virtual networks while strictly preserving all database records, Redis caches, and uploaded object storage:
```powershell
docker compose -f docker-compose.staging.yml down
```

---

### Option B: Linux Staging Runbook (Private VPC / Dedicated VM)

The Linux deployment workflow adheres to the same 12-stage lifecycle:

#### Stage 1: Prerequisite Installation
Ensure Docker Engine 24.0+ and Compose V2 are installed on Ubuntu/Debian:
```bash
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
docker compose version
```

#### Stage 2: Secure Environment Configuration
Generate cryptographically random 32-byte (64-character hex) secrets using OpenSSL and enforce POSIX file permissions (`chmod 600`):
```bash
cd /opt/bhumisetu

# Generate cryptographically secure values
STAGING_SECRET=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 24)
MINIO_PASSWORD=$(openssl rand -hex 24)

# Create restricted environment file
cat <<EOF > .env
ENVIRONMENT=staging
DEBUG=false
PROJECT_NAME="BhumiSetu Land Intelligence Platform (Staging)"
ALLOWED_ORIGINS="https://staging.bhumisetu.gov.in,https://admin.staging.bhumisetu.gov.in"

POSTGRES_USER=bhumisetu_user
POSTGRES_PASSWORD=${DB_PASSWORD}
POSTGRES_DB=bhumisetu_db
DATABASE_URL=postgresql+psycopg://bhumisetu_user:${DB_PASSWORD}@db:5432/bhumisetu_db

SECRET_KEY=${STAGING_SECRET}

STORAGE_ADAPTER=minio
AWS_S3_BUCKET=bhumisetu-staging-evidence-vault
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=${MINIO_PASSWORD}
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=${MINIO_PASSWORD}
S3_ENDPOINT_URL=http://minio:9000
S3_USE_SSL=false

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
ASYNC_PROCESSING=true
PUBLIC_BASE_URL=https://staging.bhumisetu.gov.in
EOF

chmod 600 .env
```

#### Stage 3: Compose Configuration Validation
```bash
docker compose -f docker-compose.staging.yml --env-file .env config
```

#### Stage 4: Container Image Build
```bash
docker compose -f docker-compose.staging.yml --env-file .env build
```

#### Stage 5: Service Startup
```bash
docker compose -f docker-compose.staging.yml --env-file .env up -d
```

#### Stage 6: Database Migration
```bash
docker compose -f docker-compose.staging.yml --env-file .env run --rm app python scripts/migrate.py upgrade
```

#### Stage 7: Database Readiness Verification
```bash
docker compose -f docker-compose.staging.yml ps db
docker compose -f docker-compose.staging.yml --env-file .env run --rm app python scripts/migrate.py check
```

#### Stage 8: Redis and Worker Verification
```bash
docker compose -f docker-compose.staging.yml ps redis
docker compose -f docker-compose.staging.yml logs worker --tail=20
```

#### Stage 9: Object-Storage Verification
```bash
docker compose -f docker-compose.staging.yml ps minio
curl -f http://127.0.0.1:9000/minio/health/live
```

#### Stage 10: End-to-End Smoke Testing
```bash
docker compose -f docker-compose.staging.yml --env-file .env run --rm app pytest tests/test_staging_smoke.py -v
```

#### Stage 11: Regression Testing
```bash
docker compose -f docker-compose.staging.yml --env-file .env run --rm app pytest tests -q
```

#### Stage 12: Non-Destructive Shutdown
```bash
docker compose -f docker-compose.staging.yml down
```

---

## 8. Data-Safety Precautions & Invariants

To guarantee data preservation and prevent accidental loss:

1. **Persistent Named Volumes:**
   The staging deployment relies on three designated, persistent named volumes defined in `docker-compose.staging.yml`:
   - `staging_pgdata`: Stores PostgreSQL 16 cluster data, PostGIS geometry tables, and Alembic version state.
   - `staging_redisdata`: Stores Redis append-only files (AOF) and background task states.
   - `staging_miniodata`: Stores uploaded land evidence, deeds, Khatiyan scans, and generated Land Intelligence PDF reports.

2. **Standard Shutdown Command (Non-Destructive):**
   ```bash
   docker compose -f docker-compose.staging.yml down
   ```
   > [!IMPORTANT]
   > The ordinary `down` command stops and removes containers and networks while **strictly preserving** all persistent named volumes (`staging_pgdata`, `staging_redisdata`, `staging_miniodata`). All application data, documents, and database records remain intact across restarts.

3. **Destructive Volume Wipe Policy (Restricted):**
   > [!CAUTION]
   > Running `docker compose down -v` permanently deletes named Docker volumes and destroys all uploaded evidence and database tables. **Never** execute `down -v` in a staging or shared environment unless performing an intentional, authorized catastrophic database wipe.

4. **Database Credential Lifecycle & Password Rotation:**
   - **Initial Database Provisioning:** When the PostgreSQL container starts for the very first time with an empty volume (`staging_pgdata`), its entrypoint script initializes the cluster and sets the user/password based on `POSTGRES_USER` and `POSTGRES_PASSWORD`.
   - **Updating Application Connection Configuration:** Updating `DATABASE_URL` and `POSTGRES_PASSWORD` in `.env` only alters client connection credentials. If PostgreSQL has already been initialized, the database daemon **ignores** `POSTGRES_PASSWORD` on container restart.
   - **Rotating Existing Database Passwords:** To rotate a password on an existing PostgreSQL instance, the operator must explicitly execute SQL inside the database:
     ```sql
     ALTER USER bhumisetu_user WITH PASSWORD 'new_secure_password';
     ```
     followed by synchronizing `POSTGRES_PASSWORD` and `DATABASE_URL` in `backend/.env`. Overwriting `.env` without `ALTER USER` breaks database connectivity.
   - **Volume Preservation Rule:** Under no circumstances should persistent volumes (`staging_pgdata`, `staging_miniodata`) be deleted or recreated to resolve credential desynchronization.

5. **Test Cleanup Scope:**
   - Synthetic end-to-end tests clean up only records bearing explicit test identifiers (`test-tenant-staging-smoke`, synthetic case UUIDs). Unrelated staging data is never touched.

---

## 9. Remaining Blockers

1. **Host-Level Container Runtime Absence:**
   - The Windows host requires WSL2 and Docker Desktop to execute containerized services.
2. **Real Cloud Storage Endpoint:**
   - Testing against live AWS S3 over TLS requires staging AWS IAM credentials and a provisioned cloud bucket.

---

## 10. Exact Command Sequence for the Next Operator

### Step 1: Execute Unit & Regression Gate on Host
```powershell
$env:PYTHONPATH="c:\Users\ysubh\OneDrive\Desktop\BHUMI SETU\backend;.venv\Lib\site-packages"
& "C:\Users\ysubh\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe" -m pytest tests -q
```
*Expected: 198 passed, 0 failed.*

### Step 2: Set Up Docker & Environment (Once Docker Desktop is Installed)
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

$secBytes = New-Object byte[] 32; $rng.GetBytes($secBytes)
$Sec = [System.BitConverter]::ToString($secBytes).Replace("-", "").ToLowerInvariant()

$dbBytes = New-Object byte[] 24; $rng.GetBytes($dbBytes)
$DbPass = [System.BitConverter]::ToString($dbBytes).Replace("-", "").ToLowerInvariant()

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

### Step 3: Start Services & Run Migrations
```powershell
# Start all containers
docker compose -f docker-compose.staging.yml --env-file backend\.env up -d --build

# Run migrations
docker compose -f docker-compose.staging.yml --env-file backend\.env run --rm app python scripts/migrate.py upgrade

# Verify readiness probe
curl http://127.0.0.1:8000/health/ready

# Run live staging smoke test
docker compose -f docker-compose.staging.yml --env-file backend\.env run --rm app pytest tests/test_staging_smoke.py -v
```

### Step 4: Safe, Non-Destructive Shutdown
```powershell
# Stop services without deleting persistent volumes
docker compose -f docker-compose.staging.yml down
```

---

## 11. Failure Diagnosis & Operational Troubleshooting

When troubleshooting container startup or service connectivity issues:

1. **Inspect Container Status and Exit Codes:**
   ```powershell
   docker compose -f docker-compose.staging.yml ps -a
   ```
2. **Collect Sanitized Container Logs:**
   ```powershell
   # View database logs for auth failures or initialization issues
   docker compose -f docker-compose.staging.yml logs db --tail=50

   # View application web server traces
   docker compose -f docker-compose.staging.yml logs app --tail=50

   # View Celery worker queue subscription logs
   docker compose -f docker-compose.staging.yml logs worker --tail=50
   ```
3. **Investigate Readiness Probe Failures:**
   If `GET /health/ready` returns HTTP 503, inspect the `checks` payload:
   - `checks.database.status == "unhealthy"`: Database is unreachable or rejecting credentials.
   - `checks.schema.status == "unhealthy"`: Migrations have not run. Run `scripts/migrate.py upgrade`.
   - `checks.postgis.status == "unhealthy"`: PostGIS extension is missing or uninitialized.
   - `checks.redis.status == "unhealthy"`: Redis daemon is down or unreachable under `ASYNC_PROCESSING=true`.
   - `checks.storage.status == "unhealthy"`: Storage directory is not writable or MinIO/S3 bucket is inaccessible.
4. **Interactive In-Container Shell (Non-Destructive):**
   ```powershell
   docker compose -f docker-compose.staging.yml run --rm app bash
   ```

---

## 12. Safe Credential Rotation Procedure (Existing Environments)

> [!WARNING]
> Never attempt to rotate PostgreSQL passwords by editing `.env` alone or by deleting Docker volumes. An initialized PostgreSQL cluster ignores environment variable changes on restart.

To safely rotate credentials on an active staging instance:

1. **Step 1: Generate New Cryptographic Password:**
   ```powershell
   $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
   $bytes = New-Object byte[] 24; $rng.GetBytes($bytes)
   $NewPass = [System.BitConverter]::ToString($bytes).Replace("-", "").ToLowerInvariant()
   ```
2. **Step 2: Update PostgreSQL Database Catalog Directly:**
   Execute `ALTER USER` inside the running database container:
   ```powershell
   docker compose -f docker-compose.staging.yml exec db psql -U bhumisetu_user -d bhumisetu_db -c "ALTER USER bhumisetu_user WITH PASSWORD '$NewPass';"
   ```
3. **Step 3: Update `backend/.env` with Matching Credentials:**
   Update both `POSTGRES_PASSWORD` and `DATABASE_URL` simultaneously:
   ```powershell
   $NewDbUrl = "postgresql+psycopg://bhumisetu_user:${NewPass}@db:5432/bhumisetu_db"
   (Get-Content "backend\.env") `
       -replace '^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=""$NewPass""" `
       -replace '^DATABASE_URL=.*', "DATABASE_URL=""$NewDbUrl""" | Set-Content "backend\.env"
   ```
4. **Step 4: Restart Application and Worker Containers:**
   ```powershell
   docker compose -f docker-compose.staging.yml restart app worker
   ```
5. **Step 5: Verify Readiness Probe:**
   ```powershell
   curl http://127.0.0.1:8000/health/ready
   ```

---

## 13. Backup and Disaster Recovery Prerequisites

Before upgrading or conducting major staging experiments:

1. **PostgreSQL Spatial Logical Dump:**
   ```powershell
   docker compose -f docker-compose.staging.yml exec -T db pg_dump -U bhumisetu_user -Fc bhumisetu_db > "backup_bhumisetu_$(Get-Date -Format 'yyyyMMdd_HHmmss').dump"
   ```
2. **MinIO Object Vault Backup:**
   Mirror the staging bucket to a backup directory:
   ```bash
   mc mirror staging_minio/bhumisetu-staging-evidence-vault /backup/evidence-vault/
   ```
3. **Redis Persistence Snapshot:**
   Trigger an atomic background save:
   ```powershell
   docker compose -f docker-compose.staging.yml exec redis redis-cli bgsave
   ```

---

## 14. Automated CI Integration Validation Alternative (When Host Docker is Unavailable)

If Docker Desktop and WSL2 are unavailable on the local workstation, automated staging integration validation can be executed using the GitHub Actions workflow:

- **Workflow File:** `.github/workflows/staging-integration.yml`
- **Runner:** `ubuntu-latest` (Docker Engine, Docker Compose V2, and Python pre-installed).
- **Execution Pipeline:**
  1. Runs the full backend regression suite (198 tests).
  2. Generates ephemeral, cryptographically secure CI credentials.
  3. Builds Docker images and boots PostgreSQL 16 + PostGIS 3.4, Redis 7, and MinIO.
  4. Runs database migrations (`scripts/migrate.py upgrade`).
  5. Boots application and worker containers.
  6. Executes `tests/test_containerized_staging_integration.py` against real container services:
     - Real database CRUD and PostGIS spatial validation.
     - Real Celery task execution via Redis broker to live background worker.
     - Real MinIO S3 object put, get, SHA-256 integrity check, and unauthorized rejection.
     - Application `/health/live` vs `/health/ready` probe verification.
  7. Restarts containers and verifies volume persistence.
  8. Collects sanitized diagnostic logs if any failure occurs.
  9. Shuts down and cleans up all ephemeral CI resources.

---

## 15. Critical Distinction: CI Integration Validation vs Production Readiness

Passing CI integration validation proves that containers, database migrations, Redis queues, MinIO storage, and FastAPI services connect and interoperate correctly. However, **CI staging validation is NOT a substitute for production readiness**.

| Dimension | Staging / CI Integration | Production Readiness Requirement |
|---|---|---|
| **Network Security** | Bridge network, localhost port bindings | Private isolated VPC, WAF, private subnets, TLS 1.3 termination |
| **Object Storage** | Containerized MinIO HTTP | AWS S3 with KMS SSE-S3 encryption, versioning, object locks, and IAM roles |
| **Database HA** | Single container PostgreSQL volume | Multi-AZ Managed PostgreSQL (RDS/Aurora), read replicas, automated PITR |
| **Secrets Management** | `.env` files / GitHub Action masks | HashiCorp Vault or AWS Secrets Manager with automated rotation |
| **Task Queue** | Single Redis container | Redis Cluster / AWS ElastiCache with multi-AZ failover and Celery autoscaling |
| **Disaster Recovery** | Ephemeral volumes (`down -v`) | Continuous WAL archiving, cross-region replication, RPO < 5m, RTO < 15m |
| **Observability** | Container logs / local Prometheus | Centralized OpenTelemetry, Datadog/CloudWatch metrics, PagerDuty alerts |

---

## 16. Final Readiness Verdict

### **Verdict:** `INTEGRATION WORKFLOW IMPLEMENTED — LIVE RUN NOT VERIFIED`

**Rationale:**  
The host Windows workstation continues to lack Docker Desktop and WSL2. Under TASK-P1-09D, a dedicated GitHub Actions workflow (`.github/workflows/staging-integration.yml`), real-service integration test suite (`tests/test_containerized_staging_integration.py`), and least-privilege MinIO scripts have been completely implemented. However, until this workflow executes on a live runner and all integration steps pass, live staging remains unverified.


