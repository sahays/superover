"""Avatar operations mixin for FirestoreDB."""

import logging
from typing import Any, Dict, List, Optional

from google.cloud import firestore  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)


class AvatarsMixin:
    """Avatar CRUD operations.

    Stored under `{service_name}_avatars`. Records are plain dicts so the
    frontend's persona editor can round-trip extra display-only fields if we
    add them later without a schema migration.
    """

    avatars: firestore.CollectionReference  # set in FirestoreDB.__init__

    def list_avatars(self) -> List[Dict[str, Any]]:
        query = self.avatars.order_by("created_at", direction=firestore.Query.DESCENDING)
        return [doc.to_dict() for doc in query.stream()]

    def get_avatar(self, avatar_id: str) -> Optional[Dict[str, Any]]:
        doc = self.avatars.document(avatar_id).get()
        return doc.to_dict() if doc.exists else None

    def create_avatar(self, avatar: Dict[str, Any]) -> Dict[str, Any]:
        avatar_id = avatar["id"]
        payload = {**avatar, "created_at": firestore.SERVER_TIMESTAMP}
        self.avatars.document(avatar_id).set(payload)
        logger.info(f"Created avatar: {avatar_id}")
        return self.get_avatar(avatar_id)  # type: ignore[return-value]

    def update_avatar(self, avatar_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ref = self.avatars.document(avatar_id)
        if not ref.get().exists:
            return None
        updates["updated_at"] = firestore.SERVER_TIMESTAMP
        ref.update(updates)
        logger.info(f"Updated avatar {avatar_id}: {list(updates.keys())}")
        return self.get_avatar(avatar_id)

    def delete_avatar(self, avatar_id: str) -> None:
        self.avatars.document(avatar_id).delete()
        logger.info(f"Deleted avatar: {avatar_id}")
