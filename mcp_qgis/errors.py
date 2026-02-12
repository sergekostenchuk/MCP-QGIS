from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ErrorPayload:
    code: str
    message: str
    details: dict[str, Any]
    retryable: bool = False


class MCPQGISError(Exception):
    code = "E_INTERNAL"
    retryable = False

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_payload(self) -> ErrorPayload:
        return ErrorPayload(
            code=self.code,
            message=self.message,
            details=self.details,
            retryable=self.retryable,
        )


class ValidationError(MCPQGISError):
    code = "E_VALIDATION"


class ConflictError(MCPQGISError):
    code = "E_CONFLICT"


class NotFoundError(MCPQGISError):
    code = "E_NOT_FOUND"


class PreconditionError(MCPQGISError):
    code = "E_PRECONDITION"


class AuthForbiddenError(MCPQGISError):
    code = "E_AUTH_FORBIDDEN"
