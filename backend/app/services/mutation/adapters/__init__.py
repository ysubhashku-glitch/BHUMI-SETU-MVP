"""
Mutation Adapters Module.

Exposes source providers for Bihar Bhumi public portal, operator-assisted ingestion,
and synthetic test suites, along with unified domain exceptions.
"""

from typing import Optional

from app.services.mutation.adapters.base import (
    MutationSourceAdapter,
    AdapterHealthStatus,
    MutationSourceError,
    MutationNotFoundError,
    MutationSourceUnavailableError,
    MutationRateLimitError,
    MutationCaptchaRequiredError,
    MutationSSRFBlockedError,
    MutationInvalidQueryError,
)
from app.services.mutation.adapters.bihar_bhumi_adapter import BiharBhumiAdapter
from app.services.mutation.adapters.operator_import_adapter import OperatorImportAdapter
from app.services.mutation.adapters.mock_adapter import MockMutationAdapter, PILOT_MUTATION_CASES

_default_adapter: Optional[MutationSourceAdapter] = None


def get_mutation_adapter(adapter_name: Optional[str] = None) -> MutationSourceAdapter:
    """
    Factory function returning the configured or requested mutation source adapter.
    Defaults to MockMutationAdapter in offline/testing mode, or BiharBhumiAdapter if requested.
    """
    name = (adapter_name or "MOCK_ADAPTER").upper()
    if name in ("BIHAR_BHUMI", "BIHAR_BHUMI_HTTP"):
        return BiharBhumiAdapter()
    elif name in ("OPERATOR", "OPERATOR_ASSISTED"):
        return OperatorImportAdapter()
    elif name in ("MOCK", "MOCK_ADAPTER"):
        return MockMutationAdapter()
    else:
        return MockMutationAdapter()


__all__ = [
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
    "PILOT_MUTATION_CASES",
    "get_mutation_adapter",
]
