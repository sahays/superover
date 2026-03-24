"""
Factory pattern for creating scene processors.
Selects implementation based on configuration.
"""

import logging
from pathlib import Path
from config import settings
from .base import SceneProcessor
from .sequential import SequentialSceneProcessor
from .parallel import ParallelSceneProcessor

logger = logging.getLogger(__name__)


def _init_speech_client():
    """Initialize Speech-to-Text client, returning None if unavailable."""
    try:
        from libs.speech import get_speech_client

        client = get_speech_client()
        logger.info("Speech-to-Text (Chirp 3) client initialized")
        return client
    except Exception as e:
        logger.warning(f"Speech-to-Text client not available (Chirp 3 disabled): {e}")
        return None


def get_scene_processor(db, storage, analyzer, temp_dir: Path) -> SceneProcessor:
    """
    Create and return appropriate scene processor based on configuration.

    Args:
        db: Database client
        storage: Storage client
        analyzer: Scene analyzer (Gemini)
        temp_dir: Temporary directory

    Returns:
        SceneProcessor instance (either Sequential or Parallel)
    """
    mode = settings.scene_processing_mode.lower()
    speech_client = _init_speech_client()

    if mode == "parallel":
        processor = ParallelSceneProcessor(
            db=db,
            storage=storage,
            analyzer=analyzer,
            temp_dir=temp_dir,
            max_workers=settings.max_gemini_workers,
            speech_client=speech_client,
        )
        logger.info("Scene processor initialized: PARALLEL mode")
    elif mode == "sequential":
        processor = SequentialSceneProcessor(
            db=db,
            storage=storage,
            analyzer=analyzer,
            temp_dir=temp_dir,
            speech_client=speech_client,
        )
        logger.info("Scene processor initialized: SEQUENTIAL mode")
    else:
        # Default to parallel if invalid mode specified
        logger.warning(
            f"Invalid scene_processing_mode '{mode}'. Defaulting to 'parallel'. Valid options: 'sequential', 'parallel'"
        )
        processor = ParallelSceneProcessor(
            db=db,
            storage=storage,
            analyzer=analyzer,
            temp_dir=temp_dir,
            max_workers=settings.max_gemini_workers,
            speech_client=speech_client,
        )

    # Log processor info
    info = processor.get_info()
    logger.info(f"Processor info: {info}")

    return processor
