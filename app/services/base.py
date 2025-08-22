"""
Base Service - Common service functionality and patterns.

This provides:
1. Common service initialization patterns
2. Error handling utilities
3. Logging and monitoring helpers
4. Transaction management
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
import logging

# We'll create these as we build the project
from app.core.exceptions import ServiceError

logger = logging.getLogger(__name__)


class BaseService:
    """
    Base service class providing common functionality.
    
    This establishes patterns for:
    - Database session management
    - Error handling
    - Logging
    - Transaction management
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize service with database session.
        
        Args:
            db: Async database session
        """
        self.db = db
        self.logger = logger
    
    async def _handle_service_error(self, error: Exception, operation: str) -> None:
        """
        Centralized error handling for services.
        
        Args:
            error: The exception that occurred
            operation: Description of the operation that failed
        """
        self.logger.error(f"Service error in {operation}: {str(error)}")
        
        # Roll back transaction if needed
        try:
            await self.db.rollback()
        except Exception as rollback_error:
            self.logger.error(f"Failed to rollback transaction: {rollback_error}")
        
        # Re-raise validation errors as-is, convert others to service errors
        from app.core.exceptions import ValidationError, NotFoundError
        if isinstance(error, (ValidationError, NotFoundError)):
            raise error
        else:
            raise ServiceError(f"Failed to {operation}: {str(error)}") from error
    
    def _log_operation(self, operation: str, **kwargs) -> None:
        """
        Log service operations for debugging and monitoring.
        
        Args:
            operation: Description of the operation
            **kwargs: Additional context to log
        """
        context = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        self.logger.info(f"Service operation: {operation} {context}")
    
    async def _execute_in_transaction(self, operation_func, *args, **kwargs):
        """
        Execute operation in a database transaction.
        
        Args:
            operation_func: Function to execute
            *args, **kwargs: Arguments for the function
            
        Returns:
            Result of the operation
        """
        try:
            result = await operation_func(*args, **kwargs)
            await self.db.commit()
            return result
        except Exception as error:
            await self.db.rollback()
            raise error