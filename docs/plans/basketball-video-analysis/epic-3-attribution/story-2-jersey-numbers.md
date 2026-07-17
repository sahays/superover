# Story 2: Jersey Number Recognition (Signal C, part 2)

**Status (2026-07-17): Implemented-with-deviations** — RapidOCR recognition-only retained (the small CNN was not needed on fixtures; revisit on real footage); the `--roster` CLI flag is not wired (the pure `apply_roster` helper exists); eval accuracy criteria unmeasured (clips blocked).

## Summary

Identify the scorer's jersey number: crop `number` detections on the shooter's track, classify digits with a small CNN, and aggregate by tracklet-level voting — the published-accuracy approach (~90% ceiling on broadcast footage) that per-frame VLM reading cannot match.

## Tasks

- [x] `libs/basketball/jersey.py`: collect `number`-class crops per player track (detector from Epic 2 story 2).
- [x] Legibility gate: discard blurred/tiny crops (size + Laplacian-variance threshold) before classification.
- [x] Digit recognition: start with RapidOCR digit mode on upscaled crops; if accuracy is insufficient, train the small two-digit classifier (ResNet-32-style, 0–99) on Roboflow number crops — decision recorded in the story PR. *(RapidOCR recognition-only on gray/Otsu variants was sufficient on fixtures; CNN deferred.)*
- [x] Tracklet vote: number accepted after ≥ 3 consistent reads (confidence scales with vote margin); below threshold → `jersey: null`.
- [ ] Attach voted jersey to the shooter track on each shot event; roster map (jersey → player name) as optional CLI input `--roster roster.yaml`. *(First half done — fusion attaches the voted jersey; `apply_roster` helper exists but the `--roster` CLI flag is not wired.)*

## Acceptance Criteria

- Scorer jersey correct for ≥ 85% of ground-truth scoring events on eval clips; **never** confidently wrong (wrong number with high confidence) — prefer null.
- Fixes reviewer-flagged jersey errors (shot_0029 → #4, shot_0075, shot_0078, shot_0090, shot_0094).
- With `--roster`, events include player names; without it, jersey number only.

## Edge Cases

- Number never legible during the event window (back never faces camera) → null, narration omits the number.
- Same number on both teams — jersey must be interpreted within the track's team context.
- Single-digit vs double-digit confusion (4 vs 44) — vote across crops, not per-crop best guess.

## Functional Tests

- Unit: legibility gate on synthetic sharp/blurred crops.
- Unit: tracklet voting (3 consistent reads win over 1 outlier; 2-2 split → null).
- Integration (eval marker): scorer jersey matches ground truth for labeled events; confidence ordering sane.
