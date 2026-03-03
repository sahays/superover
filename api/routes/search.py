"""Search and sync API routes for BigQuery AI.SEARCH integration."""

import json
import logging
from typing import List

from fastapi import APIRouter, HTTPException, status

from api.models.schemas.search import (
    SyncStatusItem,
    SyncRequest,
    SyncResponse,
    SearchRequest,
    VideoSearchResult,
    InVideoSearchResult,
)
from google.cloud import firestore as firestore_module
from libs.database import get_db
from libs.bigquery import get_bq_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Search"])


def _flatten_result_data(result_data: dict) -> str:
    """Flatten result_data dict into a searchable text string.

    Concatenates all text fields including timestamps, camera metadata,
    setting details, and audio cues — the rich metadata helps produce
    precise, discriminating embeddings for clip-level search.
    """
    parts = []

    def _extract_text(obj, depth=0):
        """Recursively extract text values from nested dicts/lists."""
        if depth > 5:
            return
        if isinstance(obj, str):
            stripped = obj.strip()
            if stripped:
                parts.append(stripped)
        elif isinstance(obj, dict):
            for key, val in obj.items():
                if key in ("token_usage", "gcs_path", "finish_reason"):
                    continue
                _extract_text(val, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _extract_text(item, depth + 1)

    _extract_text(result_data)
    return " ".join(parts) if parts else json.dumps(result_data)


# === Sync Endpoints ===


@router.get("/sync-status", response_model=List[SyncStatusItem])
async def get_sync_status():
    """List all scene results with their sync status.

    For items marked "pending" in Firestore, lazily checks BigQuery
    for embedding completion and updates Firestore accordingly.
    """
    try:
        db = get_db()

        # Get all scene results, filter to completed searchable jobs
        all_docs = list(db.scene_results.stream())

        SEARCHABLE_PROMPT_TYPES = {"scene_analysis", "custom"}
        job_cache: dict[str, dict | None] = {}
        docs = []
        for doc in all_docs:
            data = doc.to_dict()

            # Check prompt_type on result_data first (new results)
            prompt_type = data.get("result_data", {}).get("prompt_type")
            if prompt_type:
                if prompt_type in SEARCHABLE_PROMPT_TYPES:
                    docs.append(doc)
                continue

            # Fallback: look up the parent job (old results without prompt_type)
            job_id = data.get("scene_job_id")
            if not job_id:
                continue
            if job_id not in job_cache:
                job_cache[job_id] = db.get_scene_job(job_id)
            job = job_cache[job_id]
            if not job or job.get("status") != "completed":
                continue
            if job.get("prompt_type", "") not in SEARCHABLE_PROMPT_TYPES:
                continue
            docs.append(doc)

        # Collect pending result_ids to batch-check embedding status
        pending_ids = []
        for doc in docs:
            data = doc.to_dict()
            if data.get("bq_sync_status") == "pending":
                pending_ids.append(doc.id)

        # Batch check embedding statuses for pending items
        embedding_statuses: dict[str, str] = {}
        if pending_ids:
            try:
                bq = get_bq_client()
                embedding_statuses = bq.check_embedding_statuses(pending_ids)
                logger.info(f"Checked {len(pending_ids)} pending embeddings: {embedding_statuses}")

                # Update Firestore for any that changed from "pending"
                for rid, embed_status in embedding_statuses.items():
                    if embed_status in ("ready", "error"):
                        update = {"bq_sync_status": embed_status}
                        if embed_status == "error":
                            update["bq_sync_error"] = "Embedding generation failed"
                        db.scene_results.document(rid).update(update)
                        logger.info(f"Updated Firestore sync status for {rid}: {embed_status}")
            except Exception as bq_err:
                logger.warning(f"BigQuery unavailable for embedding check: {bq_err}")

        # Look up video filenames
        video_filenames: dict[str, str] = {}

        items = []
        for doc in docs:
            data = doc.to_dict()
            video_id = data.get("video_id", "")

            # Cache video filename lookups
            if video_id and video_id not in video_filenames:
                video = db.get_video(video_id)
                video_filenames[video_id] = video.get("filename", "") if video else ""

            # Build text preview from result_data
            text = _flatten_result_data(data.get("result_data", {}))
            preview = text[:200] + "..." if len(text) > 200 else text

            # Determine sync status:
            # - Firestore bq_sync_status field is source of truth
            # - Override with fresh embedding check for pending items
            fs_status = data.get("bq_sync_status") or "not_synced"
            if fs_status == "pending" and doc.id in embedding_statuses:
                fs_status = embedding_statuses[doc.id]

            items.append(
                SyncStatusItem(
                    result_id=doc.id,
                    video_id=video_id,
                    video_filename=video_filenames.get(video_id),
                    scene_job_id=data.get("scene_job_id"),
                    chunk_index=data.get("chunk_index"),
                    sync_status=fs_status,
                    sync_error=data.get("bq_sync_error"),
                    text_preview=preview,
                )
            )

        return items

    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync status: {str(e)}",
        )


@router.post("/sync", response_model=SyncResponse)
async def sync_results(request: SyncRequest):
    """Sync selected scene results to BigQuery for search indexing.

    DML INSERTs into BigQuery and marks results as "pending" in Firestore.
    Returns immediately — embeddings generate asynchronously.
    Check GET /sync-status to see when embeddings are ready.
    """
    logger.info(f"Sync request for {len(request.result_ids)} result(s)")
    try:
        db = get_db()
        bq = get_bq_client()

        synced_count = 0
        errors = []
        video_filenames: dict[str, str] = {}

        for result_id in request.result_ids:
            try:
                # Read the scene result document from Firestore
                doc = db.scene_results.document(result_id).get()
                if not doc.exists:
                    logger.warning(f"Result {result_id} not found in Firestore")
                    errors.append(f"Result {result_id} not found")
                    continue

                data = doc.to_dict()
                video_id = data.get("video_id", "")

                # Handle already-synced results
                current_status = data.get("bq_sync_status")
                if current_status in ("pending", "ready"):
                    if request.resync:
                        # Re-sync: delete old BQ row, re-insert with fresh text
                        logger.info(f"Re-syncing result {result_id} (was {current_status})")
                        try:
                            bq.delete_synced_result(result_id)
                        except Exception:
                            pass  # Row may not exist
                    else:
                        logger.info(f"Result {result_id} already {current_status}, skipping")
                        synced_count += 1
                        continue

                # Cache video filename lookups
                if video_id and video_id not in video_filenames:
                    video = db.get_video(video_id)
                    video_filenames[video_id] = video.get("filename", "") if video else ""

                # Flatten result_data into searchable text
                text_content = _flatten_result_data(data.get("result_data", {}))
                logger.info(f"Syncing result {result_id}: video={video_id}, text_length={len(text_content)}")

                # DML INSERT — returns immediately after insert completes
                bq.sync_scene_result(
                    result_id=result_id,
                    video_id=video_id,
                    video_filename=video_filenames.get(video_id),
                    scene_job_id=data.get("scene_job_id"),
                    chunk_index=data.get("chunk_index"),
                    text_content=text_content,
                    timestamp_start=data.get("timestamp_start"),
                    timestamp_end=data.get("timestamp_end"),
                )

                # Mark as "pending" in Firestore — embedding generates async
                db.scene_results.document(result_id).update({"bq_sync_status": "pending", "bq_sync_error": None})
                synced_count += 1
                logger.info(f"Result {result_id} inserted, marked pending")

            except Exception as e:
                logger.error(f"Failed to sync result {result_id}: {e}", exc_info=True)
                # Mark as error in Firestore
                try:
                    db.scene_results.document(result_id).update(
                        {
                            "bq_sync_status": "error",
                            "bq_sync_error": str(e),
                        }
                    )
                except Exception:
                    pass
                errors.append(f"Result {result_id}: {str(e)}")

        logger.info(f"Sync complete: {synced_count} inserted, {len(errors)} errors")
        return SyncResponse(synced_count=synced_count, errors=errors)

    except Exception as e:
        logger.error(f"Failed to sync results: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync results: {str(e)}",
        )


@router.delete("/sync/{result_id}")
async def delete_synced_result(result_id: str):
    """Remove a synced result from BigQuery and clear Firestore sync state."""
    try:
        db = get_db()
        bq = get_bq_client()

        bq.delete_synced_result(result_id)

        # Clear sync state in Firestore
        try:
            db.scene_results.document(result_id).update(
                {
                    "bq_sync_status": firestore_module.DELETE_FIELD,
                    "bq_sync_error": firestore_module.DELETE_FIELD,
                }
            )
        except Exception as fs_err:
            logger.warning(f"Failed to clear Firestore sync state: {fs_err}")

        return {"message": f"Result {result_id} removed from search index"}

    except Exception as e:
        logger.error(f"Failed to delete synced result {result_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete synced result: {str(e)}",
        )


# === Search Endpoints ===


@router.post("/videos", response_model=List[VideoSearchResult])
async def search_videos(request: SearchRequest):
    """Cross-video semantic search using AI.SEARCH."""
    try:
        bq = get_bq_client()
        raw_results = bq.search_videos(request.query, request.limit)

        # Group by video_id, keep best match per video
        video_groups: dict[str, list[dict]] = {}
        for row in raw_results:
            vid = row["video_id"]
            video_groups.setdefault(vid, []).append(row)

        results = []
        for video_id, matches in video_groups.items():
            best = matches[0]  # Already sorted by distance ASC
            results.append(
                VideoSearchResult(
                    video_id=video_id,
                    video_filename=best.get("video_filename"),
                    top_match_text=best["text_content"][:500],
                    score=best["distance"],
                    chunk_count=len(matches),
                    timestamp_start=best.get("timestamp_start"),
                    timestamp_end=best.get("timestamp_end"),
                )
            )

        # Sort by score (lower distance = better match)
        results.sort(key=lambda r: r.score)
        return results

    except Exception as e:
        logger.error(f"Failed to search videos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


@router.post("/videos/{video_id}", response_model=List[InVideoSearchResult])
async def search_within_video(video_id: str, request: SearchRequest):
    """In-video semantic search — find moments within a specific video."""
    try:
        bq = get_bq_client()
        raw_results = bq.search_within_video(video_id, request.query, request.limit)

        return [
            InVideoSearchResult(
                chunk_index=row.get("chunk_index"),
                text_content=row["text_content"],
                timestamp_start=row.get("timestamp_start"),
                timestamp_end=row.get("timestamp_end"),
                score=row["distance"],
            )
            for row in raw_results
        ]

    except Exception as e:
        logger.error(f"Failed to search within video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )
