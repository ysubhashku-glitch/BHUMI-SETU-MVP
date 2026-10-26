import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Regex pattern for redacting sensitive fields in messages and dictionary dumps
SENSITIVE_KEY_PATTERN = re.compile(
    r'(?i)(password|secret|token|bearer|authorization|private_key|api_key|access_key|secret_key|credential|jwt)'
)
TOKEN_VALUE_PATTERN = re.compile(
    r'(?i)(bearer\s+)([A-Za-z0-9\-._~+/]+=*)'
)
INLINE_SECRET_PATTERN = re.compile(
    r'(?i)(password|secret|token|api_key|access_key)\s*[:=\s]\s*([^\s,;]+)'
)

def redact_sensitive_data(data: Any) -> Any:
    """
    Recursively redacts sensitive keys from dictionaries, lists, or strings.
    """
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            if SENSITIVE_KEY_PATTERN.search(str(k)):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_sensitive_data(v)
        return redacted
    elif isinstance(data, (list, tuple)):
        return [redact_sensitive_data(item) for item in data]
    elif isinstance(data, str):
        # Redact Bearer tokens in plain text strings
        text = TOKEN_VALUE_PATTERN.sub(r'\1[REDACTED]', data)
        return INLINE_SECRET_PATTERN.sub(r'\1 [REDACTED]', text)
    return data


class StructuredJsonFormatter(logging.Formatter):
    """
    Production-grade JSON log formatter with automatic secret redaction,
    correlation ID extraction, and ISO 8601 UTC timestamps.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_data(record.getMessage()),
            "module": record.module,
            "funcName": record.funcName,
            "lineNo": record.lineno,
        }

        # Extract contextual attributes if attached to record
        if hasattr(record, "request_id"):
            log_entry["request_id"] = getattr(record, "request_id")
        if hasattr(record, "org_id"):
            log_entry["org_id"] = getattr(record, "org_id")
        if hasattr(record, "user_id"):
            log_entry["user_id"] = getattr(record, "user_id")
        if hasattr(record, "case_id"):
            log_entry["case_id"] = getattr(record, "case_id")
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_entry["data"] = redact_sensitive_data(record.extra_data)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(environment: str = "development") -> None:
    """
    Configures structured logging for BhumiSetu services.
    Uses StructuredJsonFormatter in staging/production, and standard readable formatting in dev.
    """
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler()
    if environment in ("staging", "production"):
        handler.setFormatter(StructuredJsonFormatter())
        root_logger.setLevel(logging.INFO)
    else:
        readable_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        handler.setFormatter(logging.Formatter(readable_fmt))
        root_logger.setLevel(logging.INFO)

    root_logger.addHandler(handler)
    logging.getLogger("bhumisetu").setLevel(logging.INFO)
