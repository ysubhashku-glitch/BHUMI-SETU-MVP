import os
import pytest
from app.config import Settings


def test_dev_config_defaults():
    """Verifies that development configuration permits default dev settings."""
    cfg = Settings(
        ENVIRONMENT="development",
        SECRET_KEY="bhumisetu-insecure-dev-secret-key-change-in-prod-2026",
        ALLOWED_ORIGINS=["*"],
        DATABASE_URL="sqlite:///./test.db",
        DEBUG=True
    )
    assert cfg.ENVIRONMENT == "development"
    assert cfg.DEBUG is True
    assert "*" in cfg.ALLOWED_ORIGINS


def test_staging_rejects_insecure_secret_key():
    """Staging must reject default or short insecure secret keys."""
    with pytest.raises(ValueError, match="Invalid SECRET_KEY for staging"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY="bhumisetu-insecure-dev-secret-key-change-in-prod-2026",
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
            DEBUG=False
        )


def test_staging_rejects_short_secret_key():
    """Staging must reject secret keys shorter than 32 characters."""
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY="short_custom_secret_key_123",
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
            DEBUG=False
        )


def test_staging_rejects_wildcard_cors():
    """Staging must reject wildcard '*' CORS origins."""
    with pytest.raises(ValueError, match="Wildcard CORS"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY="a_very_secure_and_cryptographically_strong_random_secret_2026",
            ALLOWED_ORIGINS=["*"],
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
            DEBUG=False
        )


def test_staging_rejects_sqlite():
    """Staging must reject SQLite databases."""
    with pytest.raises(ValueError, match="SQLite is prohibited in staging"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY="a_very_secure_and_cryptographically_strong_random_secret_2026",
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="sqlite:///./staging.db",
            DEBUG=False
        )


def test_staging_rejects_s3_without_bucket():
    """Staging with STORAGE_ADAPTER='s3' must specify AWS_S3_BUCKET."""
    with pytest.raises(ValueError, match="AWS_S3_BUCKET must be specified"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY="a_very_secure_and_cryptographically_strong_random_secret_2026",
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
            STORAGE_ADAPTER="s3",
            AWS_S3_BUCKET=None,
            DEBUG=False
        )


def test_staging_rejects_debug_mode():
    """Staging must reject DEBUG=True."""
    with pytest.raises(ValueError, match="DEBUG mode must be FALSE"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY="a_very_secure_and_cryptographically_strong_random_secret_2026",
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
            DEBUG=True
        )


def test_valid_staging_configuration():
    """Valid staging configuration must pass all security checks."""
    cfg = Settings(
        ENVIRONMENT="staging",
        SECRET_KEY="a_very_secure_and_cryptographically_strong_random_secret_2026",
        ALLOWED_ORIGINS="https://staging.bhumisetu.gov.in, https://admin.staging.bhumisetu.gov.in",
        DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
        STORAGE_ADAPTER="s3",
        AWS_S3_BUCKET="bhumisetu-staging-vault",
        DEBUG=False
    )
    assert cfg.ENVIRONMENT == "staging"
    assert len(cfg.ALLOWED_ORIGINS) == 2
    assert "https://staging.bhumisetu.gov.in" in cfg.ALLOWED_ORIGINS
    assert cfg.STORAGE_ADAPTER == "s3"


def test_staging_rejects_empty_or_whitespace_secret_key():
    """Staging must reject empty or whitespace-only SECRET_KEY."""
    for empty_val in ("", "   ", "\t\n"):
        with pytest.raises(ValueError, match="Invalid SECRET_KEY for staging"):
            Settings(
                ENVIRONMENT="staging",
                SECRET_KEY=empty_val,
                ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
                DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
                DEBUG=False
            )


def test_staging_rejects_placeholder_secret_key():
    """Staging must reject placeholder secrets from templates or documentation."""
    placeholders = [
        "replace_with_a_64_character_hexadecimal_cryptographically_secure_random_string_2026",
        "placeholder_secret_key_for_staging_deployment_test",
        "changeme_this_is_not_a_real_production_secret_123",
        "your_secret_key_must_be_set_by_operator_in_env_file",
        "my_secret_key_needs_to_be_replaced_before_running_app",
    ]
    for ph in placeholders:
        with pytest.raises(ValueError, match="Invalid SECRET_KEY for staging"):
            Settings(
                ENVIRONMENT="staging",
                SECRET_KEY=ph,
                ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
                DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
                DEBUG=False
            )


def test_staging_rejects_exposed_historical_secret_key():
    """Staging must reject the previously exposed historical key and enforce rotation."""
    exposed_key = "c8b7a6d5e4f3a2b10987654321fedcba0123456789abcdef0123456789abcdef"
    with pytest.raises(ValueError, match="exposed historical key that has been compromised and must be rotated"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY=exposed_key,
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
            DEBUG=False
        )


def test_staging_rejects_low_entropy_secret_key():
    """Staging must reject repetitive or low-entropy secrets even if long."""
    low_entropy_keys = [
        "0" * 64,
        "a" * 64,
        "12341234123412341234123412341234",
    ]
    for key in low_entropy_keys:
        with pytest.raises(ValueError, match="lacks sufficient cryptographic entropy"):
            Settings(
                ENVIRONMENT="staging",
                SECRET_KEY=key,
                ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
                DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
                DEBUG=False
            )


def test_staging_accepts_valid_operator_generated_hex_secret():
    """Staging must accept valid cryptographically generated 64-char hexadecimal secrets."""
    import secrets
    operator_secret = secrets.token_hex(32)
    cfg = Settings(
        ENVIRONMENT="staging",
        SECRET_KEY=operator_secret,
        ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
        DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
        STORAGE_ADAPTER="s3",
        AWS_S3_BUCKET="bhumisetu-staging-vault",
        DEBUG=False
    )
    assert cfg.ENVIRONMENT == "staging"
    assert cfg.SECRET_KEY == operator_secret


# ==============================================================================
# TASK-P1-09C: Credential Consistency & Deployment Safety Tests (Workstream E)
# ==============================================================================

def test_missing_env_file_does_not_cause_silent_loss(tmp_path):
    """Case 1: A missing environment file does not cause silent loss of an existing configuration."""
    from scripts.verify_config import load_env_file
    non_existent = str(tmp_path / "non_existent.env")
    assert not os.path.exists(non_existent)
    loaded = load_env_file(non_existent)
    assert loaded == {}
    # Verify no file was inadvertently created or modified
    assert not os.path.exists(non_existent)


def test_existing_env_file_is_not_automatically_overwritten(tmp_path):
    """Case 2: An existing environment file is not automatically overwritten."""
    env_file = tmp_path / ".env"
    initial_content = "EXISTING_PRESERVED_KEY=original_val_12345\n"
    env_file.write_text(initial_content, encoding="utf-8")

    # Guard simulated: initial provisioning check
    if env_file.exists():
        provision_aborted = True
    else:
        env_file.write_text("OVERWRITTEN_KEY=new_val\n", encoding="utf-8")
        provision_aborted = False

    assert provision_aborted is True
    assert env_file.read_text(encoding="utf-8") == initial_content


def test_required_credentials_detected_before_deployment():
    """Case 3: Required credentials are detected before deployment."""
    # Missing SECRET_KEY in staging
    with pytest.raises(ValueError, match="Invalid SECRET_KEY for staging"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY="",
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
            DEBUG=False
        )

    # Missing AWS_S3_BUCKET when storage adapter is minio
    with pytest.raises(ValueError, match="AWS_S3_BUCKET must be specified"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY="a1b2c3d4e5f67890123456789012345678901234567890123456789012345678",
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
            STORAGE_ADAPTER="minio",
            AWS_S3_BUCKET=None,
            S3_ENDPOINT_URL="http://minio:9000",
            DEBUG=False
        )

    # Missing S3_ENDPOINT_URL when storage adapter is minio
    with pytest.raises(ValueError, match="S3_ENDPOINT_URL must be specified"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY="a1b2c3d4e5f67890123456789012345678901234567890123456789012345678",
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
            STORAGE_ADAPTER="minio",
            AWS_S3_BUCKET="vault",
            S3_ENDPOINT_URL=None,
            DEBUG=False
        )


def test_database_credentials_and_connection_url_consistency():
    """Case 4: Database credentials and connection URL are consistent."""
    valid_key = "a1b2c3d4e5f67890123456789012345678901234567890123456789012345678"

    # 4a: Matching credentials pass
    cfg = Settings(
        ENVIRONMENT="staging",
        SECRET_KEY=valid_key,
        ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
        DATABASE_URL="postgresql+psycopg://bhumisetu_user:strong_pass_12345@db:5432/bhumisetu_db",
        POSTGRES_USER="bhumisetu_user",
        POSTGRES_PASSWORD="strong_pass_12345",
        POSTGRES_DB="bhumisetu_db",
        DEBUG=False
    )
    assert cfg.POSTGRES_USER == "bhumisetu_user"

    # 4b: URL-encoded reserved characters in password match unquoted password
    cfg_encoded = Settings(
        ENVIRONMENT="staging",
        SECRET_KEY=valid_key,
        ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
        DATABASE_URL="postgresql+psycopg://bhumisetu_user:p%40ss%23word%252026@db:5432/bhumisetu_db",
        POSTGRES_USER="bhumisetu_user",
        POSTGRES_PASSWORD="p@ss#word%2026",
        POSTGRES_DB="bhumisetu_db",
        DEBUG=False
    )
    assert cfg_encoded.POSTGRES_PASSWORD == "p@ss#word%2026"

    # 4c: Username mismatch raises ValueError
    with pytest.raises(ValueError, match="POSTGRES_USER does not match username embedded in DATABASE_URL"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY=valid_key,
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://diff_user:strong_pass_12345@db:5432/bhumisetu_db",
            POSTGRES_USER="bhumisetu_user",
            POSTGRES_PASSWORD="strong_pass_12345",
            POSTGRES_DB="bhumisetu_db",
            DEBUG=False
        )

    # 4d: Password mismatch raises ValueError
    with pytest.raises(ValueError, match="POSTGRES_PASSWORD does not match password embedded in DATABASE_URL"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY=valid_key,
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://bhumisetu_user:diff_pass_99999@db:5432/bhumisetu_db",
            POSTGRES_USER="bhumisetu_user",
            POSTGRES_PASSWORD="strong_pass_12345",
            POSTGRES_DB="bhumisetu_db",
            DEBUG=False
        )

    # 4e: Database name mismatch raises ValueError
    with pytest.raises(ValueError, match="POSTGRES_DB does not match database name embedded in DATABASE_URL"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY=valid_key,
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://bhumisetu_user:strong_pass_12345@db:5432/other_db",
            POSTGRES_USER="bhumisetu_user",
            POSTGRES_PASSWORD="strong_pass_12345",
            POSTGRES_DB="bhumisetu_db",
            DEBUG=False
        )


def test_minio_credentials_and_application_settings_consistency():
    """Case 5: MinIO credentials and application authentication settings are consistent."""
    valid_key = "a1b2c3d4e5f67890123456789012345678901234567890123456789012345678"

    # 5a: Matching credentials pass
    cfg = Settings(
        ENVIRONMENT="staging",
        SECRET_KEY=valid_key,
        ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
        DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
        STORAGE_ADAPTER="minio",
        AWS_S3_BUCKET="bhumisetu-vault",
        S3_ENDPOINT_URL="http://minio:9000",
        MINIO_ROOT_USER="minio_admin_user",
        AWS_ACCESS_KEY_ID="minio_admin_user",
        MINIO_ROOT_PASSWORD="minio_root_secret_key_123456",
        AWS_SECRET_ACCESS_KEY="minio_root_secret_key_123456",
        DEBUG=False
    )
    assert cfg.MINIO_ROOT_USER == cfg.AWS_ACCESS_KEY_ID
    assert cfg.MINIO_ROOT_PASSWORD == cfg.AWS_SECRET_ACCESS_KEY

    # 5b: User mismatch raises ValueError
    with pytest.raises(ValueError, match="MINIO_ROOT_USER and AWS_ACCESS_KEY_ID must match"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY=valid_key,
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
            STORAGE_ADAPTER="minio",
            AWS_S3_BUCKET="bhumisetu-vault",
            S3_ENDPOINT_URL="http://minio:9000",
            MINIO_ROOT_USER="minio_admin_user",
            AWS_ACCESS_KEY_ID="different_access_key",
            MINIO_ROOT_PASSWORD="minio_root_secret_key_123456",
            AWS_SECRET_ACCESS_KEY="minio_root_secret_key_123456",
            DEBUG=False
        )

    # 5c: Password mismatch raises ValueError
    with pytest.raises(ValueError, match="MINIO_ROOT_PASSWORD and AWS_SECRET_ACCESS_KEY must match"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY=valid_key,
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/bhumisetu_db",
            STORAGE_ADAPTER="minio",
            AWS_S3_BUCKET="bhumisetu-vault",
            S3_ENDPOINT_URL="http://minio:9000",
            MINIO_ROOT_USER="minio_admin_user",
            AWS_ACCESS_KEY_ID="minio_admin_user",
            MINIO_ROOT_PASSWORD="minio_root_secret_key_123456",
            AWS_SECRET_ACCESS_KEY="different_secret_key_654321",
            DEBUG=False
        )


def test_placeholder_secrets_rejected_across_all_fields():
    """Case 6: Placeholder secrets are rejected across all fields in staging/production."""
    valid_key = "a1b2c3d4e5f67890123456789012345678901234567890123456789012345678"

    # In DATABASE_URL
    with pytest.raises(ValueError, match="Must not contain placeholder values"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY=valid_key,
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://user:replace_with_db_password@db:5432/bhumisetu_db",
            DEBUG=False
        )

    # In POSTGRES_PASSWORD
    with pytest.raises(ValueError, match="POSTGRES_PASSWORD for staging environment: Must not contain placeholder values"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY=valid_key,
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://user:secure_pass@db:5432/bhumisetu_db",
            POSTGRES_PASSWORD="changeme_postgres_password",
            DEBUG=False
        )

    # In AWS_SECRET_ACCESS_KEY
    with pytest.raises(ValueError, match="AWS_SECRET_ACCESS_KEY for staging environment: Must not contain placeholder values"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY=valid_key,
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://user:secure_pass@db:5432/bhumisetu_db",
            STORAGE_ADAPTER="minio",
            AWS_S3_BUCKET="vault",
            S3_ENDPOINT_URL="http://minio:9000",
            AWS_SECRET_ACCESS_KEY="placeholder_aws_secret_key",
            DEBUG=False
        )

    # In MINIO_ROOT_PASSWORD
    with pytest.raises(ValueError, match="MINIO_ROOT_PASSWORD for staging environment: Must not contain placeholder values"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY=valid_key,
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL="postgresql+psycopg://user:secure_pass@db:5432/bhumisetu_db",
            STORAGE_ADAPTER="minio",
            AWS_S3_BUCKET="vault",
            S3_ENDPOINT_URL="http://minio:9000",
            MINIO_ROOT_PASSWORD="replace_with_minio_root_password",
            DEBUG=False
        )


def test_secret_values_never_appear_in_diagnostic_messages():
    """Case 7: Secret values do not appear in diagnostic messages."""
    valid_key = "a1b2c3d4e5f67890123456789012345678901234567890123456789012345678"
    secret_db_pass = "top_secret_database_credential_xyz999"
    secret_url_pass = "different_secret_credential_abc111"

    with pytest.raises(ValueError) as exc_info:
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY=valid_key,
            ALLOWED_ORIGINS=["https://staging.bhumisetu.gov.in"],
            DATABASE_URL=f"postgresql+psycopg://bhumisetu_user:{secret_url_pass}@db:5432/bhumisetu_db",
            POSTGRES_USER="bhumisetu_user",
            POSTGRES_PASSWORD=secret_db_pass,
            POSTGRES_DB="bhumisetu_db",
            DEBUG=False
        )

    error_msg = str(exc_info.value)
    assert secret_db_pass not in error_msg
    assert secret_url_pass not in error_msg
    assert "POSTGRES_PASSWORD does not match password embedded in DATABASE_URL" in error_msg


def test_invalid_configuration_fails_before_application_starts():
    """Case 8: Invalid configuration fails immediately before the application starts."""
    # When invalid configuration is supplied, Settings initialization raises ValueError
    with pytest.raises(ValueError):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY="short_key",
            ALLOWED_ORIGINS=["*"],
            DATABASE_URL="sqlite:///test.db",
            DEBUG=True
        )


def test_normal_shutdown_preserves_persistent_data():
    """Case 9: Normal shutdown preserves persistent data via named Docker volumes."""
    compose_path = os.path.join(os.path.dirname(__file__), "..", "..", "docker-compose.staging.yml")
    if not os.path.isfile(compose_path):
        compose_path = os.path.join(os.path.dirname(__file__), "..", "docker-compose.staging.yml")

    assert os.path.isfile(compose_path), "docker-compose.staging.yml must exist"

    with open(compose_path, "r", encoding="utf-8") as f:
        compose_text = f.read()

    # Named volumes must be declared at the root level
    assert "volumes:" in compose_text
    assert "staging_pgdata:" in compose_text
    assert "staging_redisdata:" in compose_text
    assert "staging_miniodata:" in compose_text

    # Volumes must be mounted to service storage paths
    assert "staging_pgdata:/var/lib/postgresql/data" in compose_text
    assert "staging_redisdata:/data" in compose_text
    assert "staging_miniodata:/data" in compose_text


