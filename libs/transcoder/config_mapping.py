"""
Maps application config values to Transcoder API parameters.
Transcoder API uses bitrate (not CRF) and specific codec settings.
"""

from typing import Dict


# Resolution string → target height in pixels
RESOLUTION_MAP: Dict[str, int] = {
    "360p": 360,
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
    "1440p": 1440,
    "2160p": 2160,
}

# CRF → approximate bitrate in bps (Transcoder API uses bitrate, not CRF).
# These are rough equivalents for H.264 at 480p. Higher CRF = lower bitrate.
CRF_TO_BITRATE: Dict[int, int] = {
    18: 4_000_000,   # High quality
    20: 3_000_000,
    23: 2_000_000,   # Default / medium quality
    26: 1_200_000,
    28: 800_000,
    30: 600_000,
    33: 400_000,
    36: 250_000,     # Low quality
    40: 150_000,
    51: 100_000,     # Minimum
}

# Audio format → Transcoder API codec string
AUDIO_CODEC_MAP: Dict[str, str] = {
    "aac": "aac",
    "mp3": "mp3",
    "wav": "pcm_s16le",
}

# Audio bitrate string → bps
AUDIO_BITRATE_MAP: Dict[str, int] = {
    "96k": 96_000,
    "128k": 128_000,
    "192k": 192_000,
    "256k": 256_000,
    "320k": 320_000,
}


def get_target_height(resolution: str) -> int:
    """Get target height pixels for a resolution string."""
    return RESOLUTION_MAP.get(resolution, 480)


def crf_to_bitrate(crf: int, resolution: str = "480p") -> int:
    """Convert CRF to approximate bitrate, scaled by resolution."""
    # Find nearest CRF value
    sorted_crfs = sorted(CRF_TO_BITRATE.keys())
    nearest = min(sorted_crfs, key=lambda x: abs(x - crf))
    base_bitrate = CRF_TO_BITRATE[nearest]

    # Scale bitrate by resolution relative to 480p baseline
    target_height = get_target_height(resolution)
    scale = (target_height / 480) ** 1.5  # Superlinear scaling
    return int(base_bitrate * scale)


def get_audio_codec(audio_format: str) -> str:
    """Get Transcoder API audio codec for a format string."""
    return AUDIO_CODEC_MAP.get(audio_format, "aac")


def get_audio_bitrate_bps(bitrate_str: str) -> int:
    """Convert audio bitrate string to bps."""
    return AUDIO_BITRATE_MAP.get(bitrate_str, 128_000)


