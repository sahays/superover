"""Search and sync API routes for BigQuery AI.SEARCH integration."""

import base64
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
    SearchRecommendation,
    CuratedSearchResponse,
)
from google.cloud import firestore as firestore_module
from libs.database import get_db
from libs.bigquery import get_bq_client
from libs.gemini import get_search_curator, get_search_query_interpreter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Search"])


def _build_embedding_text(result_data: dict) -> str:
    """Build focused embedding text from result_data for BQ text_content.

    Includes classification fields (genre, type, mood, setting), summary,
    and actor names. Excludes dialogue, camera work, and visual style noise
    to produce a cleaner embedding signal.
    """
    parts: list[str] = []

    # --- Top-level classification fields ---
    for key in ("genre", "type", "content_type", "category", "sub_category"):
        val = result_data.get(key)
        if val and isinstance(val, str) and val.strip():
            label = key.replace("_", " ").title()
            parts.append(f"{label}: {val.strip()}")

    # --- Chunk summary ---
    summary = result_data.get("chunk_summary")
    if summary and isinstance(summary, str):
        parts.append(f"Summary: {summary.strip()}")

    # --- Scene-level classification + actors ---
    scenes = result_data.get("scenes")
    if isinstance(scenes, list) and scenes:
        first_scene = scenes[0] if isinstance(scenes[0], dict) else {}

        mood = first_scene.get("mood", {})
        if isinstance(mood, dict):
            tone = mood.get("tone", "")
            energy = mood.get("energy", "")
            if tone or energy:
                parts.append(f"Mood: {tone} {energy}".strip())

        setting = first_scene.get("setting", {})
        if isinstance(setting, dict):
            location = setting.get("location", "")
            if location:
                parts.append(f"Setting: {location}")

        # Collect actor names across all scenes
        seen: set[str] = set()
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            # Scene summary (not detailed_description to keep it focused)
            scene_summary = scene.get("summary")
            if scene_summary and isinstance(scene_summary, str):
                parts.append(scene_summary.strip())
            for person in scene.get("people", []):
                if isinstance(person, dict):
                    name = person.get("label", "")
                    if name and name not in seen and not name.startswith("Person"):
                        seen.add(name)
                        parts.append(f"Actor: {name}")

    # --- Notable observations ---
    observations = result_data.get("notable_observations")
    if isinstance(observations, list):
        for obs in observations:
            if isinstance(obs, str) and obs.strip():
                parts.append(obs.strip())

    # --- Fallback: if nothing extracted, dump raw text ---
    if not parts:
        return _extract_all_text(result_data)

    return " ".join(parts)


def _extract_all_text(obj: object, depth: int = 0) -> str:
    """Recursively extract all text values as fallback."""
    if depth > 5:
        return ""
    if isinstance(obj, str):
        return obj.strip()
    parts: list[str] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in ("token_usage", "gcs_path", "finish_reason"):
                continue
            text = _extract_all_text(val, depth + 1)
            if text:
                parts.append(text)
    elif isinstance(obj, list):
        for item in obj:
            text = _extract_all_text(item, depth + 1)
            if text:
                parts.append(text)
    return " ".join(parts)


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
            text = _build_embedding_text(data.get("result_data", {}))
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
                    text_content=text,
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
        video_cache: dict[str, dict] = {}  # video_id -> {filename, gcs_path}

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

                # Cache video lookups (filename + gcs_path)
                if video_id and video_id not in video_cache:
                    video = db.get_video(video_id)
                    video_cache[video_id] = {
                        "filename": video.get("filename", "") if video else "",
                        "gcs_path": video.get("gcs_path", "") if video else "",
                    }

                # Build focused embedding text
                result_data = data.get("result_data", {})
                text_content = _build_embedding_text(result_data)
                logger.info(f"Syncing result {result_id}: video={video_id}, text_length={len(text_content)}")

                # Serialize full analysis JSON for BQ storage
                result_data_json = json.dumps(result_data) if result_data else None
                video_info = video_cache.get(video_id, {})

                # DML INSERT — returns immediately after insert completes
                bq.sync_scene_result(
                    result_id=result_id,
                    video_id=video_id,
                    video_filename=video_info.get("filename"),
                    scene_job_id=data.get("scene_job_id"),
                    chunk_index=data.get("chunk_index"),
                    text_content=text_content,
                    timestamp_start=data.get("timestamp_start"),
                    timestamp_end=data.get("timestamp_end"),
                    result_data_json=result_data_json,
                    gcs_path=video_info.get("gcs_path"),
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


def _extract_metadata(result_data: dict) -> dict:
    """Extract structured metadata from a scene result's result_data."""
    meta: dict = {}

    meta["description"] = result_data.get("chunk_summary")
    meta["genre"] = result_data.get("genre")
    meta["content_type"] = result_data.get("type") or result_data.get("content_type")

    scenes = result_data.get("scenes")
    if isinstance(scenes, list) and scenes:
        first = scenes[0] if isinstance(scenes[0], dict) else {}

        mood = first.get("mood", {})
        if isinstance(mood, dict):
            parts = [mood.get("tone", ""), mood.get("energy", "")]
            meta["mood"] = " ".join(p for p in parts if p) or None

        setting = first.get("setting", {})
        if isinstance(setting, dict):
            meta["setting"] = setting.get("location")

        # Collect all unique actor names across all scenes
        actors: list[str] = []
        seen: set[str] = set()
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            for person in scene.get("people", []):
                if isinstance(person, dict):
                    name = person.get("label", "")
                    if name and name not in seen and not name.startswith("Person"):
                        seen.add(name)
                        actors.append(name)
        if actors:
            meta["actors"] = actors

    return {k: v for k, v in meta.items() if v}


def _parse_result_data_json(row: dict) -> dict:
    """Parse result_data_json from a BQ row, returning empty dict on failure."""
    raw = row.get("result_data_json")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


@router.post("/videos", response_model=CuratedSearchResponse)
async def search_videos(request: SearchRequest):
    """Cross-video semantic search with Gemini curation. Zero Firestore reads."""
    try:
        # Interpret query: translate multilingual/multimodal input to English
        interpreted_query = None
        search_query = request.query

        interpreter = get_search_query_interpreter()
        audio_bytes = None
        if request.audio:
            try:
                audio_bytes = base64.b64decode(request.audio)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid base64 audio data",
                )

        if audio_bytes:
            interpreted_query = interpreter.interpret_query(
                text=request.query if request.query.strip() else None,
                audio_bytes=audio_bytes,
                audio_mime=request.audio_mime or "audio/webm",
            )
            search_query = interpreted_query
        else:
            interpreted_query = interpreter.interpret_query(text=request.query)
            if interpreted_query != request.query.strip():
                search_query = interpreted_query
            else:
                interpreted_query = None  # Don't show if unchanged (fast path)

        bq = get_bq_client()
        raw_results = bq.search_videos(search_query, request.limit)

        # Group by video_id, keep best match per video
        video_groups: dict[str, list[dict]] = {}
        for row in raw_results:
            vid = row["video_id"]
            video_groups.setdefault(vid, []).append(row)

        # Build raw_results for response (metadata from BQ, no Firestore)
        raw_video_results = []
        for video_id, matches in video_groups.items():
            best = matches[0]
            result_data = _parse_result_data_json(best)
            meta = _extract_metadata(result_data) if result_data else {}
            raw_video_results.append(
                VideoSearchResult(
                    video_id=video_id,
                    video_filename=best.get("video_filename"),
                    top_match_text=best.get("text_content", "")[:500],
                    score=best["distance"],
                    chunk_count=len(matches),
                    timestamp_start=best.get("timestamp_start"),
                    timestamp_end=best.get("timestamp_end"),
                    description=meta.get("description"),
                    genre=meta.get("genre"),
                    content_type=meta.get("content_type"),
                    mood=meta.get("mood"),
                    setting=meta.get("setting"),
                    actors=meta.get("actors"),
                )
            )
        raw_video_results.sort(key=lambda r: r.score)

        # Gemini curation
        curator = get_search_curator()
        curated = curator.curate_search_results(search_query, raw_results)

        recommendations = [SearchRecommendation(**rec) for rec in curated.get("recommendations", [])]

        return CuratedSearchResponse(
            response_text=curated.get("response_text", ""),
            recommendations=recommendations,
            raw_results=raw_video_results,
            interpreted_query=interpreted_query,
        )

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
