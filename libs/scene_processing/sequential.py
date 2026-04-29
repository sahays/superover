"""
Sequential Scene Processor
Processes video chunks one at a time.
Chunks are in GCS — Gemini reads them directly via GCS URI (no local download).
"""

import logging
from typing import List, Dict, Any, Optional
from google.api_core import exceptions as google_exceptions
from libs.database import SceneJobStatus
from .base import SceneProcessor
from .scene_analysis_schema import render_prompt

logger = logging.getLogger(__name__)


class SequentialSceneProcessor(SceneProcessor):
    """Processes scene chunks sequentially (one at a time)."""

    def get_info(self) -> Dict[str, Any]:
        """Get processor information."""
        return {
            "mode": "sequential",
            "cpu_count": 1,
            "thread_count": 1,
            "description": "Sequential single-threaded processing",
        }

    def process_chunks(
        self,
        chunks: List[Dict[str, Any]],
        job_id: str,
        video_id: str,
        prompt_text: str,
        prompt_type: str = "scene_analysis",
        context_items: List[Dict[str, Any]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Process video chunks sequentially. Chunks are read directly from GCS by Gemini.

        Args:
            chunks: List of chunk metadata dictionaries (must have gcs_path)
            job_id: Scene job ID for progress tracking
            video_id: Video ID
            prompt_text: Analysis prompt text
            prompt_type: Type of analysis (scene_analysis, subtitling, etc.)
            context_items: Optional list of context items to include in analysis
            response_schema: Optional JSON schema for structured Gemini output

        Raises:
            Exception: If processing fails
        """
        logger.info(f"[SEQUENTIAL] Analyzing {len(chunks)} chunk(s) for job {job_id}")

        # Load context files once (not per chunk)
        context_text = self.load_context_text(context_items) if context_items else None
        if context_text:
            logger.info(f"[SEQUENTIAL] Loaded context text ({len(context_text)} chars) - will be reused for all chunks")

        # Determine if Chirp 3 pre-processing is needed (subtitle/transcription jobs)
        use_chirp = prompt_type in ("subtitling", "transcription") and self.speech_client is not None
        if use_chirp:
            logger.info(f"[SEQUENTIAL] Chirp 3 enabled for prompt_type={prompt_type}")

        # For Chirp, try to find an extracted audio file (Chirp works better with audio-only)
        chirp_audio_gcs = None
        if use_chirp:
            try:
                media_jobs = self.db.list_media_jobs_for_video(video_id)
                for mj in media_jobs:
                    if mj.get("status") == "completed" and mj.get("results", {}).get("audio_path"):
                        chirp_audio_gcs = mj["results"]["audio_path"]
                        logger.info(f"[SEQUENTIAL] Using extracted audio for Chirp 3: {chirp_audio_gcs}")
                        break
            except Exception as e:
                logger.warning(f"[SEQUENTIAL] Could not find extracted audio: {e}")

        for chunk in chunks:
            chunk_index = chunk["index"]
            chunk_gcs = chunk["gcs_path"]

            logger.info(f"Analyzing chunk {chunk_index + 1}/{len(chunks)} from {chunk_gcs}")

            # Update progress
            self.db.update_scene_job_status(
                job_id,
                SceneJobStatus.PROCESSING,
                results={
                    "step": "transcribing" if use_chirp else "analyzing",
                    "progress": {
                        "completed_chunks": chunk_index,
                        "total_chunks": len(chunks),
                    },
                },
            )

            try:
                # Chirp 3 pre-processing: transcribe audio before Gemini
                chunk_context = context_text or ""
                chirp_metadata = None
                if use_chirp:
                    chirp_input = chirp_audio_gcs or chunk_gcs
                    logger.info(f"Chirp 3 input for chunk {chunk_index}: {chirp_input}")
                    chirp_result = self.speech_client.transcribe_gcs(chirp_input)
                    chirp_text = self.speech_client.format_as_context(chirp_result)
                    if not chirp_text:
                        raise ValueError(
                            f"Chirp 3 returned empty transcription for chunk {chunk_index}. "
                            f"Ensure an extracted audio file is available (not raw video)."
                        )
                    chunk_context = chirp_text + ("\n\n" + chunk_context if chunk_context else "")
                    logger.info(
                        f"Chirp 3 transcription for chunk {chunk_index}: {chirp_result.get('word_count', 0)} words"
                    )
                    chirp_metadata = {
                        "utterance_count": len(chirp_result.get("utterances", [])),
                        "detected_language": chirp_result.get("detected_language", ""),
                        "timestamps": chirp_text,
                    }

                # Update progress to analyzing phase
                if use_chirp:
                    self.db.update_scene_job_status(
                        job_id,
                        SceneJobStatus.PROCESSING,
                        results={
                            "step": "analyzing",
                            "progress": {
                                "completed_chunks": chunk_index,
                                "total_chunks": len(chunks),
                            },
                        },
                    )

                # Substitute chunk-time placeholders in prompt_text. Safe no-op
                # for prompts without {chunk_start_sec}/{chunk_end_sec}.
                chunk_start = float(chunk.get("start_time", 0.0))
                chunk_end = float(chunk.get("end_time", chunk_start + chunk.get("duration", 0)))
                rendered_prompt = render_prompt(prompt_text, chunk_start, chunk_end)

                # Analyze with Gemini — pass GCS URI directly, no local file needed
                result = self.analyzer.analyze_chunk(
                    media_path=None,
                    chunk_index=chunk_index,
                    chunk_duration=chunk["duration"],
                    prompt_text=rendered_prompt,
                    prompt_type=prompt_type,
                    context_text=chunk_context or None,
                    gcs_path=chunk_gcs,
                    response_schema=response_schema,
                )

                # Attach Chirp metadata to result
                if chirp_metadata:
                    result["chirp_transcription"] = chirp_metadata

                # Tag result with prompt_type for filtering
                result["prompt_type"] = prompt_type

                # Save result to database
                result_id = self.db.save_result(
                    video_id=video_id,
                    result_type="scene_analysis",
                    result_data=result,
                    scene_job_id=job_id,
                )
                logger.info(f"Saved analysis result {result_id} for chunk {chunk_index}")

                # Update progress after successful scene analysis
                self.db.update_scene_job_status(
                    job_id,
                    SceneJobStatus.PROCESSING,
                    results={
                        "step": "analyzing",
                        "progress": {
                            "completed_chunks": chunk_index + 1,
                            "total_chunks": len(chunks),
                        },
                    },
                )

            except google_exceptions.DeadlineExceeded as e:
                error_msg = (
                    f"Gemini API timeout for chunk {chunk_index + 1}/{len(chunks)}. "
                    f"The video chunk may be too large or complex. "
                    f"Consider using shorter chunk durations (e.g., 15-30 seconds). "
                    f"Error: {e}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg) from e

            except google_exceptions.ServiceUnavailable as e:
                error_msg = (
                    f"Gemini API service unavailable for chunk {chunk_index + 1}/{len(chunks)}. "
                    f"This is usually a temporary issue. Please try again later. "
                    f"Error: {e}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg) from e

        logger.info(f"[SEQUENTIAL] Completed all {len(chunks)} chunks for job {job_id}")
