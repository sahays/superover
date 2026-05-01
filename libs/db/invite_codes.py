"""Invite code management operations mixin for FirestoreDB."""

import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

logger = logging.getLogger(__name__)


class InviteCodesMixin:
    """Invite code CRUD operations."""

    def get_invite_codes(self) -> List[Dict[str, Any]]:
        """Get all invite codes, ordered by creation date descending."""
        query = self.invite_codes_col.order_by("created_at", direction=firestore.Query.DESCENDING)
        codes = []
        for doc in query.stream():
            codes.append(doc.to_dict())
        return codes

    def get_invite_code(self, code_id: str) -> Optional[Dict[str, Any]]:
        """Get an invite code by document ID."""
        doc = self.invite_codes_col.document(code_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def get_invite_code_by_value(self, code_str: str) -> Optional[Dict[str, Any]]:
        """Look up an invite code by its code value."""
        docs = self.invite_codes_col.where(filter=FieldFilter("code", "==", code_str)).stream()
        for doc in docs:
            return doc.to_dict()
        return None

    def create_invite_code(
        self,
        code: str,
        label: str = "",
        is_admin: bool = False,
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Create a new invite code."""
        code_id = str(uuid.uuid4())
        code_data: Dict[str, Any] = {
            "id": code_id,
            "code": code,
            "label": label,
            "is_active": True,
            "is_admin": is_admin,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        if expires_at is not None:
            code_data["expires_at"] = expires_at

        self.invite_codes_col.document(code_id).set(code_data)
        logger.info(f"Created invite code: {code_id} (label={label}, admin={is_admin})")
        return self.get_invite_code(code_id)  # type: ignore[return-value]

    def update_invite_code(self, code_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an invite code."""
        ref = self.invite_codes_col.document(code_id)
        if not ref.get().exists:
            return None
        updates["updated_at"] = firestore.SERVER_TIMESTAMP
        ref.update(updates)
        logger.info(f"Updated invite code: {code_id}")
        return self.get_invite_code(code_id)

    def delete_invite_code(self, code_id: str) -> None:
        """Delete an invite code."""
        self.invite_codes_col.document(code_id).delete()
        logger.info(f"Deleted invite code: {code_id}")
