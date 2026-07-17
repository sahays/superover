# Story 1: Shot Type Classification

## Summary

Classify each scoring event as free throw / 2PT / 3PT (and dunk/layup flavor where evident), primarily from the score-bug delta, with court-position and detector-class signals as tie-breakers — fixing the review's 3PT-vs-2PT confusions.

## Tasks

- [ ] Primary rule in `timeline.py`: delta +1 → free throw, +3 → 3PT, +2 → 2PT (authoritative when score bug is visible).
- [ ] Free-throw scene corroboration: static players along the paint + shooter at the line (player-position heuristic from tracks).
- [ ] 2PT flavor from detector action classes on the shooter track (`player-layup-dunk` → layup/dunk label) — best-effort, low-stakes.
- [ ] For OCR-absent events (Signal B only): mark shot type `unknown` unless court homography is implemented; evaluate on eval data whether homography is needed for V1 (train court-keypoint model on `basketball-court-detection-2` only if 3PT ambiguity actually hurts eval numbers).
- [ ] Missed-shot type: without a delta there is no points signal — label `missed 2PT/3PT` only when shooter's court position is known (homography-dependent), else `missed shot`.

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
