# Story 3: Trajectory Make/Miss Logic + Signal Fusion

**Status (2026-07-17): Implemented-with-deviations** — trajectory classification works from base-fps samples + geometry (no native-fps re-decode; `decode_window` exists but is unused for V1); validated on synthetic fixtures only, eval accuracy criteria unmeasured (clips blocked by CDN 403).

## Summary

Implement ball-through-rim trajectory analysis (`shots.py`) and the fusion layer (`timeline.py`) that combines Signals A (score bug) and B (trajectory + `ball-in-basket`) into final scoring events — makes AND misses — with fused confidence and evidence.

## Tasks

- [x] `libs/basketball/shots.py`: maintain ball trajectory buffer near the rim; trigger native-fps re-decode ±2 s when the ball enters the rim neighborhood; classify make (ball center passes from above-rim through inner-rim to below within N frames) vs miss (approach + departure without pass-through). *(Deviation: classifies from base-fps samples with occlusion-gap bridging; native-fps re-decode not needed for the synthetic fixtures — revisit against real clips.)*
- [x] Camera-cut detection (histogram delta) → reset trajectory buffers; ignore windows spanning cuts (replay double-count guard). *(Shared detector: `libs/basketball/cuts.py`, also used by teams.)*
- [x] `libs/basketball/timeline.py` fusion rules: make = (trajectory-through-rim OR ball-in-basket) confirmed by score delta within ~2 s; timestamp from rim-crossing (fall back to lag-adjusted OCR delta); shot with no delta = miss; delta with no shot = OCR-only event at reduced confidence.
- [x] Confidence model: per-attribute confidence from contributing evidence; evidence list names each signal (`scorebug`, `trajectory`, `ball_in_basket`).
- [x] Emit misses as first-class events `{type: shot, outcome: missed}` — the review showed misses narrated as makes.

## Acceptance Criteria

- Eval: made-shot precision AND recall ≥ 90% on the eval set (fusion of A+B); every make in ground truth has an event with correct points.
- Misses that reach the rim are detected (recall ≥ 70% for V1) and never labeled as makes when no score delta follows.
- Every emitted event carries ≥ 1 evidence entry and calibrated-ish confidence (OCR-only < single-signal < multi-signal).

## Edge Cases

- Free throws: ball enters rim slowly from above with players static — trajectory geometry must not require fast approach.
- Rolled-out rim shots (ball dips below rim plane at the front then out) — must not count as make without pass-through.
- Replay of a make inside the clip: trajectory fires again but no second score delta → suppressed by fusion + cut detection.
- Score delta while bug was hidden (event happened off-camera or during wipe) → OCR-only event with wide time bounds.

## Functional Tests

- Unit: synthetic trajectories (clean make, front-rim roll-out, airball, slow FT drop) classified correctly.
- Unit: fusion truth table — every combination of {trajectory, ball-in-basket, delta} maps to the specified outcome/confidence.
- Integration (eval marker): full pipeline on eval clips; regression assertions from Epic 1 story 2 pass for outcome-related flags (shot_0013, shot_0020, shot_0028, shot_0084, shot_0085).
