"""Google Cloud Speech-to-Text v2 (Chirp 3) client.

Provides accurate utterance timestamps for audio files in GCS.
Used as a pre-processing step before Gemini — Chirp provides timing,
Gemini listens to the audio and generates the actual subtitle text.
"""

import logging
from typing import Dict, Any, List

from google.cloud.speech_v2 import SpeechClient as GoogleSpeechClient
from google.cloud.speech_v2.types import cloud_speech
from google.api_core import exceptions as google_exceptions
from config import settings

logger = logging.getLogger(__name__)

_speech_client = None


def _duration_to_seconds(duration) -> float:
    """Convert protobuf Duration to float seconds."""
    if duration is None:
        return 0.0
    return (
        duration.total_seconds()
        if hasattr(duration, "total_seconds")
        else float(duration.seconds) + float(duration.nanos) / 1e9
    )


def _format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm for SRT-style output."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


class SpeechTranscriber:
    """Wraps Google Cloud Speech-to-Text v2 for Chirp 3 timestamp extraction."""

    def __init__(self):
        # Chirp 3 requires a regional endpoint, not global
        self.location = settings.gcp_region
        api_endpoint = f"{self.location}-speech.googleapis.com"
        self.client = GoogleSpeechClient(
            client_options={"api_endpoint": api_endpoint},
        )
        self.project_id = settings.gcp_project_id
        self.model = settings.chirp_model
        self.recognizer = f"projects/{self.project_id}/locations/{self.location}/recognizers/_"

    def transcribe_gcs(
        self,
        gcs_uri: str,
        language: str = "auto",
    ) -> Dict[str, Any]:
        """Transcribe audio from a GCS URI using Chirp 3.

        Returns timestamped utterances for use as timing anchors.
        """
        language_codes = ["auto"] if language == "auto" else [language]

        config = cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=language_codes,
            model=self.model,
            features=cloud_speech.RecognitionFeatures(
                enable_automatic_punctuation=True,
                enable_word_time_offsets=True,
            ),
        )

        logger.info(
            f"Transcribing {gcs_uri} with Chirp 3 (language={language}, model={self.model}, timestamps=enabled)"
        )

        try:
            file_metadata = cloud_speech.BatchRecognizeFileMetadata(uri=gcs_uri)

            request = cloud_speech.BatchRecognizeRequest(
                recognizer=self.recognizer,
                config=config,
                files=[file_metadata],
                recognition_output_config=cloud_speech.RecognitionOutputConfig(
                    inline_response_config=cloud_speech.InlineOutputConfig(),
                ),
            )

            operation = self.client.batch_recognize(request=request)
            logger.info("Waiting for Chirp 3 batch transcription to complete...")
            response = operation.result(timeout=600)

            return self._parse_batch_response(response, gcs_uri)

        except google_exceptions.InvalidArgument as e:
            logger.error(f"Chirp 3 invalid argument: {e}")
            raise
        except Exception as e:
            logger.error(f"Chirp 3 transcription failed for {gcs_uri}: {e}")
            raise

    def _parse_batch_response(
        self,
        response: cloud_speech.BatchRecognizeResponse,
        gcs_uri: str,
    ) -> Dict[str, Any]:
        """Parse BatchRecognize response, extracting timestamps."""
        utterances: List[Dict[str, Any]] = []
        detected_language = ""

        # BatchRecognize returns results keyed by file URI
        file_results = response.results.get(gcs_uri)
        if not file_results:
            for key, value in response.results.items():
                logger.info(f"Result key mismatch, using: {key}")
                file_results = value
                break

        if file_results:
            has_error = hasattr(file_results, "error") and file_results.error and file_results.error.code != 0
            if has_error:
                logger.warning(f"Chirp 3 error: code={file_results.error.code}, msg={file_results.error.message}")

        if not file_results or not file_results.transcript or not file_results.transcript.results:
            logger.warning(f"No transcription results for {gcs_uri}")
            return {"utterances": [], "detected_language": ""}

        # Track running time for utterances
        running_start = 0.0

        for result in file_results.transcript.results:
            if not result.alternatives:
                continue

            best_alt = result.alternatives[0]

            lang = result.language_code or ""
            if lang and not detected_language:
                detected_language = lang

            # Get result-level end time
            result_end = _duration_to_seconds(result.result_end_offset)

            # Try word-level timestamps first
            if best_alt.words:
                for word_info in best_alt.words:
                    w_start = _duration_to_seconds(word_info.start_offset)
                    w_end = _duration_to_seconds(word_info.end_offset)
                    if w_start > 0 or w_end > 0:
                        utterances.append(
                            {
                                "start": w_start,
                                "end": w_end,
                                "text": word_info.word,
                                "type": "word",
                            }
                        )
            # Fall back to utterance-level timing
            if result_end > 0:
                utterances.append(
                    {
                        "start": running_start,
                        "end": result_end,
                        "text": best_alt.transcript.strip(),
                        "type": "utterance",
                    }
                )
                running_start = result_end

        # Deduplicate: if we have word-level, keep only words; otherwise utterances
        has_words = any(u["type"] == "word" for u in utterances)
        if has_words:
            utterances = [u for u in utterances if u["type"] == "word"]
        else:
            utterances = [u for u in utterances if u["type"] == "utterance"]

        logger.info(f"Chirp 3 complete: {len(utterances)} timestamped entries, language={detected_language}")

        return {
            "utterances": utterances,
            "detected_language": detected_language,
        }

    def format_as_context(self, result: Dict[str, Any]) -> str:
        """Format timestamps + raw STT hints as context for Gemini.

        Provides timing anchors with raw Chirp text as hints.
        Gemini should use timestamps for placement and listen to the audio
        for accurate transcription — the hints are approximate.
        """
        utterances = result.get("utterances", [])
        if not utterances:
            return ""

        lines = [
            "=== SPEECH TIMESTAMPS + HINTS (Chirp 3) ===",
            "Below are speech timing anchors with raw STT hints.",
            "Timestamps are accurate — use them for subtitle cue placement.",
            "Hints are approximate and may be inaccurate — listen to the audio",
            "for the correct transcription and translation.",
            "",
        ]

        if utterances[0].get("type") == "word":
            # Group words into ~5-second windows with combined hint text
            segments: List[Dict[str, Any]] = []
            current: Dict[str, Any] = {
                "start": utterances[0]["start"],
                "end": utterances[0]["end"],
                "words": [],
            }
            for u in utterances:
                if u["start"] - current["start"] > 5.0 and current["words"]:
                    segments.append(current)
                    current = {
                        "start": u["start"],
                        "end": u["end"],
                        "words": [],
                    }
                current["end"] = u["end"]
                current["words"].append(u.get("text", ""))
            if current["words"]:
                segments.append(current)

            for seg in segments:
                start_ts = _format_timestamp(seg["start"])
                end_ts = _format_timestamp(seg["end"])
                hint = " ".join(seg["words"]).strip()
                lines.append(f"[{start_ts} --> {end_ts}] (hint: {hint})")
        else:
            for u in utterances:
                start_ts = _format_timestamp(u["start"])
                end_ts = _format_timestamp(u["end"])
                hint = u.get("text", "").strip()
                if hint:
                    lines.append(f"[{start_ts} --> {end_ts}] (hint: {hint})")
                else:
                    lines.append(f"[{start_ts} --> {end_ts}]")

        total_duration = utterances[-1]["end"] if utterances else 0
        lines.append("")
        lines.append(f"Total: {len(lines) - 7} segments, duration: {_format_timestamp(total_duration)}")

        return "\n".join(lines)


def get_speech_client() -> SpeechTranscriber:
    """Get or create singleton SpeechTranscriber instance."""
    global _speech_client
    if _speech_client is None:
        _speech_client = SpeechTranscriber()
    return _speech_client
