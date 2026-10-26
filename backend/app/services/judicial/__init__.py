"""
Judicial Risk Intelligence Subsystem for Bhumi Setu.

Provides official eCourts, District Court, and Patna High Court docket integration,
deterministic parcel-to-case entity resolution, active injunction detection,
and operator-assisted workflow.
"""

from app.services.judicial.providers import (
    JudicialSourceProvider,
    JudicialSourceError,
    JudicialSourceUnavailableError,
    JudicialRateLimitError,
    JudicialCaptchaRequiredError,
    JudicialSSRFBlockedError,
    JudicialInvalidQueryError,
    MockJudicialProvider,
    ECourtsBiharProvider,
    OperatorImportProvider,
    get_judicial_provider,
)
from app.services.judicial.matcher import JudicialEntityResolver, normalize_legal_name, token_overlap_score
from app.services.judicial.classifier import JudicialRiskClassifier
from app.services.judicial.service import JudicialService

__all__ = [
    "JudicialSourceProvider",
    "JudicialSourceError",
    "JudicialSourceUnavailableError",
    "JudicialRateLimitError",
    "JudicialCaptchaRequiredError",
    "JudicialSSRFBlockedError",
    "JudicialInvalidQueryError",
    "MockJudicialProvider",
    "ECourtsBiharProvider",
    "OperatorImportProvider",
    "get_judicial_provider",
    "JudicialEntityResolver",
    "normalize_legal_name",
    "token_overlap_score",
    "JudicialRiskClassifier",
    "JudicialService",
]
