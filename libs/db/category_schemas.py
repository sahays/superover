"""Category schema operations mixin for FirestoreDB."""

import logging
from typing import Optional, Dict, Any, List
from google.cloud import firestore

logger = logging.getLogger(__name__)


class CategorySchemasMixin:
    """Category schema CRUD operations."""

    def get_category_schema(self, category: str) -> Optional[Dict[str, Any]]:
        """Get the response schema for a prompt category."""
        doc = self.category_schemas.document(category).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def set_category_schema(self, category: str, response_schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Set or update the response schema for a prompt category."""
        schema_data = {
            "category": category,
            "response_schema": response_schema,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        self.category_schemas.document(category).set(schema_data)
        logger.info(f"Set category schema for '{category}': {'structured' if response_schema else 'free text'}")
        return self.get_category_schema(category)

    def delete_category_schema(self, category: str) -> None:
        """Delete the response schema for a prompt category."""
        self.category_schemas.document(category).delete()
        logger.info(f"Deleted category schema for '{category}'")

    def list_category_schemas(self) -> List[Dict[str, Any]]:
        """List all category schemas."""
        return [doc.to_dict() for doc in self.category_schemas.stream()]
