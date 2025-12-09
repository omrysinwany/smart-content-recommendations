"""
Authentication Service - Business logic for user authentication.

This provides:
1. User registration workflow
2. Login/logout operations
3. Token refresh functionality
4. Password reset workflow
5. User verification processes
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.security import create_user_token_data, security_manager
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.base import BaseService
from app.services.user_service import UserService


class AuthService(BaseService):
    """
    Authentication service handling all auth-related business logic.

    This demonstrates advanced authentication patterns:
    - Secure registration workflow
    - Multi-step authentication
    - Token management
    - Security event logging
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.user_repo = UserRepository(db)
        self.user_service = UserService(db)

    async def register_user(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        terms_accepted: bool = False,
    ) -> Dict[str, Any]:
        """
        Register a new user with comprehensive validation.

        Business rules:
        1. Email must be unique and valid
        2. Password must meet security requirements
        3. Terms must be accepted
        4. User starts unverified
        5. Return tokens for immediate login

        Args:
            email: User's email address
            password: Plain text password
            full_name: Optional full name
            terms_accepted: Whether user accepted terms

        Returns:
            Dictionary with user info and tokens

        Raises:
            ValidationError: If validation fails
            ConflictError: If email already exists
        """
        self._log_operation("register_user", email=email)

        try:
            # Business validation
            self._validate_registration_data(email, password, terms_accepted)

            # Check if user already exists
            existing_user = await self.user_repo.get_by_email(email)
            if existing_user:
                raise ConflictError("User with this email already exists")

            # Create user using user service
            user = await self.user_service.create_user(email, password, full_name)

            # Generate tokens for immediate login
            tokens = self._generate_user_tokens(user)

            # Log security event
            self.logger.info(f"User registered successfully: {user.id}")

            return {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "is_verified": user.is_verified,
                    "created_at": user.created_at,
                },
                "tokens": tokens,
                "message": "Registration successful. Please verify your email.",
            }

        except Exception as error:
            await self._handle_service_error(error, "register user")

    async def authenticate_user(
        self, email: str, password: str, remember_me: bool = False
    ) -> Dict[str, Any]:
        """
        Authenticate user and return tokens.

        Args:
            email: User's email
            password: Plain text password
            remember_me: Whether to extend token expiration

        Returns:
            Dictionary with user info and tokens

        Raises:
            AuthenticationError: If authentication fails
        """
        self._log_operation("authenticate_user", email=email)

        try:
            # Attempt authentication
            user = await self.user_service.authenticate_user(email, password)

            if not user:
                raise AuthenticationError("Invalid email or password")

            # Generate tokens
            token_expiry = timedelta(days=30) if remember_me else None
            tokens = self._generate_user_tokens(user, token_expiry)

            # Update last login time
            await self.user_repo.update(user.id, {"last_active": datetime.utcnow()})

            self.logger.info(f"User authenticated successfully: {user.id}")

            return {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "is_verified": user.is_verified,
                    "role": (
                        "admin" if user.email.endswith("@admin.com") else "user"
                    ),  # Simple role logic
                    "created_at": user.created_at,
                },
                "tokens": tokens,
                "message": "Login successful",
            }

        except Exception as error:
            # Don't reveal details for security
            if isinstance(error, AuthenticationError):
                raise error
            await self._handle_service_error(error, "authenticate user")

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Generate new access token from refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            New access and refresh tokens

        Raises:
            AuthenticationError: If refresh token is invalid
        """
        self._log_operation("refresh_token")

        try:
            # Decode refresh token
            payload = security_manager.decode_token(refresh_token)

            # Validate token type
            if payload.get("type") != "refresh_token":
                raise AuthenticationError("Invalid token type")

            # Get user information
            user_id = payload.get("user_id")
            email = payload.get("email")

            if not user_id or not email:
                raise AuthenticationError("Invalid token payload")

            # Verify user still exists and is active
            user = await self.user_repo.get(user_id)
            if not user or not user.is_active or user.email != email:
                raise AuthenticationError("User not found or inactive")

            # Generate new tokens
            tokens = self._generate_user_tokens(user)

            self.logger.info(f"Token refreshed for user: {user.id}")

            return {"tokens": tokens, "message": "Token refreshed successfully"}

        except Exception as error:
            if isinstance(error, AuthenticationError):
                raise error
            await self._handle_service_error(error, "refresh token")

    async def initiate_password_reset(self, email: str) -> Dict[str, Any]:
        """
        Initiate password reset process.

        Args:
            email: User's email address

        Returns:
            Success message (always success for security)
        """
        self._log_operation("initiate_password_reset", email=email)

        try:
            # Always return success for security (don't reveal if email exists)
            user = await self.user_repo.get_by_email(email)

            if user and user.is_active:
                # Generate reset token (short expiration)
                reset_token_data = {
                    "user_id": user.id,
                    "email": user.email,
                    "type": "password_reset",
                    "purpose": "reset_password",
                }

                reset_token = security_manager.create_access_token(
                    reset_token_data,
                    expires_delta=timedelta(hours=1),  # 1 hour expiration
                )

                # In production, send email with reset link
                # await self.email_service.send_password_reset(user.email, reset_token)

                self.logger.info(f"Password reset initiated for user: {user.id}")

                # For development, return token (remove in production)
                return {
                    "message": "Password reset email sent",
                    "reset_token": reset_token,  # Remove in production
                }

            # Always return same message for security
            return {
                "message": "If an account with that email exists, a password reset link has been sent."
            }

        except Exception as error:
            await self._handle_service_error(error, "initiate password reset")

    async def reset_password(
        self, reset_token: str, new_password: str
    ) -> Dict[str, Any]:
        """
        Reset user password using reset token.

        Args:
            reset_token: Password reset token
            new_password: New password

        Returns:
            Success message

        Raises:
            AuthenticationError: If token is invalid
            ValidationError: If password is invalid
        """
        self._log_operation("reset_password")

        try:
            # Decode reset token
            payload = security_manager.decode_token(reset_token)

            # Validate token purpose
            if payload.get("purpose") != "reset_password":
                raise AuthenticationError("Invalid reset token")

            user_id = payload.get("user_id")
            if not user_id:
                raise AuthenticationError("Invalid token payload")

            # Get user
            user = await self.user_repo.get(user_id)
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")

            # Validate new password
            if len(new_password) < 8:
                raise ValidationError("Password must be at least 8 characters")

            # Update password
            hashed_password = security_manager.create_password_hash(new_password)
            await self.user_repo.update(user_id, {"hashed_password": hashed_password})

            self.logger.info(f"Password reset successful for user: {user.id}")

            return {"message": "Password reset successful"}

        except Exception as error:
            if isinstance(error, (AuthenticationError, ValidationError)):
                raise error
            await self._handle_service_error(error, "reset password")

    async def verify_user_email(self, verification_token: str) -> Dict[str, Any]:
        """
        Verify user email using verification token.

        Args:
            verification_token: Email verification token

        Returns:
            Success message
        """
        self._log_operation("verify_user_email")

        try:
            # Decode verification token
            payload = security_manager.decode_token(verification_token)

            user_id = payload.get("user_id")
            if not user_id:
                raise AuthenticationError("Invalid verification token")

            # Update user verification status
            user = await self.user_repo.update(user_id, {"is_verified": True})

            if not user:
                raise NotFoundError("User not found")

            self.logger.info(f"Email verified for user: {user.id}")

            return {"message": "Email verification successful"}

        except Exception as error:
            if isinstance(error, (AuthenticationError, NotFoundError)):
                raise error
            await self._handle_service_error(error, "verify user email")

    # Private helper methods

    def _validate_registration_data(
        self, email: str, password: str, terms_accepted: bool
    ) -> None:
        """Validate registration data according to business rules"""
        # Email validation
        if not email or "@" not in email:
            raise ValidationError("Invalid email address")

        # Password validation
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters")

        if not any(c.isupper() for c in password):
            raise ValidationError("Password must contain at least one uppercase letter")

        if not any(c.isdigit() for c in password):
            raise ValidationError("Password must contain at least one number")

        # Terms validation
        if not terms_accepted:
            raise ValidationError("Terms and conditions must be accepted")

    def _generate_user_tokens(
        self, user: User, access_token_expiry: Optional[timedelta] = None
    ) -> Dict[str, str]:
        """Generate access and refresh tokens for user"""
        # Determine user role (simple logic for demo)
        role = "admin" if user.email.endswith("@admin.com") else "user"

        # Create token data
        token_data = create_user_token_data(
            user_id=user.id,
            email=user.email,
            role=role,
            is_active=user.is_active,
            additional_data={"is_verified": user.is_verified},
        )

        # Generate tokens
        access_token = security_manager.create_access_token(
            token_data, expires_delta=access_token_expiry
        )

        refresh_token = security_manager.create_refresh_token(token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
