"""
GCS Storage module for upload/download operations.
Works both locally and on Cloud Run.
"""

import datetime
import logging
from pathlib import Path
from typing import Optional

import google.auth
from google.auth.transport import requests as auth_requests
from google.cloud import storage
from config import settings

logger = logging.getLogger(__name__)


class GCSStorage:
    """Google Cloud Storage operations."""

    def __init__(self):
        """Initialize GCS client."""
        self.client = storage.Client(project=settings.gcp_project_id)
        self.uploads_bucket = self.client.bucket(settings.uploads_bucket)
        self.processed_bucket = self.client.bucket(settings.processed_bucket)
        self.results_bucket = self.client.bucket(settings.results_bucket)
        # For signed URLs on Cloud Run (Compute Engine credentials have no
        # private key — we use IAM signBlob via service_account_email + access_token).
        self.credentials, _ = google.auth.default()

    def _sign(self, blob, expiration, method, content_type=None):
        """Generate a v4 signed URL, works both locally and on Cloud Run."""
        self.credentials.refresh(auth_requests.Request())
        kwargs = {
            "version": "v4",
            "expiration": expiration,
            "method": method,
            "service_account_email": self.credentials.service_account_email,
            "access_token": self.credentials.token,
        }
        if content_type:
            kwargs["content_type"] = content_type
        return blob.generate_signed_url(**kwargs)

    def generate_signed_upload_url(
        self,
        filename: str,
        content_type: str,
        bucket_type: str = "uploads",
        expiration_minutes: int = 15,
    ) -> tuple[str, str]:
        """Generate a signed URL for direct browser uploads."""
        bucket = self._get_bucket(bucket_type)
        blob = bucket.blob(filename)
        url = self._sign(blob, datetime.timedelta(minutes=expiration_minutes), "PUT", content_type)
        gcs_path = f"gs://{bucket.name}/{filename}"
        logger.info(f"Generated signed upload URL for: {gcs_path}")
        return url, gcs_path

    def generate_signed_download_url(self, gcs_path: str, expiration_minutes: int = 60) -> str:
        """Generate a signed URL for downloading a file."""
        bucket_name, blob_name = self._parse_gcs_path(gcs_path)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        url = self._sign(blob, datetime.timedelta(minutes=expiration_minutes), "GET")
        logger.info(f"Generated signed download URL for: {gcs_path}")
        return url

    def upload_file(self, local_path: Path, gcs_path: str, content_type: Optional[str] = None) -> str:
        """
        Upload a file from local storage to GCS.

        Args:
            local_path: Path to local file
            gcs_path: Destination GCS path (gs://bucket/path/to/file)
            content_type: Optional MIME type

        Returns:
            GCS path of uploaded file
        """
        bucket_name, blob_name = self._parse_gcs_path(gcs_path)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        if content_type:
            blob.content_type = content_type

        blob.upload_from_filename(str(local_path))
        logger.info(f"Uploaded {local_path} to {gcs_path}")
        return gcs_path

    def upload_bytes(self, data: bytes, gcs_path: str, content_type: Optional[str] = None) -> str:
        """
        Upload binary data directly to GCS.

        Args:
            data: Binary data to upload
            gcs_path: Destination GCS path (gs://bucket/path/to/file)
            content_type: Optional MIME type

        Returns:
            GCS path of uploaded file
        """
        bucket_name, blob_name = self._parse_gcs_path(gcs_path)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        if content_type:
            blob.content_type = content_type

        blob.upload_from_string(data, content_type=content_type)
        logger.info(f"Uploaded {len(data)} bytes to {gcs_path}")
        return gcs_path

    def download_file(self, gcs_path: str, local_path: Path) -> Path:
        """
        Download a file from GCS to local storage.

        Args:
            gcs_path: Source GCS path (gs://bucket/path/to/file)
            local_path: Destination local path

        Returns:
            Path to downloaded file
        """
        bucket_name, blob_name = self._parse_gcs_path(gcs_path)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Ensure parent directory exists
        local_path.parent.mkdir(parents=True, exist_ok=True)

        blob.download_to_filename(str(local_path))
        logger.info(f"Downloaded {gcs_path} to {local_path}")
        return local_path

    def file_exists(self, gcs_path: str) -> bool:
        """
        Check if a file exists in GCS.

        Args:
            gcs_path: GCS path to check

        Returns:
            True if file exists
        """
        try:
            bucket_name, blob_name = self._parse_gcs_path(gcs_path)
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            return blob.exists()
        except Exception as e:
            logger.error(f"Error checking file existence: {e}")
            return False

    def delete_file(self, gcs_path: str) -> bool:
        """
        Delete a file from GCS.

        Args:
            gcs_path: GCS path to delete

        Returns:
            True if successful
        """
        try:
            bucket_name, blob_name = self._parse_gcs_path(gcs_path)
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.delete()
            logger.info(f"Deleted {gcs_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False

    def get_file_metadata(self, gcs_path: str) -> dict:
        """
        Get metadata for a file in GCS.

        Args:
            gcs_path: GCS path

        Returns:
            Dictionary with metadata (size, content_type, created, etc.)
        """
        bucket_name, blob_name = self._parse_gcs_path(gcs_path)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.reload()

        return {
            "size": blob.size,
            "content_type": blob.content_type,
            "created": blob.time_created,
            "updated": blob.updated,
            "md5_hash": blob.md5_hash,
        }

    def _get_bucket(self, bucket_type: str) -> storage.Bucket:
        """Get bucket by type."""
        bucket_map = {
            "uploads": self.uploads_bucket,
            "processed": self.processed_bucket,
            "results": self.results_bucket,
        }
        return bucket_map.get(bucket_type, self.uploads_bucket)

    @staticmethod
    def _parse_gcs_path(gcs_path: str) -> tuple[str, str]:
        """
        Parse GCS path into bucket and blob name.

        Args:
            gcs_path: Path like gs://bucket/path/to/file

        Returns:
            Tuple of (bucket_name, blob_name)
        """
        if not gcs_path.startswith("gs://"):
            raise ValueError(f"Invalid GCS path: {gcs_path}")

        path_parts = gcs_path[5:].split("/", 1)
        if len(path_parts) != 2:
            raise ValueError(f"Invalid GCS path format: {gcs_path}")

        return path_parts[0], path_parts[1]


# Singleton instance
_storage_instance: Optional[GCSStorage] = None


def get_storage() -> GCSStorage:
    """Get or create GCS storage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = GCSStorage()
    return _storage_instance
