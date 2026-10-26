"""
Judicial Source Providers Package.

Exposes base interfaces, domain exceptions, and factory function.
"""

from typing import Optional

from app.config import settings
from app.services.judicial.providers.base import (
    JudicialSourceProvider,
    JudicialSourceError,
    JudicialSourceUnavailableError,
    JudicialRateLimitError,
    JudicialCaptchaRequiredError,
    JudicialSSRFBlockedError,
    JudicialInvalidQueryError,
)
from app.services.judicial.providers.mock_provider import MockJudicialProvider, SEED_MOCK_CASES
from app.services.judicial.providers.ecourts_provider import (
    ECourtsBiharProvider,
    ALLOWED_JUDICIAL_DOMAINS,
    validate_judicial_url,
)
from app.services.judicial.providers.operator_import import OperatorImportProvider, parse_property_schedule

_mock_singleton: Optional[MockJudicialProvider] = None
_operator_singleton: Optional[OperatorImportProvider] = None


def get_judicial_provider(provider_type: Optional[str] = None) -> JudicialSourceProvider:
    """
    Returns the appropriate judicial source provider based on runtime configuration
    or explicit provider_type argument.
    """
    global _mock_singleton, _operator_singleton

    # Check configuration override or parameter
    effective_type = (provider_type or getattr(settings, "JUDICIAL_PROVIDER_TYPE", "MOCK")).upper()

    if effective_type in ("MOCK", "SIMULATION", "TEST"):
        if _mock_singleton is None:
            _mock_singleton = MockJudicialProvider()
        return _mock_singleton

    if effective_type in ("OPERATOR", "MANUAL", "OPERATOR_IMPORT"):
        if _operator_singleton is None:
            _operator_singleton = OperatorImportProvider()
        return _operator_singleton

    if effective_type in ("ECOURTS", "LIVE", "PATNA_HIGH_COURT"):
        return ECourtsBiharProvider()

    # Default fallback to Mock to ensure offline safety and deterministic CI
    if _mock_singleton is None:
        _mock_singleton = MockJudicialProvider()
    return _mock_singleton


__all__ = [
    "JudicialSourceProvider",
    "JudicialSourceError",
    "JudicialSourceUnavailableError",
    "JudicialRateLimitError",
    "JudicialCaptchaRequiredError",
    "JudicialSSRFBlockedError",
    "JudicialInvalidQueryError",
    "MockJudicialProvider",
    "SEED_MOCK_CASES",
    "ECourtsBiharProvider",
    "ALLOWED_JUDICIAL_DOMAINS",
    "validate_judicial_url",
    "OperatorImportProvider",
    "parse_property_schedule",
    "get_judicial_provider",
]
