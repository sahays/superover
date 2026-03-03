"""Prompt management operations mixin for FirestoreDB."""

import logging
import uuid
from typing import Optional, Dict, Any, List
from google.cloud import firestore

logger = logging.getLogger(__name__)


class PromptsMixin:
    """Prompt CRUD operations."""

    def create_prompt(
        self,
        name: str,
        type: str,
        prompt_text: str,
        supports_context: bool = False,
        context_description: Optional[str] = None,
        required_context_types: Optional[List[str]] = None,
        max_context_items: int = 5,
    ) -> Dict[str, Any]:
        """Create a new prompt document with auto-generated ID."""
        prompt_id = str(uuid.uuid4())
        prompt_data = {
            "prompt_id": prompt_id,
            "name": name,
            "type": type,
            "prompt_text": prompt_text,
            "supports_context": supports_context,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        if supports_context:
            prompt_data["context_description"] = context_description or "Upload additional context files"
            prompt_data["required_context_types"] = required_context_types or []
            prompt_data["max_context_items"] = max_context_items

        self.prompts.document(prompt_id).set(prompt_data)
        logger.info(f"Created prompt: {prompt_id} ({name}) of type {type}, supports_context={supports_context}")
        return self.get_prompt(prompt_id)

    def get_prompt(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get a prompt document by its ID."""
        doc = self.prompts.document(prompt_id).get()
        if doc.exists:
            data = doc.to_dict()
            if "type" not in data:
                data["type"] = "custom"
            if "name" not in data and "prompt_name" in data:
                data["name"] = data["prompt_name"]
            if "name" not in data:
                data["name"] = f"Prompt {data.get('prompt_id', 'unknown')[:8]}"
            if "supports_context" not in data:
                data["supports_context"] = False
            return data
        return None

    def list_prompts(self) -> List[Dict[str, Any]]:
        """List all prompt documents ordered by creation date."""
        query = self.prompts.order_by("created_at", direction=firestore.Query.DESCENDING)
        prompts = []
        for doc in query.stream():
            data = doc.to_dict()
            if "type" not in data:
                data["type"] = "custom"
            if "name" not in data and "prompt_name" in data:
                data["name"] = data["prompt_name"]
            if "name" not in data:
                data["name"] = f"Prompt {data.get('prompt_id', 'unknown')[:8]}"
            if "supports_context" not in data:
                data["supports_context"] = False
            prompts.append(data)
        return prompts

    def update_prompt(
        self,
        prompt_id: str,
        name: Optional[str] = None,
        type: Optional[str] = None,
        prompt_text: Optional[str] = None,
        supports_context: Optional[bool] = None,
        context_description: Optional[str] = None,
        required_context_types: Optional[List[str]] = None,
        max_context_items: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a prompt document."""
        prompt_ref = self.prompts.document(prompt_id)
        if not prompt_ref.get().exists:
            return None

        update_data = {"updated_at": firestore.SERVER_TIMESTAMP}

        if name is not None:
            update_data["name"] = name
        if type is not None:
            update_data["type"] = type
        if prompt_text is not None:
            update_data["prompt_text"] = prompt_text
        if supports_context is not None:
            update_data["supports_context"] = supports_context
        if context_description is not None:
            update_data["context_description"] = context_description
        if required_context_types is not None:
            update_data["required_context_types"] = required_context_types
        if max_context_items is not None:
            update_data["max_context_items"] = max_context_items

        if len(update_data) == 1:  # Only updated_at
            raise ValueError("At least one field must be provided for update")

        prompt_ref.update(update_data)
        logger.info(f"Updated prompt: {prompt_id}")
        return self.get_prompt(prompt_id)

    def delete_prompt(self, prompt_id: str) -> None:
        """Delete a prompt document."""
        self.prompts.document(prompt_id).delete()
        logger.info(f"Deleted prompt: {prompt_id}")

    def count_jobs_using_prompt(self, prompt_id: str) -> int:
        """Count how many scene jobs are using this prompt."""
        query = self.scene_jobs.where("prompt_id", "==", prompt_id)
        return len(list(query.stream()))
