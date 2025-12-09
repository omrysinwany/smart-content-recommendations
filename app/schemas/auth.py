"""
Authentication schemas for request/response validation.

This provides:
1. Request validation schemas
2. Response formatting schemas
3. Token validation schemas
4. Type safety for authentication endpoints
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field, validator


class UserRegistrationRequest(BaseModel):
    """Schema for user registration requests."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="User's password (min 8 characters)",
    )
    full_name: Optional[str] = Field(
        None, max_length=255, description="User's full name"
    )
    terms_accepted: bool = Field(
        ..., description="Whether user accepted terms and conditions"
    )

    @validator("password")
    def validate_password_strength(cls, v):
        """Validate password meets security requirements"""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")

        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")

        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")

        # Optional: Check for special characters
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in v):
            raise ValueError("Password must contain at least one special character")

        return v

    @validator("terms_accepted")
    def validate_terms_accepted(cls, v):
        """Ensure terms are accepted"""
        if not v:
            raise ValueError("Terms and conditions must be accepted")
        return v

    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!",
                "full_name": "John Doe",
                "terms_accepted": True,
            }
        }


class UserLoginRequest(BaseModel):
    """Schema for user login requests."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")
    remember_me: bool = Field(
        default=False, description="Whether to keep user logged in longer"
    )

    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!",
                "remember_me": False,
            }
        }


class TokenRefreshRequest(BaseModel):
    """Schema for token refresh requests."""

    refresh_token: str = Field(..., description="Valid refresh token")

    class Config:
        schema_extra = {
            "example": {"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
        }


class PasswordResetRequest(BaseModel):
    """Schema for password reset initiation."""

    email: EmailStr = Field(..., description="Email address to send reset link")

    class Config:
        schema_extra = {"example": {"email": "user@example.com"}}


class PasswordResetConfirmRequest(BaseModel):
    """Schema for password reset confirmation."""

    reset_token: str = Field(..., description="Password reset token from email")
    new_password: str = Field(
        ..., min_length=8, max_length=100, description="New password"
    )

    @validator("new_password")
    def validate_password_strength(cls, v):
        """Validate new password meets security requirements"""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")

        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")

        return v

    class Config:
        schema_extra = {
            "example": {
                "reset_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "new_password": "NewSecurePass123!",
            }
        }


class EmailVerificationRequest(BaseModel):
    """Schema for email verification."""

    verification_token: str = Field(..., description="Email verification token")

    class Config:
        schema_extra = {
            "example": {"verification_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
        }


# Response Schemas


class TokenResponse(BaseModel):
    """Schema for authentication token responses."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: Optional[int] = Field(
        default=1800, description="Access token expiration time in seconds"
    )

    class Config:
        schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
            }
        }


class UserInfoResponse(BaseModel):
    """Schema for user information in auth responses."""

    id: int = Field(..., description="User's unique ID")
    email: str = Field(..., description="User's email address")
    full_name: Optional[str] = Field(None, description="User's full name")
    is_verified: bool = Field(..., description="Whether email is verified")
    role: str = Field(default="user", description="User's role")
    created_at: datetime = Field(..., description="Account creation timestamp")

    class Config:
        orm_mode = True  # Allow creation from SQLAlchemy models
        schema_extra = {
            "example": {
                "id": 1,
                "email": "user@example.com",
                "full_name": "John Doe",
                "is_verified": True,
                "role": "user",
                "created_at": "2024-01-15T10:30:00Z",
            }
        }


class AuthenticationResponse(BaseModel):
    """Schema for complete authentication responses."""

    user: UserInfoResponse = Field(..., description="User information")
    tokens: TokenResponse = Field(..., description="Authentication tokens")
    message: str = Field(..., description="Success message")

    class Config:
        schema_extra = {
            "example": {
                "user": {
                    "id": 1,
                    "email": "user@example.com",
                    "full_name": "John Doe",
                    "is_verified": True,
                    "role": "user",
                    "created_at": "2024-01-15T10:30:00Z",
                },
                "tokens": {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 1800,
                },
                "message": "Login successful",
            }
        }


class MessageResponse(BaseModel):
    """Schema for simple message responses."""

    message: str = Field(..., description="Response message")

    class Config:
        schema_extra = {"example": {"message": "Operation completed successfully"}}


class CurrentUserResponse(BaseModel):
    """Schema for current user information."""

    id: int = Field(..., description="User's unique ID")
    email: str = Field(..., description="User's email address")
    full_name: Optional[str] = Field(None, description="User's full name")
    is_verified: bool = Field(..., description="Whether email is verified")
    role: str = Field(..., description="User's role")
    is_active: bool = Field(..., description="Whether account is active")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_active: Optional[datetime] = Field(None, description="Last activity timestamp")

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "id": 1,
                "email": "user@example.com",
                "full_name": "John Doe",
                "is_verified": True,
                "role": "user",
                "is_active": True,
                "created_at": "2024-01-15T10:30:00Z",
                "last_active": "2024-01-20T15:45:00Z",
            }
        }


# Token validation schemas for internal use


class TokenPayload(BaseModel):
    """Schema for JWT token payload validation."""

    user_id: int
    email: str
    role: str = "user"
    is_active: bool = True
    is_verified: bool = False
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp
    type: str  # Token type (access_token, refresh_token, etc.)


class APIError(BaseModel):
    """Schema for API error responses."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )

    class Config:
        schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Password must contain at least one uppercase letter",
                "details": {"field": "password", "code": "password_strength"},
            }
        }
