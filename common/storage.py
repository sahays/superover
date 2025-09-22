import os
from google.cloud import storage
from urllib.parse import urlparse
import tempfile
import logging
import shutil

class StorageManager:
    """
    A class to handle file operations for both local and GCS paths,
    including downloading GCS files to temporary local paths for processing.
    """
    def __init__(self):
        self._gcs_client = None
        self.temp_files = []

    @property
    def gcs_client(self):
        if self._gcs_client is None:
            self._gcs_client = storage.Client()
        return self._gcs_client

    def _parse_gcs_path(self, path: str) -> (str, str):
        """Parses a gs:// path into bucket and blob name."""
        parsed = urlparse(path)
        if parsed.scheme != 'gs':
            raise ValueError(f"Path '{path}' is not a valid GCS path.")
        return parsed.netloc, parsed.path.lstrip('/')

    def is_gcs_path(self, path: str) -> bool:
        """Checks if a path is a GCS path."""
        return path.startswith('gs://')

    def get_local_path(self, path: str) -> str:
        """
        Ensures a file is available on the local filesystem.
        If the path is a GCS path, it downloads the file to a temporary
        local file and returns the path to it.
        If the path is already local, it returns it directly.
        """
        if self.is_gcs_path(path):
            logging.info(f"Downloading GCS file: {path} to a temporary local path.")
            bucket_name, blob_name = self._parse_gcs_path(path)
            bucket = self.gcs_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)

            # Create a temporary file and keep its name
            _, temp_local_path = tempfile.mkstemp(suffix=os.path.basename(blob_name))
            
            # Download the blob to the temporary file
            blob.download_to_filename(temp_local_path)
            
            # Keep track of temp files to clean up later
            self.temp_files.append(temp_local_path)
            return temp_local_path
        else:
            # If the local file doesn't exist, raise an error.
            if not os.path.exists(path):
                raise FileNotFoundError(f"Local file not found: {path}")
            return path

    def upload_file(self, local_path: str, gcs_path: str):
        """Uploads a local file to a GCS path."""
        if not self.is_gcs_path(gcs_path):
            raise ValueError(f"Destination path '{gcs_path}' is not a valid GCS path.")
        
        logging.info(f"Uploading local file '{local_path}' to GCS path '{gcs_path}'.")
        bucket_name, blob_name = self._parse_gcs_path(gcs_path)
        bucket = self.gcs_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(local_path)

    def move_file(self, source_local_path: str, destination_path: str):
        """Moves a local file to a destination that can be either local or GCS."""
        if self.is_gcs_path(destination_path):
            self.upload_file(source_local_path, destination_path)
        else:
            # Ensure the local destination directory exists
            destination_dir = os.path.dirname(destination_path)
            os.makedirs(destination_dir, exist_ok=True)
            shutil.move(source_local_path, destination_path)

    def cleanup_temp_files(self):
        """Deletes all temporary files created during the session."""
        logging.info(f"Cleaning up {len(self.temp_files)} temporary files.")
        for f in self.temp_files:
            try:
                os.remove(f)
            except OSError as e:
                logging.error(f"Error removing temporary file {f}: {e}")
        self.temp_files = []

    def write_json(self, path: str, data: dict):
        """Writes a dictionary to a JSON file on either local disk or GCS."""
        import json
        content = json.dumps(data, indent=4).encode('utf-8') # Encode to bytes
        
        if self.is_gcs_path(path):
            bucket_name, blob_name = self._parse_gcs_path(path)
            bucket = self.gcs_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.upload_from_string(content, content_type='application/json')
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(content)
