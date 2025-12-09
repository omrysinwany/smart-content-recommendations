"""
AWS S3 storage service for file management.

This provides:
1. S3 file upload/download operations
2. Presigned URL generation for direct client uploads
3. File metadata management
4. Multipart upload for large files
5. Error handling and retry logic
"""

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timedelta
from typing import Any, BinaryIO, Dict, List, Optional

import aiofiles
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.config import settings

logger = logging.getLogger(__name__)


class S3StorageService:
    """
    AWS S3 storage service for handling file operations.

    Provides async-friendly S3 operations with proper error handling
    and AWS best practices for production deployment.
    """

    def __init__(self):
        """Initialize S3 storage service."""
        self.s3_client = None
        self.bucket_name = settings.s3_bucket_name

    def _get_s3_client(self):
        """Get or create S3 client."""
        if not self.s3_client:
            self.s3_client = settings.get_s3_client()
        return self.s3_client

    async def upload_file(
        self,
        file_content: bytes,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Upload file to S3.

        Args:
            file_content: File content as bytes
            key: S3 object key (file path)
            content_type: MIME type of the file
            metadata: Additional metadata to store with file

        Returns:
            Dictionary with upload result information
        """
        if not self.bucket_name:
            raise ValueError("S3 bucket name not configured")

        s3_client = self._get_s3_client()
        if not s3_client:
            raise ConnectionError("S3 client not available")

        try:
            # Prepare upload parameters
            upload_params = {
                "Bucket": self.bucket_name,
                "Key": key,
                "Body": file_content,
            }

            if content_type:
                upload_params["ContentType"] = content_type

            if metadata:
                upload_params["Metadata"] = metadata

            # Add server-side encryption for production
            if settings.is_aws_environment:
                upload_params["ServerSideEncryption"] = "AES256"

            # Run S3 upload in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: s3_client.put_object(**upload_params)
            )

            logger.info(f"Successfully uploaded file to S3: {key}")

            return {
                "success": True,
                "key": key,
                "bucket": self.bucket_name,
                "etag": response.get("ETag", "").strip('"'),
                "version_id": response.get("VersionId"),
                "upload_timestamp": datetime.utcnow().isoformat(),
            }

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"S3 upload failed for {key}: {error_code} - {str(e)}")
            return {
                "success": False,
                "error": f"S3 upload failed: {error_code}",
                "key": key,
            }
        except Exception as e:
            logger.error(f"Unexpected error uploading to S3: {str(e)}")
            return {"success": False, "error": f"Upload failed: {str(e)}", "key": key}

    async def download_file(self, key: str) -> Optional[bytes]:
        """
        Download file from S3.

        Args:
            key: S3 object key

        Returns:
            File content as bytes, or None if not found
        """
        if not self.bucket_name:
            raise ValueError("S3 bucket name not configured")

        s3_client = self._get_s3_client()
        if not s3_client:
            raise ConnectionError("S3 client not available")

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: s3_client.get_object(Bucket=self.bucket_name, Key=key)
            )

            content = response["Body"].read()
            logger.info(f"Successfully downloaded file from S3: {key}")
            return content

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"File not found in S3: {key}")
                return None
            else:
                logger.error(f"S3 download failed for {key}: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error downloading from S3: {str(e)}")
            raise

    async def delete_file(self, key: str) -> bool:
        """
        Delete file from S3.

        Args:
            key: S3 object key

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.bucket_name:
            raise ValueError("S3 bucket name not configured")

        s3_client = self._get_s3_client()
        if not s3_client:
            raise ConnectionError("S3 client not available")

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, lambda: s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            )

            logger.info(f"Successfully deleted file from S3: {key}")
            return True

        except ClientError as e:
            logger.error(f"S3 delete failed for {key}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting from S3: {str(e)}")
            return False

    async def generate_presigned_url(
        self, key: str, operation: str = "get_object", expiration: int = 3600
    ) -> Optional[str]:
        """
        Generate presigned URL for S3 operations.

        Args:
            key: S3 object key
            operation: S3 operation ('get_object', 'put_object')
            expiration: URL expiration time in seconds

        Returns:
            Presigned URL string or None if failed
        """
        if not self.bucket_name:
            raise ValueError("S3 bucket name not configured")

        s3_client = self._get_s3_client()
        if not s3_client:
            raise ConnectionError("S3 client not available")

        try:
            loop = asyncio.get_event_loop()
            url = await loop.run_in_executor(
                None,
                lambda: s3_client.generate_presigned_url(
                    operation,
                    Params={"Bucket": self.bucket_name, "Key": key},
                    ExpiresIn=expiration,
                ),
            )

            logger.info(f"Generated presigned URL for {operation}: {key}")
            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {key}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {str(e)}")
            return None

    async def list_files(
        self, prefix: str = "", max_keys: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        List files in S3 bucket.

        Args:
            prefix: Key prefix to filter by
            max_keys: Maximum number of keys to return

        Returns:
            List of file information dictionaries
        """
        if not self.bucket_name:
            raise ValueError("S3 bucket name not configured")

        s3_client = self._get_s3_client()
        if not s3_client:
            raise ConnectionError("S3 client not available")

        try:
            params = {"Bucket": self.bucket_name, "MaxKeys": max_keys}

            if prefix:
                params["Prefix"] = prefix

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: s3_client.list_objects_v2(**params)
            )

            files = []
            for obj in response.get("Contents", []):
                files.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                        "etag": obj["ETag"].strip('"'),
                        "storage_class": obj.get("StorageClass", "STANDARD"),
                    }
                )

            logger.info(f"Listed {len(files)} files from S3 with prefix: {prefix}")
            return files

        except ClientError as e:
            logger.error(f"S3 list failed: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing S3 files: {str(e)}")
            return []

    async def get_file_info(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata from S3.

        Args:
            key: S3 object key

        Returns:
            File metadata dictionary or None if not found
        """
        if not self.bucket_name:
            raise ValueError("S3 bucket name not configured")

        s3_client = self._get_s3_client()
        if not s3_client:
            raise ConnectionError("S3 client not available")

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: s3_client.head_object(Bucket=self.bucket_name, Key=key)
            )

            return {
                "key": key,
                "size": response["ContentLength"],
                "last_modified": response["LastModified"].isoformat(),
                "etag": response["ETag"].strip('"'),
                "content_type": response.get("ContentType"),
                "metadata": response.get("Metadata", {}),
                "version_id": response.get("VersionId"),
                "storage_class": response.get("StorageClass", "STANDARD"),
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return None
            else:
                logger.error(f"S3 head_object failed for {key}: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error getting S3 file info: {str(e)}")
            raise


# Global storage service instance
storage_service = S3StorageService()


async def init_storage():
    """Initialize storage service and verify S3 connection."""
    try:
        if settings.s3_bucket_name:
            s3_client = storage_service._get_s3_client()
            if s3_client:
                # Test S3 connection by listing bucket (with limit)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, lambda: s3_client.head_bucket(Bucket=settings.s3_bucket_name)
                )
                logger.info(
                    f"S3 storage initialized successfully (bucket: {settings.s3_bucket_name})"
                )
            else:
                logger.warning("S3 client not available - file storage disabled")
        else:
            logger.info("S3 bucket not configured - file storage disabled")
    except Exception as e:
        logger.error(f"Failed to initialize S3 storage: {e}")
        # Don't raise - allow app to start without S3


# Helper functions for common use cases
async def upload_content_file(
    content_id: int, file_content: bytes, filename: str
) -> Dict[str, Any]:
    """Upload a content-related file to S3."""
    key = f"content/{content_id}/{filename}"
    return await storage_service.upload_file(file_content, key)


async def upload_user_avatar(
    user_id: int, image_content: bytes, image_type: str
) -> Dict[str, Any]:
    """Upload user avatar image to S3."""
    extension = image_type.split("/")[-1] if "/" in image_type else image_type
    key = f"avatars/{user_id}/avatar.{extension}"
    return await storage_service.upload_file(
        image_content, key, content_type=image_type, metadata={"user_id": str(user_id)}
    )


async def get_content_file_url(
    content_id: int, filename: str, expiration: int = 3600
) -> Optional[str]:
    """Get presigned URL for content file download."""
    key = f"content/{content_id}/{filename}"
    return await storage_service.generate_presigned_url(key, "get_object", expiration)
