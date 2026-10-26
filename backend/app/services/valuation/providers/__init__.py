"""
Valuation Providers Package.

Exposes base interfaces, domain exceptions, and provider factory.
"""

from typing import Optional

from app.config import settings
from app.services.valuation.providers.base import (
    ValuationSourceProvider,
    ValuationSourceError,
    MVRRateNotFoundError,
    ValuationSourceUnavailableError,
    ValuationRateLimitError,
    ValuationCaptchaRequiredError,
    ValuationSSRFBlockedError,
    InvalidJurisdictionError,
)
from app.services.valuation.providers.mock_provider import MockValuationProvider, SEED_MVR_SCHEDULES
from app.services.valuation.providers.enibandhan_provider import (
    ENibandhanBiharProvider,
    ALLOWED_VALUATION_DOMAINS,
    validate_valuation_url,
)
from app.services.valuation.providers.operator_import import (
    OperatorImportValuationProvider,
    generate_schedule_code,
)

_mock_singleton: Optional[MockValuationProvider] = None
_operator_singleton: Optional[OperatorImportValuationProvider] = None


def get_valuation_provider(provider_type: Optional[str] = None) -> ValuationSourceProvider:
    """
    Returns the appropriate MVR circle rate provider based on configuration or parameter.
    """
    global _mock_singleton, _operator_singleton

    effective_type = (provider_type or getattr(settings, "VALUATION_PROVIDER_TYPE", "MOCK")).upper()

    if effective_type in ("MOCK", "SIMULATION", "TEST"):
        if _mock_singleton is None:
            _mock_singleton = MockValuationProvider()
        return _mock_singleton

    if effective_type in ("OPERATOR", "MANUAL", "OPERATOR_IMPORT"):
        if _operator_singleton is None:
            _operator_singleton = OperatorImportValuationProvider()
        return _operator_singleton

    if effective_type in ("ENIBANDHAN", "LIVE", "BHUMIJANKARI"):
        return ENibandhanBiharProvider()

    # Default fallback to mock for safe offline/CI behavior
    if _mock_singleton is None:
        _mock_singleton = MockValuationProvider()
    return _mock_singleton


__all__ = [
    "ValuationSourceProvider",
    "ValuationSourceError",
    "MVRRateNotFoundError",
    "ValuationSourceUnavailableError",
    "ValuationRateLimitError",
    "ValuationCaptchaRequiredError",
    "ValuationSSRFBlockedError",
    "InvalidJurisdictionError",
    "MockValuationProvider",
    "SEED_MVR_SCHEDULES",
    "ENibandhanBiharProvider",
    "ALLOWED_VALUATION_DOMAINS",
    "validate_valuation_url",
    "OperatorImportValuationProvider",
    "generate_schedule_code",
    "get_valuation_provider",
]
