# Story 1: Player Tracking & Team Assignment (Signal C, part 1)

**Status (2026-07-17): Implemented-with-deviations** — the SigLIP-embedding fallback is not implemented (the silhouette gate scales cluster confidence down instead); cluster→team naming uses a majority vote over score-delta-confirmed makes in the fuse stage (attacked-basket inference unneeded for V1); validated on synthetic fixtures only.

## Summary

Track players across frames with ByteTrack and assign each track to a team by jersey-color clustering, so events can name the correct team on offense/defense — fixing the review's team-swap errors at the perception level.

## Tasks

- [x] `libs/basketball/teams.py`: ByteTrack via `supervision` over player detections; reset tracks at camera cuts (reuse cut detector from Epic 2 story 3 — shared `libs/basketball/cuts.py`).
- [x] Referee filtering via the detector's `referee` class before clustering.
- [x] HSV torso-pixel clustering (k=2) per track aggregated over its frames; silhouette-score gate → SigLIP embedding + KMeans fallback when colors are too close. *(Deviation: below-gate silhouettes scale confidences down instead of a SigLIP fallback — deferred until real-clip evals show it is needed.)*
- [x] Map cluster → team name using score-bug team abbreviations (Epic 2 story 1) + which basket each team attacks (inferred from shot events per half). *(Deviation: majority vote of cluster(shooter) = scorebug team over confirmed makes, in `timeline._apply_team_and_jersey`; attacked-basket inference not needed.)*
- [x] Attach `team` + shooter-track ID to shot events in the fusion layer: shooter = the tracked player nearest the ball at release / in possession before the shot.

## Acceptance Criteria

- Team assignment accuracy ≥ 95% over tracked player-frames on eval clips (spot-checked via debug video).
- Every fused shot event carries the correct offensive team on the eval set (fixes flagged clips shot_0015, shot_0017, shot_0071, shot_0092, shot_0093, shot_0094).
- Cluster→team-name mapping is stable across a whole clip.

## Edge Cases

- White/light home jerseys vs light court and crowd; teams with similar accent colors (silhouette gate → fallback path).
- Track fragmentation from occlusion in the paint — team label must survive re-identification via cluster reassignment, not track ID.
- Fewer than 4 players of a team visible (tight camera shots) — clustering still needs to converge or defer to previous frames' model.

## Functional Tests

- Unit: HSV clustering on synthetic torso patches (two well-separated kits; two near-identical kits triggers fallback).
- Unit: cluster→team mapping given mocked score-bug abbreviations and shot directions.
- Integration (eval marker): team attribution correct for all ground-truth scoring events on eval clips.
