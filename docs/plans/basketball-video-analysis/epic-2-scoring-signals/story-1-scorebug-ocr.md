# Story 1: Score-Bug OCR → Scoring Events (Signal A)

## Summary

Read the broadcast score overlay with RapidOCR and emit scoring events from score changes — exact timestamps, scoring team, and 1/2/3 points. Zero model training; this story alone produces the first real eval numbers.

## Tasks

- [ ] `libs/basketball/scorebug.py`: locate the static score bug (pixel-stability mask across sampled frames), identify per-field ROIs (home score, away score, team abbreviations, game clock).
- [ ] Per-field pipeline: crop → 3–4x upscale (INTER_CUBIC) → RapidOCR at 1–2 fps.
- [ ] Temporal smoothing: sliding-window majority vote per field; reject reads violating domain rules (scores only increase, clock decreases within a period).
- [ ] Emit `score_change` events: `{t, team, delta}`; adjust t backwards by configurable lag estimate (`basketball_scorebug_lag_sec`, default ~1.5 s) — Epic 2 story 3 replaces this with the rim-crossing timestamp when available.
- [ ] Map bug sides to team names via OCR'd abbreviations (e.g. KU/KSU).
- [ ] `--debug-video` overlay: draw ROIs + current reads for visual QA.

## Acceptance Criteria

- On eval clips where the bug is visible, every actual score change produces exactly one `score_change` event with correct team and delta.
- No false score-change events from OCR noise (majority vote must absorb single-frame misreads).
- Eval harness shows recall of made-shot events from Signal A alone ≥ 80% on clips with a visible bug.

## Edge Cases

- Bug hidden during replays/graphics wipes → carry last state forward, re-sync on reappearance; no phantom deltas on reappearance jumps (delta > 3 or negative → re-baseline, not event).
- OCR confusions on low-res digits (8↔3, 1↔7) — must be handled by voting + monotonicity.
- Halftime/period graphics changing the bug layout; clips that start mid-score-animation.

## Functional Tests

- Unit: smoothing rejects a single-frame `35→85→35` misread; accepts a persistent `35→38`.
- Unit: delta classification (+1/+2/+3) and re-baseline on impossible jumps.
- Integration (eval marker): known eval clip yields its expected `score_change` events within ±2 s.
