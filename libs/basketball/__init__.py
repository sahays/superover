"""Basketball broadcast-video analysis (local CLI, no Firestore/GCS deps).

Deterministic CPU perception owns the timestamps and facts; Gemini owns only
the prose (see docs/plans/basketball-video-analysis/plan.md). This package is
importable without the repo root ``config.py`` (no GCP env required) — use
``libs.basketball.config`` instead.
"""
