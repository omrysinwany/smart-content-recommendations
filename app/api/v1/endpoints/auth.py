"""
Authentication API endpoints.

This provides:
1. User registration and login
2. Token refresh and validation
3. Password reset workflow
4. Email verification
5. User profile access
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.security import get_current_active_user, require_admin
from app.database import get_db
from app.schemas.auth import (
    APIError,
    AuthenticationResponse,
    CurrentUserResponse,
    EmailVerificationRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegistrationRequest,
)
from app.services.auth_service import AuthService
from app.services.user_service import UserService

# Create router with tags for API documentation
router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
    responses={
        401: {"model": APIError, "description": "Authentication failed"},
        422: {"model": APIError, "description": "Validation error"},
    },
)


@router.post(
    "/register",
    response_model=AuthenticationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password validation.",
    responses={
        201: {"description": "User registered successfully"},
        409: {"model": APIError, "description": "Email already exists"},
        422: {"model": APIError, "description": "Validation failed"},
    },
)
async def register(
    user_data: UserRegistrationRequest, db: AsyncSession = Depends(get_db)
) -> AuthenticationResponse:
    """
    Register a new user account.

    **Business Rules:**
    - Email must be unique
    - Password must meet security requirements
    - Terms and conditions must be accepted
    - Returns authentication tokens for immediate login

    **Password Requirements:**
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    """
    try:
        auth_service = AuthService(db)

        result = await auth_service.register_user(
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            terms_accepted=user_data.terms_accepted,
        )

        return AuthenticationResponse(**result)

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "ValidationError",
                "message": str(e),
                "details": {"field": "registration_data"},
            },
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "ConflictError",
                "message": str(e),
                "details": {"field": "email"},
            },
        )


@router.post(
    "/login",
    response_model=AuthenticationResponse,
    summary="Authenticate user",
    description="Authenticate user with email and password, return JWT tokens.",
    responses={
        200: {"description": "Login successful"},
        401: {"model": APIError, "description": "Invalid credentials"},
    },
)
async def login(
    credentials: UserLoginRequest, db: AsyncSession = Depends(get_db)
) -> AuthenticationResponse:
    """
    Authenticate user and return JWT tokens.

    **Features:**
    - Email and password validation
    - Remember me option for extended sessions
    - Automatic last login update
    - Role-based token generation
    """
    try:
        auth_service = AuthService(db)

        result = await auth_service.authenticate_user(
            email=credentials.email,
            password=credentials.password,
            remember_me=credentials.remember_me,
        )

        return AuthenticationResponse(**result)

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "AuthenticationError",
                "message": str(e),
                "details": {"field": "credentials"},
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Generate new access token using refresh token.",
    responses={
        200: {"description": "Token refreshed successfully"},
        401: {"model": APIError, "description": "Invalid refresh token"},
    },
)
async def refresh_token(
    token_data: TokenRefreshRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """
    Refresh JWT access token.

    **Security Features:**
    - Validates refresh token signature and expiration
    - Verifies user still exists and is active
    - Generates new access and refresh tokens
    - Logs token refresh events
    """
    try:
        auth_service = AuthService(db)

        result = await auth_service.refresh_token(token_data.refresh_token)

        return TokenResponse(**result["tokens"])

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "AuthenticationError",
                "message": str(e),
                "details": {"field": "refresh_token"},
            },
        )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get current user",
    description="Get current authenticated user information.",
    dependencies=[Depends(get_current_active_user)],
    responses={
        200: {"description": "Current user information"},
        401: {"model": APIError, "description": "Authentication required"},
    },
)
async def get_current_user(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CurrentUserResponse:
    """
    Get current authenticated user information.

    **Requires:** Valid JWT token in Authorization header

    **Returns:** Complete user profile with activity information
    """
    try:
        user_service = UserService(db)

        # Get detailed user profile
        user_profile = await user_service.get_user_profile(current_user["user_id"])
        user_data = user_profile["user"]

        return CurrentUserResponse(
            id=user_data["id"],
            email=user_data["email"],
            full_name=user_data["full_name"],
            is_verified=user_data["is_verified"],
            role=current_user.get("role", "user"),
            is_active=True,  # Must be active to get token
            created_at=user_data["created_at"],
            last_active=None,  # Would get from user data
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NotFoundError", "message": str(e)},
        )


@router.post(
    "/password-reset",
    response_model=MessageResponse,
    summary="Initiate password reset",
    description="Send password reset email to user.",
    responses={
        200: {"description": "Password reset email sent (if account exists)"},
    },
)
async def initiate_password_reset(
    reset_data: PasswordResetRequest, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """
    Initiate password reset process.

    **Security Features:**
    - Always returns success message (doesn't reveal if email exists)
    - Generates time-limited reset tokens (1 hour expiration)
    - Logs password reset attempts
    - Rate limiting should be implemented in production
    """
    auth_service = AuthService(db)

    result = await auth_service.initiate_password_reset(reset_data.email)

    return MessageResponse(message=result["message"])


@router.post(
    "/password-reset/confirm",
    response_model=MessageResponse,
    summary="Confirm password reset",
    description="Reset password using reset token.",
    responses={
        200: {"description": "Password reset successful"},
        401: {"model": APIError, "description": "Invalid or expired token"},
        422: {"model": APIError, "description": "Invalid password"},
    },
)
async def confirm_password_reset(
    reset_data: PasswordResetConfirmRequest, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """
    Complete password reset process.

    **Validation:**
    - Verifies reset token signature and expiration
    - Validates new password strength
    - Updates password and invalidates reset token
    - Logs security event
    """
    try:
        auth_service = AuthService(db)

        result = await auth_service.reset_password(
            reset_token=reset_data.reset_token, new_password=reset_data.new_password
        )

        return MessageResponse(message=result["message"])

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "AuthenticationError",
                "message": str(e),
                "details": {"field": "reset_token"},
            },
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "ValidationError",
                "message": str(e),
                "details": {"field": "new_password"},
            },
        )


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Verify email address",
    description="Verify user email using verification token.",
    responses={
        200: {"description": "Email verified successfully"},
        401: {"model": APIError, "description": "Invalid verification token"},
    },
)
async def verify_email(
    verification_data: EmailVerificationRequest, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """
    Verify user email address.

    **Process:**
    - Validates verification token
    - Updates user verification status
    - Logs verification event
    - Enables full account features
    """
    try:
        auth_service = AuthService(db)

        result = await auth_service.verify_user_email(
            verification_token=verification_data.verification_token
        )

        return MessageResponse(message=result["message"])

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "AuthenticationError",
                "message": str(e),
                "details": {"field": "verification_token"},
            },
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NotFoundError", "message": str(e)},
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout user",
    description="Logout current user (client-side token removal).",
    dependencies=[Depends(get_current_active_user)],
    responses={
        200: {"description": "Logout successful"},
        401: {"model": APIError, "description": "Authentication required"},
    },
)
async def logout(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> MessageResponse:
    """
    Logout current user.

    **Note:** JWT tokens are stateless, so logout is primarily client-side.
    In production, you might implement:
    - Token blacklisting
    - Database token revocation
    - Redis token invalidation
    """
    # In production, add token to blacklist or revocation list
    # await token_blacklist.add(current_token)

    return MessageResponse(
        message=f"User {current_user['email']} logged out successfully"
    )


# Admin-only endpoints


@router.get(
    "/admin/users",
    summary="List all users (Admin only)",
    description="Get list of all users in the system.",
    dependencies=[Depends(require_admin)],
    responses={
        200: {"description": "List of all users"},
        403: {"model": APIError, "description": "Admin access required"},
    },
)
async def list_all_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin_user: Dict[str, Any] = Depends(require_admin),
):
    """
    Get list of all users (admin only).

    **Admin Features:**
    - Pagination support
    - User statistics
    - Activity information
    - Account status
    """
    user_service = UserService(db)

    # This would be implemented in UserService
    # users = await user_service.get_all_users_admin(skip=skip, limit=limit)

    return {
        "message": "Admin endpoint - would return user list",
        "requested_by": admin_user["email"],
        "pagination": {"skip": skip, "limit": limit},
    }
