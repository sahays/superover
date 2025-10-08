"""Task management API routes."""
import logging
from typing import List
from fastapi import APIRouter, HTTPException, status
from api.models.schemas import TaskResponse
from libs.database import get_db, TaskStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get task information by ID."""
    try:
        db = get_db()
        task = db.get_task(task_id)

        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}"
            )

        return TaskResponse(**task)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task: {str(e)}"
        )


@router.get("/video/{video_id}", response_model=List[TaskResponse])
async def list_tasks_for_video(
    video_id: str,
    status_filter: TaskStatus = None
):
    """List all tasks for a specific video."""
    try:
        db = get_db()
        tasks = db.list_tasks_for_video(video_id, status=status_filter)
        return [TaskResponse(**t) for t in tasks]

    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tasks: {str(e)}"
        )


@router.get("", response_model=List[TaskResponse])
async def list_pending_tasks(limit: int = 10):
    """List pending tasks (for worker polling)."""
    try:
        db = get_db()
        tasks = db.get_pending_tasks(limit=limit)
        return [TaskResponse(**t) for t in tasks]

    except Exception as e:
        logger.error(f"Failed to list pending tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list pending tasks: {str(e)}"
        )
