"""
Valuation Source Provider Interface and Domain Exceptions.

Defines the contract for retrieving, validating, and normalizing government
Minimum Valuation Register (MVR) / Circle Rate schedules across Bihar.
"""

from __future__ import annotations

import abc
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.exceptions import BhumiSetuException
from app.schemas.valuation import MVRScheduleRecord, MVRScheduleSearchQuery


# =====================================================================
# Domain Exceptions for MVR / Valuation
# =====================================================================

class ValuationSourceError(BhumiSetuException):
    """Base exception for all valuation and MVR schedule errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class MVRRateNotFoundError(ValuationSourceError):
    """Raised when no verified MVR circle rate exists for a specific jurisdiction/category."""
    pass


class ValuationSourceUnavailableError(ValuationSourceError):
    """Raised when the official registration portal is unreachable or down."""
    pass


class ValuationRateLimitError(ValuationSourceError):
    """Raised when portal request limits have been exceeded."""
    pass


class ValuationCaptchaRequiredError(ValuationSourceError):
    """Raised when an interactive CAPTCHA is required by the portal."""
    pass


class ValuationSSRFBlockedError(ValuationSourceError):
    """Raised when an outbound URL violates valuation domain whitelisting."""
    pass


class InvalidJurisdictionError(ValuationSourceError):
    """Raised when district, circle, or mauza identifiers are invalid or contradictory."""
    pass


# =====================================================================
# Valuation Provider Interface
# =====================================================================

class ValuationSourceProvider(abc.ABC):
    """
    Abstract interface for MVR circle rate providers.
    All implementations must return normalized MVRScheduleRecord objects
    with explicit provenance and verification status.
    """

    @property
    @abc.abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier (e.g., 'ENIBANDHAN_BIHAR_OFFICIAL', 'MOCK_MVR_PROVIDER')."""
        pass

    @abc.abstractmethod
    async def search_schedules(
        self,
        query: MVRScheduleSearchQuery,
        timeout_seconds: float = 10.0,
    ) -> List[MVRScheduleRecord]:
        """
        Search MVR schedules matching the given jurisdiction and property traits.
        """
        pass

    @abc.abstractmethod
    async def get_schedule_by_code(
        self,
        schedule_code: str,
        timeout_seconds: float = 10.0,
    ) -> Optional[MVRScheduleRecord]:
        """
        Directly retrieve an MVR schedule by its unique schedule code.
        """
        pass

    @abc.abstractmethod
    async def get_district_coverage(self) -> List[Dict[str, Any]]:
        """
        Returns coverage summary indicating which districts and anchals
        have verified, provisional, or unavailable circle rate schedules.
        """
        pass

    @abc.abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check provider operational status and upstream reachability."""
        pass
