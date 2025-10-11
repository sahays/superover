"""Prompt management API routes."""
import logging
from typing import List
from fastapi import APIRouter, HTTPException, status
from api.models.schemas import (
    PromptResponse,
    CreatePromptRequest,
    UpdatePromptRequest,
)
from libs.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.get("", response_model=List[PromptResponse])
async def list_prompts():
    """List all available prompts."""
    try:
        db = get_db()
        prompts = db.list_prompts()

        # Add jobs_count to each prompt
        prompts_with_counts = []
        for prompt in prompts:
            jobs_count = db.count_jobs_using_prompt(prompt["prompt_id"])
            prompt["jobs_count"] = jobs_count
            prompts_with_counts.append(prompt)

        return [PromptResponse(**p) for p in prompts_with_counts]
    except Exception as e:
        logger.error(f"Failed to list prompts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list prompts: {str(e)}",
        )


@router.post("", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(request: CreatePromptRequest):
    """Create a new prompt with auto-generated ID."""
    try:
        db = get_db()
        prompt_data = db.create_prompt(
            name=request.name,
            type=request.type,
            prompt_text=request.prompt_text,
        )
        prompt_data["jobs_count"] = 0  # New prompt has no jobs yet
        return PromptResponse(**prompt_data)
    except Exception as e:
        logger.error(f"Failed to create prompt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create prompt: {str(e)}",
        )


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(prompt_id: str):
    """Get a specific prompt by its ID."""
    try:
        db = get_db()
        prompt = db.get_prompt(prompt_id)
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt not found: {prompt_id}",
            )

        # Add jobs count
        prompt["jobs_count"] = db.count_jobs_using_prompt(prompt_id)
        return PromptResponse(**prompt)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get prompt {prompt_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get prompt: {str(e)}",
        )


@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(prompt_id: str, request: UpdatePromptRequest):
    """Update a prompt's name, type, and/or text."""
    try:
        db = get_db()

        # Validate at least one field is provided
        if request.name is None and request.type is None and request.prompt_text is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field (name, type, or prompt_text) must be provided"
            )

        updated_prompt = db.update_prompt(
            prompt_id=prompt_id,
            name=request.name,
            type=request.type,
            prompt_text=request.prompt_text,
        )

        if not updated_prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt not found: {prompt_id}",
            )

        # Add jobs count
        updated_prompt["jobs_count"] = db.count_jobs_using_prompt(prompt_id)
        return PromptResponse(**updated_prompt)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update prompt {prompt_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update prompt: {str(e)}",
        )


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(prompt_id: str):
    """Delete a prompt (only if no jobs are using it)."""
    try:
        db = get_db()

        # Check if prompt exists
        prompt = db.get_prompt(prompt_id)
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt not found: {prompt_id}",
            )

        # Check if any jobs are using this prompt
        jobs_count = db.count_jobs_using_prompt(prompt_id)
        if jobs_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete prompt: {jobs_count} job(s) are using it"
            )

        # Delete the prompt
        db.delete_prompt(prompt_id)
        logger.info(f"Deleted prompt: {prompt_id}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete prompt {prompt_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete prompt: {str(e)}",
        )
