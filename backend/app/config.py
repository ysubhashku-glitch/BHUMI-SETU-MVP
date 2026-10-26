import os
from typing import List, Optional, Union
from pydantic import model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "BhumiSetu Land Intelligence Platform"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")  # 'development', 'test', 'staging', 'production'
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # CORS Origins (Comma-separated in env, JSON array, or list)
    ALLOWED_ORIGINS: Union[str, List[str]] = ["*"]
    
    # Database: PostgreSQL 16 + PostGIS 3.4
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://bhumisetu_user:bhumisetu_secure_password_2026@localhost:5432/bhumisetu_db"
    )
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))
    POSTGRES_USER: Optional[str] = os.getenv("POSTGRES_USER", None)
    POSTGRES_PASSWORD: Optional[str] = os.getenv("POSTGRES_PASSWORD", None)
    POSTGRES_DB: Optional[str] = os.getenv("POSTGRES_DB", None)
    
    # JWT Authentication
    SECRET_KEY: str = os.getenv("SECRET_KEY", "bhumisetu-insecure-dev-secret-key-change-in-prod-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Evidence Vault Object Storage
    STORAGE_ADAPTER: str = os.getenv("STORAGE_ADAPTER", "local")  # 'local', 's3', 'minio'
    STORAGE_DIR: str = os.getenv("STORAGE_DIR", "./storage/documents")
    AWS_S3_BUCKET: Optional[str] = os.getenv("AWS_S3_BUCKET", None)
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID", None)
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY", None)
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-south-1")
    S3_ENDPOINT_URL: Optional[str] = os.getenv("S3_ENDPOINT_URL", None)  # e.g., http://minio:9000
    S3_USE_SSL: bool = os.getenv("S3_USE_SSL", "true").lower() in ("true", "1", "yes")
    MINIO_ROOT_USER: Optional[str] = os.getenv("MINIO_ROOT_USER", None)
    MINIO_ROOT_PASSWORD: Optional[str] = os.getenv("MINIO_ROOT_PASSWORD", None)
    MINIO_DEDICATED_APP_IDENTITY: bool = os.getenv("MINIO_DEDICATED_APP_IDENTITY", "false").lower() in ("true", "1", "yes")

    # Redis & Asynchronous Worker Workloads
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    ASYNC_PROCESSING: bool = os.getenv("ASYNC_PROCESSING", "false").lower() in ("true", "1", "yes")
    
    # Operational Boundaries & Public Verification
    DEFAULT_TENANT_NAME: str = "BhumiSetu Operations (Deoghar)"
    DEFAULT_TENANT_SLUG: str = "bhumisetu-deoghar"
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "https://bhumisetu.gov.in")
    
    # Model Context Protocol (MCP) Governed Agent Interface
    MCP_ENABLED: bool = os.getenv("MCP_ENABLED", "true").lower() in ("true", "1", "yes")
    MCP_SERVER_NAME: str = os.getenv("MCP_SERVER_NAME", "bhumi-setu-agent-mcp")
    MCP_TRANSPORT: str = os.getenv("MCP_TRANSPORT", "stdio")  # 'stdio' or 'sse'
    MCP_HOST: str = os.getenv("MCP_HOST", "127.0.0.1")
    MCP_PORT: int = int(os.getenv("MCP_PORT", "8001"))
    MCP_ALLOW_STATE_MUTATIONS: bool = os.getenv("MCP_ALLOW_STATE_MUTATIONS", "true").lower() in ("true", "1", "yes")

    @field_validator("ALLOWED_ORIGINS", mode="after")
    @classmethod
    def parse_allowed_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("[") and v_str.endswith("]"):
                try:
                    import json
                    return json.loads(v_str)
                except Exception:
                    pass
            if v_str == "*":
                return ["*"]
            return [origin.strip() for origin in v_str.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def validate_staging_production_security(self) -> "Settings":
        """
        Enforces strict fail-safe security gates when running in staging or production.
        Prevents accidental startup with insecure dev defaults.
        """
        env = self.ENVIRONMENT.lower()
        if env in ("staging", "production"):
            # 1. Reject default, placeholder, exposed, or weak SECRET_KEY
            insecure_markers = [
                "bhumisetu-insecure",
                "insecure-dev",
                "change-in-prod",
                "default-secret",
                "dev-secret",
                "replace_with",
                "placeholder",
                "changeme",
                "your_secret",
                "secret_key",
            ]
            key_stripped = (self.SECRET_KEY or "").strip()
            key_lower = key_stripped.lower()

            # Reject known historical exposed keys (must be rotated)
            exposed_keys = {
                "c8b7a6d5e4f3a2b10987654321fedcba0123456789abcdef0123456789abcdef",
            }
            if key_lower in exposed_keys:
                raise ValueError(
                    f"Invalid SECRET_KEY for {env} environment: The supplied secret matches an exposed "
                    f"historical key that has been compromised and must be rotated."
                )

            if not key_stripped or len(key_stripped) < 32 or any(marker in key_lower for marker in insecure_markers):
                raise ValueError(
                    f"Invalid SECRET_KEY for {env} environment: Must be a non-default, "
                    f"cryptographically random secret of at least 32 characters."
                )

            # Reject low-entropy or repetitive secrets (e.g. all same character)
            if len(set(key_stripped)) < 8:
                raise ValueError(
                    f"Invalid SECRET_KEY for {env} environment: Secret lacks sufficient cryptographic "
                    f"entropy (too few unique characters)."
                )


            # 2. Reject Wildcard CORS in staging/production
            if "*" in self.ALLOWED_ORIGINS:
                raise ValueError(
                    f"Wildcard CORS allowed_origins ['*'] is strictly forbidden in {env}. "
                    f"Configure explicit origins (e.g. 'https://staging.bhumisetu.gov.in')."
                )

            # 3. Reject SQLite in staging/production
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError(
                    f"SQLite is prohibited in {env}. PostgreSQL with PostGIS must be configured."
                )

            # 4. Reject placeholders across all credential fields
            placeholder_markers = ["replace_with", "placeholder", "changeme", "your_secret", "change_me"]
            if any(pm in self.DATABASE_URL.lower() for pm in placeholder_markers):
                raise ValueError(
                    f"Invalid DATABASE_URL for {env} environment: Must not contain placeholder values."
                )
            if self.POSTGRES_PASSWORD and any(pm in self.POSTGRES_PASSWORD.lower() for pm in placeholder_markers):
                raise ValueError(
                    f"Invalid POSTGRES_PASSWORD for {env} environment: Must not contain placeholder values."
                )
            if self.AWS_SECRET_ACCESS_KEY and any(pm in self.AWS_SECRET_ACCESS_KEY.lower() for pm in placeholder_markers):
                raise ValueError(
                    f"Invalid AWS_SECRET_ACCESS_KEY for {env} environment: Must not contain placeholder values."
                )
            if self.MINIO_ROOT_PASSWORD and any(pm in self.MINIO_ROOT_PASSWORD.lower() for pm in placeholder_markers):
                raise ValueError(
                    f"Invalid MINIO_ROOT_PASSWORD for {env} environment: Must not contain placeholder values."
                )

            # 5. Database credential consistency verification
            from urllib.parse import urlsplit, unquote
            if self.DATABASE_URL and not self.DATABASE_URL.startswith("sqlite"):
                try:
                    parsed_db = urlsplit(self.DATABASE_URL)
                    db_user = parsed_db.username
                    db_pass = unquote(parsed_db.password) if parsed_db.password is not None else None
                    db_name = parsed_db.path.lstrip("/") if parsed_db.path else None

                    if self.POSTGRES_USER and db_user and self.POSTGRES_USER != db_user:
                        raise ValueError(
                            f"Database credential inconsistency in {env}: POSTGRES_USER "
                            f"does not match username embedded in DATABASE_URL."
                        )
                    if self.POSTGRES_PASSWORD and db_pass and self.POSTGRES_PASSWORD != db_pass:
                        raise ValueError(
                            f"Database credential inconsistency in {env}: POSTGRES_PASSWORD "
                            f"does not match password embedded in DATABASE_URL."
                        )
                    if self.POSTGRES_DB and db_name and self.POSTGRES_DB != db_name:
                        raise ValueError(
                            f"Database credential inconsistency in {env}: POSTGRES_DB "
                            f"does not match database name embedded in DATABASE_URL."
                        )
                except ValueError as ve:
                    raise ve
                except Exception:
                    pass

            # 6. Storage configuration validation
            if self.STORAGE_ADAPTER == "s3" and not self.AWS_S3_BUCKET:
                raise ValueError(f"AWS_S3_BUCKET must be specified when STORAGE_ADAPTER is 's3' in {env}.")

            if self.STORAGE_ADAPTER == "minio":
                if not self.AWS_S3_BUCKET:
                    raise ValueError(f"AWS_S3_BUCKET must be specified when STORAGE_ADAPTER is 'minio' in {env}.")
                if not self.S3_ENDPOINT_URL:
                    raise ValueError(
                        f"MinIO configuration error in {env}: S3_ENDPOINT_URL must be specified when STORAGE_ADAPTER is 'minio'."
                    )

                # MinIO credential consistency verification
                if not self.MINIO_DEDICATED_APP_IDENTITY:
                    if self.MINIO_ROOT_USER and self.AWS_ACCESS_KEY_ID and self.MINIO_ROOT_USER != self.AWS_ACCESS_KEY_ID:
                        raise ValueError(
                            f"MinIO credential inconsistency in {env}: MINIO_ROOT_USER "
                            f"and AWS_ACCESS_KEY_ID must match when STORAGE_ADAPTER is 'minio'."
                        )
                    elif self.MINIO_ROOT_USER and not self.AWS_ACCESS_KEY_ID:
                        self.AWS_ACCESS_KEY_ID = self.MINIO_ROOT_USER

                    if self.MINIO_ROOT_PASSWORD and self.AWS_SECRET_ACCESS_KEY and self.MINIO_ROOT_PASSWORD != self.AWS_SECRET_ACCESS_KEY:
                        raise ValueError(
                            f"MinIO credential inconsistency in {env}: MINIO_ROOT_PASSWORD "
                            f"and AWS_SECRET_ACCESS_KEY must match when STORAGE_ADAPTER is 'minio'."
                        )
                    elif self.MINIO_ROOT_PASSWORD and not self.AWS_SECRET_ACCESS_KEY:
                        self.AWS_SECRET_ACCESS_KEY = self.MINIO_ROOT_PASSWORD
                else:
                    # In dedicated least-privilege mode, AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY represent the scoped app user
                    if not self.AWS_ACCESS_KEY_ID or not self.AWS_SECRET_ACCESS_KEY:
                        raise ValueError(
                            f"MinIO configuration error in {env}: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY "
                            f"must be provided when MINIO_DEDICATED_APP_IDENTITY is enabled."
                        )

            # 7. Disable debug mode in staging/production
            if self.DEBUG:
                raise ValueError(f"DEBUG mode must be FALSE in {env}.")

        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
