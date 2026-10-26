"""
Mutation Intelligence Package (TASK-P2-05).

Provides end-to-end processing of Bihar Dakhil-Kharij proceedings,
lifecycle state management, anti-name-only entity resolution,
reconciliation, and Property Passport timeline integration.
"""

from app.services.mutation.service import MutationService
from app.services.mutation.extractor import MutationExtractor
from app.services.mutation.matcher import MutationEntityResolver
from app.services.mutation.lifecycle import MutationLifecycleEngine
from app.services.mutation.passport_timeline import PropertyPassportTimelineBuilder
from app.services.mutation.reconciliation import MutationReconciliationEngine
from app.services.mutation.adapters import (
    MutationSourceAdapter,
    AdapterHealthStatus,
    MutationSourceError,
    MutationNotFoundError,
    MutationSourceUnavailableError,
    MutationRateLimitError,
    MutationCaptchaRequiredError,
    MutationSSRFBlockedError,
    MutationInvalidQueryError,
    BiharBhumiAdapter,
    OperatorImportAdapter,
    MockMutationAdapter,
    get_mutation_adapter,
)

__all__ = [
    "MutationService",
    "MutationExtractor",
    "MutationEntityResolver",
    "MutationLifecycleEngine",
    "PropertyPassportTimelineBuilder",
    "MutationReconciliationEngine",
    "MutationSourceAdapter",
    "AdapterHealthStatus",
    "MutationSourceError",
    "MutationNotFoundError",
    "MutationSourceUnavailableError",
    "MutationRateLimitError",
    "MutationCaptchaRequiredError",
    "MutationSSRFBlockedError",
    "MutationInvalidQueryError",
    "BiharBhumiAdapter",
    "OperatorImportAdapter",
    "MockMutationAdapter",
    "get_mutation_adapter",
]
