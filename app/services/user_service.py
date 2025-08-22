"""
User Service - Business logic for user operations.

This provides:
1. User registration and authentication logic
2. Profile management operations
3. Follow/unfollow business rules
4. User preferences and settings
5. User analytics and statistics
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.services.base import BaseService
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.core.exceptions import (
    ValidationError, 
    AuthenticationError, 
    NotFoundError, 
    ConflictError
)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService(BaseService):
    """
    User service handling all user-related business logic.
    
    This demonstrates the Service layer pattern:
    - Coordinates multiple repositories
    - Implements business rules
    - Handles complex workflows
    - Validates business constraints
    """
    
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.user_repo = UserRepository(db)
    
    async def create_user(
        self, 
        email: str, 
        password: str, 
        full_name: Optional[str] = None
    ) -> User:
        """
        Create a new user with business validation.
        
        Business rules:
        1. Email must be unique
        2. Password must be hashed
        3. User starts as unverified
        4. Default preferences are set
        
        Args:
            email: User's email address
            password: Plain text password
            full_name: Optional full name
            
        Returns:
            Created user instance
            
        Raises:
            ValidationError: If email format is invalid
            ConflictError: If email already exists
        """
        self._log_operation("create_user", email=email)
        
        try:
            # Business validation
            if not self._is_valid_email(email):
                raise ValidationError("Invalid email format")
            
            if len(password) < 8:
                raise ValidationError("Password must be at least 8 characters")
            
            # Check if user already exists
            existing_user = await self.user_repo.get_by_email(email)
            if existing_user:
                raise ConflictError("User with this email already exists")
            
            # Hash password
            hashed_password = self._hash_password(password)
            
            # Create user data
            user_data = {
                "email": email.lower().strip(),
                "hashed_password": hashed_password,
                "full_name": full_name,
                "is_active": True,
                "is_verified": False,
                "preferences": self._get_default_preferences(),
                "total_interactions": 0
            }
            
            # Create user
            user = await self.user_repo.create(user_data)
            
            self.logger.info(f"User created successfully: {user.id}")
            return user
            
        except Exception as error:
            await self._handle_service_error(error, "create user")
    
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate user with email and password.
        
        Business rules:
        1. User must exist and be active
        2. Password must match
        3. Update last_active timestamp
        
        Args:
            email: User's email
            password: Plain text password
            
        Returns:
            User instance if authentication successful, None otherwise
        """
        self._log_operation("authenticate_user", email=email)
        
        try:
            # Get user by email
            user = await self.user_repo.get_by_email(email.lower().strip())
            
            if not user or not user.is_active:
                return None
            
            # Verify password
            if not self._verify_password(password, user.hashed_password):
                return None
            
            # Update last active (business logic)
            await self.user_repo.update(user.id, {"last_active": "now()"})
            
            self.logger.info(f"User authenticated successfully: {user.id}")
            return user
            
        except Exception as error:
            self.logger.error(f"Authentication error: {error}")
            return None
    
    async def get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive user profile with statistics.
        
        This demonstrates service orchestration:
        - Combines data from multiple sources
        - Applies business logic
        - Formats response
        
        Args:
            user_id: User's ID
            
        Returns:
            Complete user profile with stats
            
        Raises:
            NotFoundError: If user doesn't exist
        """
        self._log_operation("get_user_profile", user_id=user_id)
        
        try:
            # Get user with stats (using repository)
            user_data = await self.user_repo.get_user_with_stats(user_id)
            
            if not user_data:
                raise NotFoundError("User not found")
            
            user = user_data["user"]
            stats = user_data["stats"]
            
            # Apply business logic for profile completeness
            profile_completeness = self._calculate_profile_completeness(user)
            
            # Format response
            return {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "bio": user.bio,
                    "avatar_url": user.avatar_url,
                    "is_verified": user.is_verified,
                    "created_at": user.created_at
                },
                "stats": stats,
                "profile_completeness": profile_completeness,
                "reputation_score": self._calculate_reputation_score(stats)
            }
            
        except Exception as error:
            await self._handle_service_error(error, "get user profile")
    
    async def follow_user(self, follower_id: int, followed_id: int) -> bool:
        """
        Handle user following with business rules.
        
        Business rules:
        1. Can't follow yourself
        2. Can't follow the same user twice
        3. Both users must exist and be active
        
        Args:
            follower_id: ID of user who wants to follow
            followed_id: ID of user to be followed
            
        Returns:
            True if follow was successful
            
        Raises:
            ValidationError: If trying to follow yourself
            NotFoundError: If either user doesn't exist
        """
        self._log_operation("follow_user", follower_id=follower_id, followed_id=followed_id)
        
        try:
            # Business validation
            if follower_id == followed_id:
                raise ValidationError("Cannot follow yourself")
            
            # Check if both users exist and are active
            follower = await self.user_repo.get(follower_id)
            followed = await self.user_repo.get(followed_id)
            
            if not follower or not follower.is_active:
                raise NotFoundError("Follower not found or inactive")
            
            if not followed or not followed.is_active:
                raise NotFoundError("User to follow not found or inactive")
            
            # Create follow relationship
            success = await self.user_repo.follow_user(follower_id, followed_id)
            
            if success:
                self.logger.info(f"Follow created: {follower_id} -> {followed_id}")
            else:
                self.logger.info(f"Follow already exists: {follower_id} -> {followed_id}")
            
            return success
            
        except Exception as error:
            await self._handle_service_error(error, "follow user")
    
    async def unfollow_user(self, follower_id: int, followed_id: int) -> bool:
        """
        Handle user unfollowing.
        
        Args:
            follower_id: ID of user who wants to unfollow
            followed_id: ID of user to be unfollowed
            
        Returns:
            True if unfollow was successful
        """
        self._log_operation("unfollow_user", follower_id=follower_id, followed_id=followed_id)
        
        try:
            success = await self.user_repo.unfollow_user(follower_id, followed_id)
            
            if success:
                self.logger.info(f"Unfollow successful: {follower_id} -> {followed_id}")
            
            return success
            
        except Exception as error:
            await self._handle_service_error(error, "unfollow user")
    
    async def update_user_preferences(
        self, 
        user_id: int, 
        preferences: Dict[str, Any]
    ) -> User:
        """
        Update user preferences with validation.
        
        Business rules:
        1. Validate preference structure
        2. Merge with existing preferences
        3. Apply business constraints
        
        Args:
            user_id: User's ID
            preferences: New preferences to set
            
        Returns:
            Updated user instance
        """
        self._log_operation("update_preferences", user_id=user_id)
        
        try:
            # Get current user
            user = await self.user_repo.get(user_id)
            if not user:
                raise NotFoundError("User not found")
            
            # Validate and merge preferences
            validated_prefs = self._validate_preferences(preferences)
            current_prefs = user.preferences or {}
            merged_prefs = {**current_prefs, **validated_prefs}
            
            # Update user
            updated_user = await self.user_repo.update(
                user_id, 
                {"preferences": merged_prefs}
            )
            
            return updated_user
            
        except Exception as error:
            await self._handle_service_error(error, "update user preferences")
    
    # Private helper methods (business logic)
    
    def _is_valid_email(self, email: str) -> bool:
        """Simple email validation"""
        return "@" in email and "." in email.split("@")[1]
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return pwd_context.hash(password)
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def _get_default_preferences(self) -> Dict[str, Any]:
        """Get default user preferences"""
        return {
            "categories": [],
            "max_recommendations": 20,
            "email_notifications": True,
            "content_types": ["article", "video"]
        }
    
    def _calculate_profile_completeness(self, user: User) -> float:
        """Calculate profile completeness percentage"""
        total_fields = 5
        completed_fields = 0
        
        if user.full_name:
            completed_fields += 1
        if user.bio:
            completed_fields += 1
        if user.avatar_url:
            completed_fields += 1
        if user.is_verified:
            completed_fields += 1
        if user.preferences and len(user.preferences.get("categories", [])) > 0:
            completed_fields += 1
        
        return (completed_fields / total_fields) * 100
    
    def _calculate_reputation_score(self, stats: Dict[str, Any]) -> int:
        """Calculate user reputation based on activity"""
        follower_count = stats.get("follower_count", 0)
        content_count = stats.get("content_count", 0)
        total_interactions = stats.get("total_interactions", 0)
        
        return (follower_count * 10) + (content_count * 5) + total_interactions
    
    def _validate_preferences(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user preferences structure"""
        valid_prefs = {}
        
        # Validate categories
        if "categories" in preferences:
            categories = preferences["categories"]
            if isinstance(categories, list) and len(categories) <= 10:
                valid_prefs["categories"] = categories
        
        # Validate max_recommendations
        if "max_recommendations" in preferences:
            max_recs = preferences["max_recommendations"]
            if isinstance(max_recs, int) and 1 <= max_recs <= 100:
                valid_prefs["max_recommendations"] = max_recs
        
        # Validate email_notifications
        if "email_notifications" in preferences:
            email_notif = preferences["email_notifications"]
            if isinstance(email_notif, bool):
                valid_prefs["email_notifications"] = email_notif
        
        return valid_prefs