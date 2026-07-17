# Story 1: Shot Type Classification

**Status (2026-07-17): Implemented-with-deviations** — homography is deferred, so missed shots stay type "shot" with `points: null` plus a fusion_debug warning (2PT/3PT never guessed); the layup/dunk flavor needs the fine-tuned model's action classes (pending GPU); eval-set acceptance criteria unmeasured (clips blocked).

## Summary

Classify each scoring event as free throw / 2PT / 3PT (and dunk/layup flavor where evident), primarily from the score-bug delta, with court-position and detector-class signals as tie-breakers — fixing the review's 3PT-vs-2PT confusions.

## Tasks

- [x] Primary rule in `timeline.py`: delta +1 → free throw, +3 → 3PT, +2 → 2PT (authoritative when score bug is visible). *(`_delta_type` + and-one matching guard in `_match_deltas` — a +1 within 3 s of a +2/+3 always stays a separate FT event.)*
- [x] Free-throw scene corroboration: static players along the paint + shooter at the line (player-position heuristic from tracks). *(`timeline.ft_scene_corroborated`: ≥4 near-static tracks — center travel ≤0.6 player-heights within ±3 s — clustered within 8 rim-widths of one rim; boosts OCR-only +1 confidence by 0.12, capped at 0.55, evidence tag `ft_scene`.)*
- [ ] 2PT flavor from detector action classes on the shooter track (`player-layup-dunk` → layup/dunk label) — best-effort, low-stakes. *(Blocked: needs the fine-tuned basketball model's action classes — COCO smoke model has none.)*
- [x] For OCR-absent events (Signal B only): mark shot type `unknown` unless court homography is implemented; evaluate on eval data whether homography is needed for V1 (train court-keypoint model on `basketball-court-detection-2` only if 3PT ambiguity actually hurts eval numbers). *(Type stays plain "shot" with `points: null`; homography evaluation itself pending eval clips.)*
- [x] Missed-shot type: without a delta there is no points signal — label `missed 2PT/3PT` only when shooter's court position is known (homography-dependent), else `missed shot`. *(Always `missed shot` for V1 — homography deferred; each such event adds a fusion_debug warning.)*

## Acceptance Criteria

- Shot type correct for 100% of score-delta-confirmed events on the eval set (it is arithmetic).
- Reviewer-flagged type errors fixed (shot_0024: 2PT not 3PT; shot_0013: FT context correct).
- No event labeled 3PT/FT without either a delta or an explicit position signal.

## Edge Cases

- And-one sequences: +2 followed by +1 within seconds — two events (FG + FT), not one +3 (guard via inter-delta gap and free-throw scene detection).
- Consecutive free throws (+1, +1) — separate events with correct timestamps.
- Missed 3PT (shot_0099's flagged case) — only classifiable with homography; otherwise `missed shot` with position unknown, never a guessed type.

## Functional Tests

- Unit: delta→type mapping incl. and-one splitting and consecutive FT sequences.
- Unit: free-throw scene heuristic on mocked track layouts.
- Integration (eval marker): type accuracy on all ground-truth events; and-one clip fixture handled as two events.
