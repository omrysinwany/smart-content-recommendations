"""
Security utilities for authentication and authorization.

This provides:
1. JWT token creation and validation
2. Password hashing and verification
3. Security dependencies for FastAPI
4. Role-based access control
"""

from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token scheme
security = HTTPBearer()


class SecurityManager:
    """
    Centralized security management for the application.
    
    This class demonstrates security best practices:
    - Secure password hashing
    - JWT token management
    - Token validation and expiration
    - Role-based access control
    """
    
    def __init__(self):
        self.secret_key = settings.secret_key
        self.algorithm = settings.algorithm
        self.access_token_expire_minutes = settings.access_token_expire_minutes
    
    def create_password_hash(self, password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password string
        """
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Previously hashed password
            
        Returns:
            True if password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(
        self, 
        data: Dict[str, Any], 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT access token.
        
        Args:
            data: Data to encode in the token (user_id, email, etc.)
            expires_delta: Optional custom expiration time
            
        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        
        # Set expiration time
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        # Add standard JWT claims
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),  # Issued at
            "type": "access_token"
        })
        
        # Encode token
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """
        Create a JWT refresh token (longer expiration).
        
        Args:
            data: Data to encode in the token
            
        Returns:
            Encoded JWT refresh token
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=7)  # 7 days for refresh tokens
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh_token"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and validate a JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload
            
        Raises:
            AuthenticationError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            raise AuthenticationError(f"Could not validate token: {str(e)}")
    
    def extract_user_from_token(self, token: str) -> Dict[str, Any]:
        """
        Extract user information from a JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            User information from token
            
        Raises:
            AuthenticationError: If token is invalid or doesn't contain user info
        """
        payload = self.decode_token(token)
        
        # Validate required fields
        user_id = payload.get("user_id")
        email = payload.get("email")
        
        if not user_id or not email:
            raise AuthenticationError("Token does not contain valid user information")
        
        return {
            "user_id": user_id,
            "email": email,
            "role": payload.get("role", "user"),
            "is_active": payload.get("is_active", True)
        }


# Global security manager instance
security_manager = SecurityManager()


# FastAPI Dependencies for authentication
async def get_current_user_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    FastAPI dependency to extract current user from JWT token.
    
    This is used in route handlers like:
    @app.get("/protected")
    async def protected_route(current_user: dict = Depends(get_current_user_token)):
        return {"user_id": current_user["user_id"]}
    
    Args:
        credentials: HTTP Bearer token from request
        
    Returns:
        Current user information
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        token = credentials.credentials
        user_info = security_manager.extract_user_from_token(token)
        
        # Check if user is active
        if not user_info.get("is_active"):
            raise AuthenticationError("User account is inactive")
        
        return user_info
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user_token)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get active user (alias for readability).
    
    Args:
        current_user: User info from token
        
    Returns:
        Active user information
    """
    return current_user


class RoleChecker:
    """
    Role-based access control checker.
    
    This allows route-level permissions:
    @app.get("/admin", dependencies=[Depends(RoleChecker(["admin"]))])
    async def admin_only_route():
        return {"message": "Admin access granted"}
    """
    
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles
    
    def __call__(self, current_user: Dict[str, Any] = Depends(get_current_user_token)):
        user_role = current_user.get("role", "user")
        
        if user_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(self.allowed_roles)}"
            )
        
        return current_user


# Pre-defined role checkers for common use cases
require_admin = RoleChecker(["admin"])
require_moderator = RoleChecker(["admin", "moderator"])
require_verified_user = RoleChecker(["admin", "moderator", "verified_user"])


def create_user_token_data(
    user_id: int,
    email: str,
    role: str = "user",
    is_active: bool = True,
    additional_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Helper function to create token data for a user.
    
    Args:
        user_id: User's database ID
        email: User's email
        role: User's role (user, admin, moderator)
        is_active: Whether user is active
        additional_data: Optional additional claims
        
    Returns:
        Token data dictionary
    """
    token_data = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "is_active": is_active
    }
    
    if additional_data:
        token_data.update(additional_data)
    
    return token_data


# Optional: API Key authentication for service-to-service communication
class APIKeyChecker:
    """
    API Key authentication for service-to-service communication.
    
    Usage:
    @app.get("/api", dependencies=[Depends(APIKeyChecker())])
    async def api_endpoint():
        return {"message": "API access granted"}
    """
    
    def __init__(self, api_key_name: str = "X-API-Key"):
        self.api_key_name = api_key_name
    
    def __call__(self, api_key: str = Depends(lambda: None)):  # Would get from header
        # In production, validate against database or environment variable
        valid_api_keys = [
            settings.secret_key,  # Simple example
            # Add more API keys as needed
        ]
        
        if api_key not in valid_api_keys:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        return {"api_key": api_key}