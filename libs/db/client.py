"""FirestoreDB client — composed from domain mixins."""

import logging
from typing import Optional
from google.cloud import firestore
from config import settings

from .videos import VideosMixin
from .scenes import ScenesMixin
from .media import MediaMixin
from .images import ImagesMixin
from .prompts import PromptsMixin
from .category_schemas import CategorySchemasMixin
from .branding import BrandingMixin

logger = logging.getLogger(__name__)


class FirestoreDB(
    VideosMixin,
    ScenesMixin,
    MediaMixin,
    ImagesMixin,
    PromptsMixin,
    CategorySchemasMixin,
    BrandingMixin,
):
    """Firestore database operations."""

    def __init__(self):
        """Initialize Firestore client."""
        self.client = firestore.Client(project=settings.gcp_project_id, database=settings.firestore_database)
        prefix = f"{settings.service_name}_"

        self.videos = self.client.collection(f"{prefix}videos")
        self.scene_manifests = self.client.collection(f"{prefix}scene_manifests")
        self.scene_jobs = self.client.collection(f"{prefix}scene_jobs")
        self.scene_results = self.client.collection(f"{prefix}scene_results")
        self.scene_prompts = self.client.collection(f"{prefix}scene_prompts")
        self.media_jobs = self.client.collection(f"{prefix}media_jobs")
        self.image_jobs = self.client.collection(f"{prefix}image_jobs")
        self.image_results = self.client.collection(f"{prefix}image_results")
        self.prompts = self.client.collection(f"{prefix}prompts")
        self.category_schemas = self.client.collection(f"{prefix}category_schemas")
        self.branding_settings = self.client.collection(f"{prefix}branding_settings")

    def seed_default_prompts(self):
        """Seed default prompts if they don't exist."""
        query = self.prompts.where("type", "==", "image_adaptation").limit(1)
        if not list(query.stream()):
            logger.info("Seeding default image adaptation prompt")
            self.create_prompt(
                name="Cinematic Vertical Adapt",
                type="image_adaptation",
                prompt_text=(
                    "Generate a cinematic 9:16 vertical version of this image. "
                    "Extend the background intelligently using outpainting. "
                    "Maintain the focal point and lighting style."
                ),
                supports_context=False,
            )
            self.create_prompt(
                name="Social Media Square",
                type="image_adaptation",
                prompt_text=(
                    "Generate a balanced 1:1 square version of this image suitable for Instagram. "
                    "Ensure the main subject is centered."
                ),
                supports_context=False,
            )


# Singleton instance
_db_instance: Optional[FirestoreDB] = None


def get_db() -> FirestoreDB:
    """Get or create Firestore DB instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = FirestoreDB()
    return _db_instance
