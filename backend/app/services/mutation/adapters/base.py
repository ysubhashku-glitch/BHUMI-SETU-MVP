"""
Mutation Source Adapter Abstract Base Class and Domain Exceptions.

Defines the contract for Bihar Dakhil-Kharij (Mutation) data acquisition
from official state portals, operator-assisted ingestion channels, and synthetic test suites.
"""

from __future__ import annotations

import abc
from enum import Enum
from typing import Dict, Any, List, Optional
from app.core.exceptions import BhumiSetuException


class AdapterHealthStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    MANUAL_IMPORT_REQUIRED = "MANUAL_IMPORT_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


# =====================================================================
# Domain Exceptions for Mutation Retrieval
# =====================================================================

class MutationSourceError(BhumiSetuException):
    """Base exception for all mutation intelligence retrieval errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class MutationNotFoundError(MutationSourceError):
    """Raised when the specified mutation petition or case is not found."""
    pass


class MutationSourceUnavailableError(MutationSourceError):
    """Raised when the official Bihar Bhumi portal is unreachable or down."""
    pass


class MutationRateLimitError(MutationSourceError):
    """Raised when portal request limits have been exceeded."""
    pass


class MutationCaptchaRequiredError(MutationSourceError):
    """
    Raised when an interactive visual or session CAPTCHA is required.
    Automated circumvention is strictly prohibited by security and compliance policies.
    """
    pass


class MutationSSRFBlockedError(MutationSourceError):
    """Raised when an outbound URL violates mutation domain whitelisting."""
    pass


class MutationInvalidQueryError(MutationSourceError):
    """Raised when query parameters are malformed or missing mandatory geographic filters."""
    pass


# =====================================================================
# Adapter Interface
# =====================================================================

class MutationSourceAdapter(abc.ABC):
    """
    Abstract interface for Bihar mutation proceedings and docket providers.
    All implementations must respect source access rules, rate limits,
    preserve raw payloads, and normalize results without fabricating missing fields.
    """

    @property
    @abc.abstractmethod
    def adapter_name(self) -> str:
        """Unique identifier for the adapter (e.g. 'BIHAR_BHUMI_HTTP', 'OPERATOR_ASSISTED', 'MOCK_ADAPTER')."""
        pass

    @property
    @abc.abstractmethod
    def health_status(self) -> AdapterHealthStatus:
        """Current operational and access status of the provider."""
        pass

    @abc.abstractmethod
    async def search_cases(
        self,
        district: str,
        circle: str,
        mauza: Optional[str] = None,
        khata_number: Optional[str] = None,
        khesra_number: Optional[str] = None,
        case_number: Optional[str] = None,
        deed_number: Optional[str] = None,
        applicant_name: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ) -> List[Dict[str, Any]]:
        """
        Search mutation cases matching the specified parameters.
        Returns a list of raw or structured case dictionaries.
        """
        pass

    @abc.abstractmethod
    async def get_case_detail(
        self,
        case_number: str,
        district: str,
        circle: str,
        timeout_seconds: float = 10.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve complete details for a specific mutation case.
        Returns None if not found.
        """
        pass

    @abc.abstractmethod
    async def get_case_events(
        self,
        case_number: str,
        district: str,
        circle: str,
        timeout_seconds: float = 10.0,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve chronological lifecycle events (notices, reports, orders) for a case.
        """
        pass

    @abc.abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check provider operational status, connectivity, and rate-limit latency.
        """
        pass
