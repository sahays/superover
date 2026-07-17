# Story 2: Eval Dataset & Scoring Harness

## Summary

Turn the ~20 human-reviewed 30 s clips into a labeled eval set and build the scoring harness that every subsequent story reports against, following `docs/tech/evaluation-strategy.md` (Rung 1: deterministic golden set).

## Tasks

- [ ] `evals/basketball/build_dataset.py`: download the review clips from their URLs into `evals/basketball/datasets/clips/` (gitignored; manifest holds URLs).
- [ ] `evals/basketball/datasets/manifest.yaml`: per clip — URL, checksum, and ground-truth events `{t_start, t_end, type, outcome, team, points, jersey}` transcribed from reviewer notes **plus one manual viewing pass** (review notes only flag errors; label all scoring events).
- [ ] `evals/basketball/run_eval.py`: match predicted events to ground truth within ±2 s tolerance windows; report event precision/recall/F1 + attribute accuracy (team, points, jersey) per clip and aggregate.
- [ ] Regression assertions for each reviewer-flagged error (e.g. shot_0013: no made-FT at 00:21–26; shot_0017: 3PT credited to Kansas; shot_0029: scorer jersey #4).
- [ ] Wire into pytest with an `eval` marker (skipped unless clips are present locally).

## Acceptance Criteria

- `manifest.yaml` has complete scoring-event labels for every clip, verified by a human.
- `run_eval.py` on an empty prediction set reports recall 0 without crashing; on ground truth as predictions reports P=R=1.0.
- Eval output is a single table (per-clip + aggregate) suitable for pasting into a PR description.

## Edge Cases

- Clip URL no longer resolves → build script reports and continues; eval skips that clip with a warning.
- Two ground-truth events within one tolerance window (fast put-back) — matching must be 1:1 (greedy by time distance).
- Events at clip boundaries (t < 2 s or t > 28 s).

## Functional Tests

- Unit: tolerance-window matcher on synthetic prediction/truth pairs (exact, offset-by-1s, offset-by-3s, duplicate predictions).
- Unit: attribute scoring counts only matched events.
- Integration: `run_eval.py --manifest tests/fixtures/mini_manifest.yaml` against a canned predictions file reproduces known scores.
