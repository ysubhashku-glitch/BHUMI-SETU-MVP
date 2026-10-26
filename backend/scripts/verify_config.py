"""
BhumiSetu Preflight Configuration & Credential Consistency Validator.
Safely validates environment configuration without exposing secret values or altering files.

Usage:
    python -m scripts.verify_config [--env-file <path>]
"""
import os
import sys
import argparse
from typing import Dict, List, Tuple, Optional
from urllib.parse import urlsplit, unquote


def load_env_file(filepath: str) -> Dict[str, str]:
    """Parses a simple KEY=VALUE or KEY="VALUE" environment file into a dictionary."""
    if not os.path.isfile(filepath):
        return {}
    env_vars = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                env_vars[k] = v
    return env_vars


def verify_configuration(env_vars: Dict[str, str], filepath: Optional[str] = None) -> Tuple[bool, List[str]]:
    """
    Validates environment settings against staging/production requirements.
    NEVER prints or leaks secret values in messages.
    Returns: (is_valid, list_of_report_messages)
    """
    reports = []
    has_errors = False
    target = filepath or "active environment"

    reports.append(f"Auditing configuration source: {target}")

    # 1. Environment and Debug Mode
    env = env_vars.get("ENVIRONMENT", "development").lower()
    debug = env_vars.get("DEBUG", "false").lower() in ("true", "1", "yes")
    reports.append(f"  [CHECK] Environment Mode: {env}")
    if env in ("staging", "production") and debug:
        reports.append("  [FAIL] DEBUG must be 'false' in staging and production.")
        has_errors = True
    else:
        reports.append("  [OK] DEBUG mode is appropriately disabled.")

    # 2. Secret Key Validation
    secret_key = (env_vars.get("SECRET_KEY") or "").strip()
    placeholder_markers = ["replace_with", "placeholder", "changeme", "your_secret", "change_me", "bhumisetu-insecure", "insecure-dev", "change-in-prod", "default-secret", "dev-secret"]
    exposed_keys = {"c8b7a6d5e4f3a2b10987654321fedcba0123456789abcdef0123456789abcdef"}

    if not secret_key:
        reports.append("  [FAIL] SECRET_KEY is missing or empty.")
        has_errors = True
    elif secret_key.lower() in exposed_keys:
        reports.append("  [FAIL] SECRET_KEY matches an exposed historical key and must be rotated.")
        has_errors = True
    elif any(pm in secret_key.lower() for pm in placeholder_markers):
        reports.append("  [FAIL] SECRET_KEY contains placeholder/default text.")
        has_errors = True
    elif len(secret_key) < 32:
        reports.append(f"  [FAIL] SECRET_KEY length ({len(secret_key)}) is under minimum threshold (32 characters).")
        has_errors = True
    elif len(set(secret_key)) < 8:
        reports.append("  [FAIL] SECRET_KEY lacks sufficient cryptographic entropy.")
        has_errors = True
    else:
        reports.append(f"  [OK] SECRET_KEY meets cryptographic complexity requirements ({len(secret_key)} characters).")

    # 3. Database Credentials & DATABASE_URL Consistency
    db_url = env_vars.get("DATABASE_URL", "").strip()
    pg_user = env_vars.get("POSTGRES_USER", "").strip()
    pg_pass = env_vars.get("POSTGRES_PASSWORD", "").strip()
    pg_db = env_vars.get("POSTGRES_DB", "").strip()

    if not db_url:
        reports.append("  [FAIL] DATABASE_URL is missing.")
        has_errors = True
    elif env in ("staging", "production") and db_url.startswith("sqlite"):
        reports.append("  [FAIL] SQLite is forbidden in staging/production.")
        has_errors = True
    elif any(pm in db_url.lower() for pm in placeholder_markers):
        reports.append("  [FAIL] DATABASE_URL contains placeholder markers.")
        has_errors = True
    else:
        reports.append("  [OK] DATABASE_URL is configured.")

    if pg_pass and any(pm in pg_pass.lower() for pm in placeholder_markers):
        reports.append("  [FAIL] POSTGRES_PASSWORD contains placeholder markers.")
        has_errors = True

    if db_url and not db_url.startswith("sqlite"):
        try:
            parsed = urlsplit(db_url)
            url_user = parsed.username
            url_pass = unquote(parsed.password) if parsed.password is not None else None
            url_db = parsed.path.lstrip("/") if parsed.path else None

            if pg_user and url_user and pg_user != url_user:
                reports.append("  [FAIL] POSTGRES_USER does not match username in DATABASE_URL.")
                has_errors = True
            elif pg_user and url_user:
                reports.append("  [OK] POSTGRES_USER matches DATABASE_URL username.")

            if pg_pass and url_pass and pg_pass != url_pass:
                reports.append("  [FAIL] POSTGRES_PASSWORD does not match password embedded in DATABASE_URL.")
                has_errors = True
            elif pg_pass and url_pass:
                reports.append("  [OK] POSTGRES_PASSWORD matches DATABASE_URL password.")

            if pg_db and url_db and pg_db != url_db:
                reports.append("  [FAIL] POSTGRES_DB does not match database name in DATABASE_URL.")
                has_errors = True
            elif pg_db and url_db:
                reports.append("  [OK] POSTGRES_DB matches DATABASE_URL database.")
        except Exception:
            reports.append("  [WARNING] Unable to parse DATABASE_URL components.")

    # 4. Storage Adapter & MinIO Consistency
    storage_adapter = env_vars.get("STORAGE_ADAPTER", "local").lower()
    s3_bucket = env_vars.get("AWS_S3_BUCKET", "").strip()
    s3_endpoint = env_vars.get("S3_ENDPOINT_URL", "").strip()
    minio_user = env_vars.get("MINIO_ROOT_USER", "").strip()
    minio_pass = env_vars.get("MINIO_ROOT_PASSWORD", "").strip()
    s3_key_id = env_vars.get("AWS_ACCESS_KEY_ID", "").strip()
    s3_secret = env_vars.get("AWS_SECRET_ACCESS_KEY", "").strip()

    reports.append(f"  [CHECK] Storage Adapter: {storage_adapter}")
    if storage_adapter in ("s3", "minio"):
        if not s3_bucket:
            reports.append("  [FAIL] AWS_S3_BUCKET is required when using S3/MinIO.")
            has_errors = True
        else:
            reports.append(f"  [OK] S3 Bucket configured: '{s3_bucket}'.")

    if storage_adapter == "minio":
        if not s3_endpoint:
            reports.append("  [FAIL] S3_ENDPOINT_URL is required when STORAGE_ADAPTER is 'minio'.")
            has_errors = True
        else:
            reports.append(f"  [OK] MinIO endpoint configured: '{s3_endpoint}'.")

        if minio_pass and any(pm in minio_pass.lower() for pm in placeholder_markers):
            reports.append("  [FAIL] MINIO_ROOT_PASSWORD contains placeholder markers.")
            has_errors = True

        if s3_secret and any(pm in s3_secret.lower() for pm in placeholder_markers):
            reports.append("  [FAIL] AWS_SECRET_ACCESS_KEY contains placeholder markers.")
            has_errors = True

        dedicated_identity = env_vars.get("MINIO_DEDICATED_APP_IDENTITY", "false").lower() in ("true", "1", "yes")
        if not dedicated_identity:
            if minio_user and s3_key_id and minio_user != s3_key_id:
                reports.append("  [FAIL] MINIO_ROOT_USER does not match AWS_ACCESS_KEY_ID.")
                has_errors = True
            elif minio_user and s3_key_id:
                reports.append("  [OK] MinIO root user matches AWS_ACCESS_KEY_ID.")

            if minio_pass and s3_secret and minio_pass != s3_secret:
                reports.append("  [FAIL] MINIO_ROOT_PASSWORD does not match AWS_SECRET_ACCESS_KEY.")
                has_errors = True
            elif minio_pass and s3_secret:
                reports.append("  [OK] MinIO root password matches AWS_SECRET_ACCESS_KEY.")
        else:
            if not s3_key_id or not s3_secret:
                reports.append("  [FAIL] Dedicated MinIO application credentials (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY) missing.")
                has_errors = True
            else:
                reports.append("  [OK] Dedicated least-privilege MinIO application identity configured.")

    # 5. CORS Origins
    allowed_origins = env_vars.get("ALLOWED_ORIGINS", "")
    if env in ("staging", "production") and "*" in allowed_origins:
        reports.append("  [FAIL] Wildcard '*' CORS is strictly prohibited in staging/production.")
        has_errors = True
    else:
        reports.append("  [OK] CORS allowed origins configured safely.")

    is_valid = not has_errors
    return is_valid, reports


def main():
    parser = argparse.ArgumentParser(description="BhumiSetu Preflight Configuration & Credential Consistency Validator")
    parser.add_argument("--env-file", default=None, help="Path to .env file to inspect")
    args = parser.parse_args()

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_env = args.env_file or os.path.join(backend_dir, ".env")

    print("================================================================================")
    print("BhumiSetu Preflight Configuration Safety & Credential Consistency Audit")
    print("================================================================================")

    if not os.path.isfile(target_env):
        print(f"[ERROR] Environment file not found at: {target_env}")
        print("Initial provisioning is required. Follow the documented runbook:")
        print("  1. Copy .env.example to .env only if .env does not exist.")
        print("  2. Generate cryptographically secure random secrets.")
        print("  3. Synchronize dependent fields (DATABASE_URL, AWS_SECRET_ACCESS_KEY).")
        sys.exit(1)

    env_vars = load_env_file(target_env)
    is_valid, reports = verify_configuration(env_vars, target_env)

    for r in reports:
        print(r)

    print("--------------------------------------------------------------------------------")
    if is_valid:
        print("[PREFLIGHT RESULT] ALL CHECKS PASSED. Configuration is consistent and secure.")
        sys.exit(0)
    else:
        print("[PREFLIGHT RESULT] CONFIGURATION DEFECTS DETECTED. Please correct the items marked [FAIL].")
        sys.exit(1)


if __name__ == "__main__":
    main()
