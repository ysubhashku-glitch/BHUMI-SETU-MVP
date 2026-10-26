from typing import Optional, Any
from fastapi import HTTPException, status

class BhumiSetuException(Exception):
    def __init__(
        self,
        code: str,
        message: Optional[str] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Any] = None
    ):
        if message is None:
            message = code
            code = "BHUMISETU_ERROR"
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

class EntityNotFoundError(BhumiSetuException):
    def __init__(self, entity_name: str, entity_id: Any):
        super().__init__(
            code="ENTITY_NOT_FOUND",
            message=f"{entity_name} with identifier '{entity_id}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"entity_name": entity_name, "entity_id": str(entity_id)}
        )

class CrossTenantAccessError(BhumiSetuException):
    def __init__(self, message: str = "Access to the requested resource across tenant boundary is prohibited."):
        super().__init__(
            code="CROSS_TENANT_ACCESS_DENIED",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN
        )

class StateTransitionError(BhumiSetuException):
    def __init__(self, current_state: str, attempted_state: str, reason: str):
        super().__init__(
            code="STATE_TRANSITION_ERROR",
            message=f"Cannot transition case from '{current_state}' to '{attempted_state}': {reason}",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"current_state": current_state, "attempted_state": attempted_state, "reason": reason}
        )

class UnauthorizedError(BhumiSetuException):
    def __init__(self, message: str = "Invalid or expired authentication credentials."):
        super().__init__(
            code="AUTHENTICATION_FAILED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )

# Alias for convenience
AuthenticationError = UnauthorizedError

class ForbiddenError(BhumiSetuException):
    def __init__(self, message: str = "Insufficient permissions to perform this operation."):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN
        )

class DomainValidationError(BhumiSetuException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            code="DOMAIN_VALIDATION_ERROR",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )

class BusinessRuleViolationError(BhumiSetuException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            code="BUSINESS_RULE_VIOLATION",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )

