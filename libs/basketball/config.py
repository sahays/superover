"""Standalone settings for the basketball CLI.

Deliberately independent from the repo root ``config.py``: that module has
required GCP fields, and this CLI must run without any GCP environment. All
fields here have defaults; every one can be overridden via a ``BASKETBALL_``
environment variable (e.g. ``BASKETBALL_BASE_FPS=5``).
"""

from functools import lru_cache
from typing import Dict

from pydantic_settings import BaseSettings, SettingsConfigDict


class BasketballSettings(BaseSettings):
    """Configuration knobs for the basketball video-analysis pipeline."""

    model_config = SettingsConfigDict(env_prefix="BASKETBALL_", extra="ignore")

    # --- Decode / sampling ---
    base_fps: float = 8.0
    """Base sampling rate (fps) for the first decode pass."""

    window_pad_sec: float = 2.0
    """Padding (seconds) for native-fps re-decode windows around events."""

    # --- Caching ---
    workdir: str = ".basketball-work"
    """Root of the per-clip stage cache (``<workdir>/<clip_id>/<stage>/``)."""

    # --- Score-bug OCR (Epic 2) ---
    scorebug_lag_sec: float = 1.5
    """Typical delay between a made basket and the on-screen score update."""

    # --- Ball/rim/player detection (Epic 2, libs/basketball/detect.py) ---
    detect_model_path: str = ""
    """Path to the YOLO ONNX detection model. Empty -> the detect stage raises
    with instructions; see libs/basketball/models/README.md for how to train
    the basketball model or produce the COCO smoke-test fallback."""

    detect_input_size: int = 960
    """Detector input resolution (square). Ignored when the ONNX export has a
    static input shape — the model's own size wins then."""

    detect_conf: float = 0.25
    """Default confidence threshold applied to every detection class."""

    detect_classes: Dict[str, str] = {
        # Roboflow basketball-player-detection-3 (production model)
        "ball": "ball",
        "ball-in-basket": "ball_in_basket",
        "rim": "rim",
        "player": "player",
        "number": "number",
        "referee": "referee",
        # The dataset labels an acting player with the action class INSTEAD of
        # "player" (verified on v18: only 4% of action boxes overlap a plain
        # player box, median IoU 0.02). Left unmapped these become ids >= 6 and
        # teams/shots — which filter on the canonical player id 3 — would skip
        # the shooter and silently attribute the shot to the nearest bystander.
        # Map them all to "player" so tracking and shooter attribution see them.
        # (Trade-off: loses the layup/dunk flavor epic-4 story-1 wants; that
        # needs a separate action array, and is deferred/low-stakes for V1.)
        "player-in-possession": "player",
        "player-jump-shot": "player",
        "player-layup-dunk": "player",
        "player-shot-block": "player",
        # COCO smoke-test fallback (yolo11n)
        "person": "player",
        "sports ball": "ball",
    }
    """Model class name -> canonical role. Canonical roles downstream stages
    key on: ball, rim, ball_in_basket, player, number, referee. Model class
    names not in this map pass through unchanged. Env override is JSON, e.g.
    ``BASKETBALL_DETECT_CLASSES='{"person": "player"}'``."""

    detect_threads: int = 0
    """onnxruntime intra-op thread count; 0 = let onnxruntime decide."""

    # --- Shot trajectory analysis (Epic 2, libs/basketball/shots.py) ---
    shots_cut_threshold: float = 0.5
    """Camera-cut threshold for the shots stage: total-variation distance
    (in [0, 1]) between consecutive sampled frames' HSV histograms above this
    marks a cut. Shared detector: libs/basketball/cuts.py (teams has its own
    knob, ``teams_cut_threshold``)."""

    shots_rim_neighborhood: float = 3.0
    """Ball detections inside the rim box expanded by this factor (about its
    center) join a rim's trajectory episode."""

    shots_inner_rim_frac: float = 0.6
    """Inner-rim x-range as a fraction of rim-box width, centered. A make
    requires the below-plane sample inside this range (front-rim roll-outs
    that dip below the plane outside it never count)."""

    shots_miss_proximity: float = 1.5
    """Rim-box expansion factor for 'the ball reached the rim': episodes with
    no pass-through classify as a miss when the ball got this close (or fell
    past the rim plane inside the neighborhood); otherwise 'unknown'."""

    shots_gap_max_samples: int = 3
    """Max consecutive missing base-fps ball samples (occlusion by rim/net/
    players) tolerated inside one trajectory episode before it splits."""

    shots_pass_window_sec: float = 0.6
    """Max time between the above-plane sample and the below-plane sample of
    a make's crossing pair (converted to a sample count via the base fps)."""

    shots_min_rim_dets: int = 2
    """Minimum detections for a rim cluster to count as a persistent rim."""

    shots_replay_window_sec: float = 25.0
    """Same-kind shot candidates in *different* camera segments within this
    many seconds get ``possible_replay: true`` (fusion drops them unless a
    score delta confirms them independently)."""

    # --- Player tracking & team clustering (Epic 3, libs/basketball/teams.py) ---
    teams_min_track_dets: int = 4
    """Tracks with fewer detections than this get ``cluster: null`` — too
    little evidence to color-cluster (never confidently wrong)."""

    teams_min_silhouette: float = 0.15
    """Silhouette-score gate for the k=2 kit-color clustering. Below it the
    cluster assignment is kept but every track's ``cluster_confidence`` is
    scaled down proportionally (low-confidence clustering)."""

    teams_torso_top: float = 0.2
    """Torso crop: top edge as a fraction of the player-box height."""

    teams_torso_bottom: float = 0.6
    """Torso crop: bottom edge as a fraction of the player-box height."""

    teams_torso_inset_x: float = 0.2
    """Torso crop: horizontal inset from each box side, fraction of box width
    (0.2 keeps the central 60% — jersey, not arms/background)."""

    teams_max_samples: int = 5
    """Max well-spread per-track frames aggregated into the track's kit-color
    feature."""

    teams_cut_threshold: float = 0.5
    """Camera-cut threshold for the teams stage (same shared detector as
    ``shots_cut_threshold`` — libs/basketball/cuts.py); a cut resets the
    player tracker so track IDs never bridge it."""

    # --- Jersey numbers (Epic 3, libs/basketball/jersey.py) ---
    jersey_min_reads: int = 3
    """Minimum OCR reads of the winning number before a track's jersey is
    accepted; fewer -> ``jersey: null`` (never confidently wrong)."""

    jersey_min_crop_px: int = 12
    """Minimum number-crop height in source pixels; smaller crops are
    discarded by the legibility gate."""

    jersey_min_sharpness: float = 40.0
    """Minimum Laplacian variance of the grayscale number crop (pre-upscale);
    blurrier crops are discarded by the legibility gate."""

    jersey_vote_margin: int = 2
    """Minimum vote lead of the winning number over the runner-up (per
    track); a smaller margin -> ``jersey: null``."""

    # --- Signal fusion (Epic 2, libs/basketball/timeline.py ``fuse`` stage) ---
    fuse_confirm_window_sec: float = 2.0
    """A shot candidate is confirmed 'made' when a score-bug delta lands
    within this many seconds of the candidate's rim-crossing time (scorebug
    event times are already lag-adjusted)."""

    fuse_jersey_min_conf: float = 0.5
    """Minimum jersey-stage vote confidence before the shooter's jersey
    number is attached to an event; below it ``jersey`` stays null."""

    # --- Evaluation ---
    eval_tolerance_sec: float = 2.0
    """Tolerance window (± seconds) when matching predicted events to truth."""

    # --- Eval dataset ---
    clips_base_url: str = ""
    """Base URL for eval clips; overrides sources.local.yaml when set
    (env: ``BASKETBALL_CLIPS_BASE_URL``). Never committed to the repo."""

    # --- Gemini narration (Epic 4) ---
    narrate_enabled: bool = False
    """Run the Gemini narration stage. Off by default: it needs the repo root
    GCP config (env vars + ADC) and google-genai, which the offline pipeline
    does not. The CLI's ``--narrate`` flag flips this on for the run."""

    narrate_model: str = ""
    """Gemini model override for narration; empty means the repo default
    (root ``config.py`` ``gemini_default_model``)."""

    narrate_max_retries: int = 1
    """Fact-validation retries (after the first attempt) before falling back
    to templated per-event narration."""


@lru_cache
def get_settings() -> BasketballSettings:
    """Singleton accessor, mirroring the repo's ``get_settings()`` pattern."""
    return BasketballSettings()
