import tempfile
import wave
from pathlib import Path
from unittest.mock import patch
import pytest

from libs.gemini.dubbing_engine import (
    GeminiDubbingEngine,
    AudioExtractionService,
    AudioSynthesisService,
    LANGUAGE_METADATA,
)
from libs.transcoder.builders.dubbing_job_builder import build_dubbing_mux_job_config


class TestDubbingEngine:
    """Test suite for Gemini Live Speech-to-Speech Dubbing Engine."""

    @patch("libs.gemini.dubbing_engine.genai.Client")
    def test_init_engine(self, mock_genai_client):
        engine = GeminiDubbingEngine()
        assert engine is not None
        assert "hi-IN" in LANGUAGE_METADATA
        assert "es-ES" in LANGUAGE_METADATA
        assert "pt-BR" in LANGUAGE_METADATA
        assert "de-DE" in LANGUAGE_METADATA
        assert "en-US" in LANGUAGE_METADATA
        assert len(engine.get_supported_languages()) == 5

    def test_audio_extraction_baseline(self):
        service = AudioExtractionService()
        with tempfile.TemporaryDirectory() as tmpdir:
            out_pcm = str(Path(tmpdir) / "test.pcm")
            res = service.extract_pcm_16k("non_existent.mp4", out_pcm)
            assert Path(res).exists()
            assert Path(res).stat().st_size > 0

    def test_audio_synthesis_pcm_to_wav(self):
        service = AudioSynthesisService()
        with tempfile.TemporaryDirectory() as tmpdir:
            out_wav = str(Path(tmpdir) / "dubbed.wav")
            # 1 second of 24kHz 16-bit mono PCM = 48000 bytes
            dummy_pcm = b"\x00\x00" * 24000
            res = service.pcm_24k_to_wav(dummy_pcm, out_wav, sample_rate=24000)
            assert Path(res).exists()

            with wave.open(res, "rb") as wf:
                assert wf.getnchannels() == 1
                assert wf.getframerate() == 24000
                assert wf.getnframes() == 24000

    @pytest.mark.asyncio
    @patch("libs.gemini.dubbing_engine.genai.Client")
    async def test_translate_speech_live_fallback(self, mock_genai_client):
        engine = GeminiDubbingEngine()
        with tempfile.TemporaryDirectory() as tmpdir:
            dummy_pcm = str(Path(tmpdir) / "source.pcm")
            with open(dummy_pcm, "wb") as f:
                f.write(b"\x00\x00" * 16000)  # 1 second of 16kHz PCM

            result = await engine._synthesize_fallback(dummy_pcm, "hi-IN", "Kore")
            assert "audio_bytes" in result
            assert len(result["audio_bytes"]) > 0
            assert result["target_language"]["code"] == "hi-IN"
            assert "input_transcription" in result
            assert "output_transcription" in result

    @pytest.mark.asyncio
    @patch("libs.gemini.dubbing_engine.genai.Client")
    async def test_process_multilingual_dubbing(self, mock_genai_client):
        engine = GeminiDubbingEngine()
        with tempfile.TemporaryDirectory() as tmpdir:
            dummy_video = str(Path(tmpdir) / "test_video.mp4")
            with open(dummy_video, "wb") as f:
                f.write(b"fake video container")

            result = await engine.process_multilingual_dubbing(
                video_path=dummy_video,
                target_languages=["hi-IN", "es-ES"],
                voice_preset="Kore",
                output_dir=tmpdir,
            )

            assert "tracks" in result
            assert "hi-IN" in result["tracks"]
            assert "es-ES" in result["tracks"]
            assert Path(result["tracks"]["hi-IN"]["audio_wav_path"]).exists()
            assert Path(result["tracks"]["es-ES"]["audio_wav_path"]).exists()


class TestDubbingJobBuilder:
    """Test suite for Video Transcoder API multiplexing configuration."""

    def test_build_dubbing_mux_job_config_hindi(self):
        job = build_dubbing_mux_job_config(
            video_input_gcs_uri="gs://uploads/clip.mp4",
            dubbed_audio_gcs_uri="gs://processed/hindi_dub.aac",
            output_gcs_prefix="gs://results/dubbed_hi/",
            language_code="hi-IN",
        )
        assert job is not None
        assert len(job.config.elementary_streams) >= 2
        assert len(job.config.mux_streams) >= 1

    def test_build_dubbing_mux_job_config_spanish(self):
        job = build_dubbing_mux_job_config(
            video_input_gcs_uri="gs://uploads/clip.mp4",
            dubbed_audio_gcs_uri="gs://processed/spanish_dub.aac",
            output_gcs_prefix="gs://results/dubbed_es/",
            language_code="es-ES",
        )
        assert job is not None
        assert len(job.config.elementary_streams) >= 2
