"""Branding settings operations mixin for FirestoreDB."""

import logging
from typing import Dict, Any
from google.cloud import firestore

logger = logging.getLogger(__name__)

BRANDING_DEFAULTS = {
    "app_title": "Superover",
    "subtitle": "Video Analysis Platform",
    "logo_url": "",
}


class BrandingMixin:
    """Branding settings CRUD operations."""

    def get_branding(self) -> Dict[str, Any]:
        """Get branding settings, returning defaults if no document exists."""
        doc = self.branding_settings.document("default").get()
        if doc.exists:
            return doc.to_dict()
        return {**BRANDING_DEFAULTS}

    def update_branding(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update branding settings (upsert via merge)."""
        updates["updated_at"] = firestore.SERVER_TIMESTAMP
        self.branding_settings.document("default").set(updates, merge=True)
        logger.info(f"Updated branding settings: {list(updates.keys())}")
        return self.get_branding()
