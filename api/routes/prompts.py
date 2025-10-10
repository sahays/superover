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


@router.post("", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(request: CreatePromptRequest):
    """Create a new prompt."""
    try:
        db = get_db()
        prompt_data = db.create_prompt(
            prompt_id=request.prompt_id,
            prompt_name=request.prompt_name,
            prompt_type=request.prompt_type,
            prompt_text=request.prompt_text,
        )
        return PromptResponse(**prompt_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create prompt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create prompt: {str(e)}",
        )


@router.get("", response_model=List[PromptResponse])
async def list_prompts():
    """List all available prompts."""
    try:
        db = get_db()
        prompts = db.list_prompts()
        return [PromptResponse(**p) for p in prompts]
    except Exception as e:
        logger.error(f"Failed to list prompts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list prompts: {str(e)}",
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
    """Update the text of a prompt."""
    try:
        db = get_db()
        updated_prompt = db.update_prompt(
            prompt_id=prompt_id,
            prompt_text=request.prompt_text,
        )
        if not updated_prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt not found: {prompt_id}",
            )
        return PromptResponse(**updated_prompt)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update prompt {prompt_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update prompt: {str(e)}",
        )
