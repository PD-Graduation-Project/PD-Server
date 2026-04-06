from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from loguru import logger

from config import Config


class S3Storage:
    """MinIO/S3 storage backend."""

    def __init__(self):
        self.endpoint = Config.MINIO_ENDPOINT
        self.bucket = Config.MINIO_BUCKET
        self.secure = Config.MINIO_SECURE

        boto_config = BotoConfig(
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3},
        )

        self.client = boto3.client(
            "s3",
            endpoint_url=f"{'https' if self.secure else 'http'}://{self.endpoint}",
            aws_access_key_id=Config.MINIO_ROOT_USER,
            aws_secret_access_key=Config.MINIO_ROOT_PASSWORD,
            config=boto_config,
        )

    def upload_file(self, file_path: str, s3_key: str) -> bool:
        """Upload local file to S3."""
        try:
            self.client.upload_file(file_path, self.bucket, s3_key)
            logger.debug(f"S3 uploaded: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"S3 upload failed for {s3_key}: {e}")
            return False

    def upload_fileobj(
        self, file_obj, s3_key: str, content_type: str = None, file_size: int = None
    ) -> tuple[bool, int]:
        """
        Upload file object to S3.

        Returns:
            tuple: (success, file_size)
        """
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type

            # Reset file pointer if seekable
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)

            # Get file size if not provided
            if file_size is None and hasattr(file_obj, "getbuffer"):
                file_size = file_obj.getbuffer().nbytes
            elif file_size is None and hasattr(file_obj, "tell"):
                pos = file_obj.tell()
                file_obj.seek(0, 2)
                file_size = file_obj.tell()
                file_obj.seek(pos)

            self.client.upload_fileobj(
                file_obj, self.bucket, s3_key, ExtraArgs=extra_args
            )
            logger.debug(f"S3 uploaded: {s3_key} ({file_size} bytes)")
            return True, file_size
        except ClientError as e:
            logger.error(f"S3 upload failed for {s3_key}: {e}")
            return False, 0

    def delete_file(self, s3_key: str) -> bool:
        """Delete file from S3."""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=s3_key)
            logger.debug(f"S3 deleted: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"S3 delete failed for {s3_key}: {e}")
            return False

    def get_presigned_url(self, s3_key: str, expires_in: int = 3600) -> str:
        """Generate pre-signed URL for downloading."""
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": s3_key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(f"Pre-signed URL generation failed for {s3_key}: {e}")
            return ""

    def file_exists(self, s3_key: str) -> bool:
        """Check if file exists in S3."""
        try:
            self.client.head_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError:
            return False

    def create_bucket_if_not_exists(self):
        """Create bucket if it doesn't exist."""
        try:
            self.client.create_bucket(Bucket=self.bucket)
            logger.info(f"Created bucket: {self.bucket}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "BucketAlreadyOwnedByYou":
                logger.debug(f"Bucket already exists: {self.bucket}")
            else:
                logger.error(f"Failed to create bucket: {e}")

    def download_file(self, s3_key: str, local_path: str) -> bool:
        """Download file from S3 to local path."""
        try:
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            self.client.download_file(self.bucket, s3_key, local_path)
            return True
        except ClientError as e:
            logger.error(f"S3 download failed for {s3_key}: {e}")
            return False


_storage: Optional[S3Storage] = None


def get_storage() -> S3Storage:
    """Get storage instance (lazy init)."""
    global _storage
    if _storage is None:
        _storage = S3Storage()
    return _storage


def is_s3_enabled() -> bool:
    """Check if S3 storage is enabled."""
    return Config.STORAGE_BACKEND == "s3"
