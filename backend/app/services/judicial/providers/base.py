"""
Judicial Source Provider Abstract Base Class and Domain Exceptions.

Defines the contract for court data acquisition from eCourts, Patna High Court,
and operator-assisted ingestion channels.
"""

from __future__ import annotations

import abc
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.exceptions import BhumiSetuException
from app.schemas.judicial import JudicialCaseRecord, JudicialSearchQuery


# =====================================================================
# Domain Exceptions for Judicial Retrieval
# =====================================================================

class JudicialSourceError(BhumiSetuException):
    """Base exception for all judicial intelligence retrieval errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class JudicialSourceUnavailableError(JudicialSourceError):
    """Raised when the official court portal is unreachable or down."""
    pass


class JudicialRateLimitError(JudicialSourceError):
    """Raised when portal request limits have been exceeded."""
    pass


class JudicialCaptchaRequiredError(JudicialSourceError):
    """
    Raised when an interactive visual/audio CAPTCHA is required.
    Automated circumvention is strictly prohibited by system security controls.
    """
    pass


class JudicialSSRFBlockedError(JudicialSourceError):
    """Raised when an outbound URL violates judicial domain whitelisting."""
    pass


class JudicialInvalidQueryError(JudicialSourceError):
    """Raised when court search parameters are invalid or malformed."""
    pass


# =====================================================================
# Provider Interface
# =====================================================================

class JudicialSourceProvider(abc.ABC):
    """
    Abstract interface for court docket and proceeding providers.
    All implementations must respect source access rules, rate limits,
    and return normalized JudicialCaseRecord structures.
    """

    @property
    @abc.abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for the provider (e.g., 'ECOURTS_BIHAR', 'PATNA_HIGH_COURT', 'MOCK_PROVIDER')."""
        pass

    @abc.abstractmethod
    async def search_cases(
        self,
        query: JudicialSearchQuery,
        timeout_seconds: float = 10.0,
    ) -> List[JudicialCaseRecord]:
        """
        Search court proceedings matching the specified query criteria.
        Returns a list of normalized JudicialCaseRecord objects.
        """
        pass

    @abc.abstractmethod
    async def get_case_by_cnr(
        self,
        cnr_number: str,
        timeout_seconds: float = 10.0,
    ) -> Optional[JudicialCaseRecord]:
        """
        Directly retrieve a specific case by its 16-character CNR number.
        Returns None if not found in the source registry.
        """
        pass

    @abc.abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check provider operational status, connectivity, and rate-limit latency."""
        pass
