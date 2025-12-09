"""
Custom exceptions for the application.

This provides:
1. Specific exception types for different error scenarios
2. HTTP status code mapping
3. User-friendly error messages
4. Error context preservation
"""

from typing import Any, Dict, Optional


class AppException(Exception):
    """Base exception class for application-specific errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(AppException):
    """Raised when input validation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


class AuthenticationError(AppException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class AuthorizationError(AppException):
    """Raised when user doesn't have permission for an operation."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, status_code=403)


class NotFoundError(AppException):
    """Raised when requested resource is not found."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ConflictError(AppException):
    """Raised when operation conflicts with current state."""

    def __init__(self, message: str = "Conflict with current state"):
        super().__init__(message, status_code=409)


class ServiceError(AppException):
    """Raised when business logic operation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)


class ExternalServiceError(AppException):
    """Raised when external service call fails."""

    def __init__(self, service: str, message: str = "External service error"):
        super().__init__(f"{service}: {message}", status_code=502)
