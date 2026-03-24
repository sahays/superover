"""Category schema operations mixin for FirestoreDB."""

import logging
from typing import Optional, Dict, Any, List
from google.cloud import firestore

logger = logging.getLogger(__name__)


def _schema_doc_id(category: str, schema_name: str) -> str:
    """Build composite document ID for a named schema."""
    return f"{category}__{schema_name}"


class CategorySchemasMixin:
    """Category schema CRUD operations."""

    def get_category_schema(self, category: str, schema_name: str = "default") -> Optional[Dict[str, Any]]:
        """Get the response schema for a prompt category and schema name.

        Falls back to legacy doc ID (just category) for backward compatibility.
        """
        doc_id = _schema_doc_id(category, schema_name)
        doc = self.category_schemas.document(doc_id).get()
        if doc.exists:
            return doc.to_dict()

        # Backward compat: try legacy doc ID (category only, no schema_name)
        if schema_name == "default":
            legacy_doc = self.category_schemas.document(category).get()
            if legacy_doc.exists:
                return legacy_doc.to_dict()

        return None

    def set_category_schema(
        self,
        category: str,
        response_schema: Optional[Dict[str, Any]],
        schema_name: str = "default",
    ) -> Dict[str, Any]:
        """Set or update the response schema for a category + schema name."""
        doc_id = _schema_doc_id(category, schema_name)
        schema_data = {
            "category": category,
            "schema_name": schema_name,
            "response_schema": response_schema,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        self.category_schemas.document(doc_id).set(schema_data)
        logger.info(
            f"Set category schema for '{category}/{schema_name}': {'structured' if response_schema else 'free text'}"
        )
        return self.get_category_schema(category, schema_name)

    def delete_category_schema(self, category: str, schema_name: str = "default") -> None:
        """Delete the response schema for a category + schema name."""
        doc_id = _schema_doc_id(category, schema_name)
        self.category_schemas.document(doc_id).delete()
        logger.info(f"Deleted category schema for '{category}/{schema_name}'")

    def list_category_schemas(self) -> List[Dict[str, Any]]:
        """List all category schemas."""
        schemas = []
        for doc in self.category_schemas.stream():
            data = doc.to_dict()
            # Normalize legacy docs that lack schema_name
            if "schema_name" not in data:
                data["schema_name"] = "default"
            schemas.append(data)
        return schemas

    def list_schemas_for_category(self, category: str) -> List[Dict[str, Any]]:
        """List all named schemas for a given category."""
        schemas = []
        for doc in self.category_schemas.where("category", "==", category).stream():
            data = doc.to_dict()
            if "schema_name" not in data:
                data["schema_name"] = "default"
            schemas.append(data)

        # Also check legacy doc (category as doc ID, no category field)
        if not schemas:
            legacy_doc = self.category_schemas.document(category).get()
            if legacy_doc.exists:
                data = legacy_doc.to_dict()
                if "schema_name" not in data:
                    data["schema_name"] = "default"
                schemas.append(data)

        return schemas
