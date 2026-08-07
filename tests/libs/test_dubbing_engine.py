"""Unit tests for Gemini AI Dubbing Engine and Transcoder muxing builder."""

import tempfile
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from libs.gemini.dubbing_engine import GeminiDubbingEngine, LANGUAGE_METADATA
from libs.transcoder.builders.dubbing_job_builder import build_dubbing_mux_job_config


class TestDubbingEngine:
    """Test suite for GeminiDubbingEngine audio processing and translation."""

    @patch("libs.gemini.dubbing_engine.genai.Client")
    def test_init_engine(self, mock_genai_client):
        engine = GeminiDubbingEngine()
        assert engine is not None
        assert "hi-IN" in LANGUAGE_METADATA
        assert "es-ES" in LANGUAGE_METADATA
        assert "pt-BR" in LANGUAGE_METADATA
        assert "de-DE" in LANGUAGE_METADATA
        assert "en-US" in LANGUAGE_METADATA

    @patch("libs.gemini.dubbing_engine.genai.Client")
    def test_extract_dialogue_parsing(self, mock_genai_client):
        mock_client = MagicMock()
        mock_genai_client.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.text = """{
            "detected_language": "en-US",
            "summary": "Basketball interview clip",
            "segments": [
                {
                    "speaker": "Speaker 1",
                    "start_seconds": 1.2,
                    "end_seconds": 4.8,
                    "text": "Great game tonight team.",
                    "emotion": "excited"
                }
            ]
        }"""
        mock_client.models.generate_content.return_value = mock_resp

        engine = GeminiDubbingEngine()
        result = engine.extract_dialogue("gs://test-bucket/sample.mp4")

        assert result["detected_language"] == "en-US"
        assert len(result["segments"]) == 1
        assert result["segments"][0]["text"] == "Great game tonight team."

    @patch("libs.gemini.dubbing_engine.genai.Client")
    def test_translate_and_pace(self, mock_genai_client):
        mock_client = MagicMock()
        mock_genai_client.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.text = """{
            "target_language": "hi-IN",
            "translated_segments": [
                {
                    "speaker": "Speaker 1",
                    "start_seconds": 1.2,
                    "end_seconds": 4.8,
                    "original_text": "Great game tonight team.",
                    "translated_text": "आज रात बहुत बढ़िया खेल रहा टीम।",
                    "confidence": 0.96
                }
            ]
        }"""
        mock_client.models.generate_content.return_value = mock_resp

        engine = GeminiDubbingEngine()
        segments = [{"speaker": "Speaker 1", "start_seconds": 1.2, "end_seconds": 4.8, "text": "Great game tonight team."}]
        translated = engine.translate_and_pace(segments, target_language="hi-IN")

        assert len(translated) == 1
        assert translated[0]["translated_text"] == "आज रात बहुत बढ़िया खेल रहा टीम।"
        assert translated[0]["confidence"] == 0.96

    @patch("libs.gemini.dubbing_engine.genai.Client")
    def test_synthesize_audio_track_creates_valid_wav(self, mock_genai_client):
        engine = GeminiDubbingEngine()

        with tempfile.TemporaryDirectory() as tmpdir:
            out_wav = Path(tmpdir) / "output_dub.wav"
            translated_segs = [
                {
                    "speaker": "Speaker 1",
                    "start_seconds": 0.5,
                    "end_seconds": 2.5,
                    "translated_text": "Hola mundo",
                }
            ]

            engine.synthesize_audio_track(
                translated_segments=translated_segs,
                voice_preset="Kore",
                target_language="es-ES",
                total_duration_seconds=3.0,
                output_local_wav_path=out_wav,
            )

            assert out_wav.exists()
            assert out_wav.stat().st_size > 0

            # Verify WAV headers
            with wave.open(str(out_wav), "rb") as wf:
                assert wf.getnchannels() == 2
                assert wf.getsampwidth() == 2
                assert wf.getframerate() == 48000
                total_seconds = wf.getnframes() / 48000
                assert total_seconds >= 2.9


class TestDubbingJobBuilder:
    """Test suite for Transcoder API dubbing muxing job builder."""

    def test_build_dubbing_mux_job_config(self):
        job = build_dubbing_mux_job_config(
            video_input_gcs_uri="gs://bucket/source.mp4",
            dubbed_audio_gcs_uri="gs://bucket/dub_hi.wav",
            output_gcs_prefix="gs://bucket/output/",
            language_code="hi-IN",
            resolution_height=720,
        )

        assert job.input_uri == "gs://bucket/source.mp4"
        assert job.output_uri == "gs://bucket/output/"
        assert len(job.config.inputs) == 2
        assert len(job.config.elementary_streams) == 2
        assert len(job.config.mux_streams) == 1
        assert "dubbed_mux_hi_in" in job.config.mux_streams[0].key
        assert job.config.mux_streams[0].file_name == "video_dubbed_hi_in.mp4"
