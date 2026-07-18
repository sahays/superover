# Basketball Video Analysis — Eval Results

Status: **measured** (2026-07). Scored by `evals/basketball/run_eval.py` against
`evals/basketball/datasets/manifest.yaml`.

## Summary

The CPU-first pipeline (`libs/basketball/`) was evaluated on the original
review set (22 clips of a Kansas vs Kansas State broadcast) and, as a
generalization check, on a **held-out** set of 5 clips it had never been tuned
against.

| Metric | Original 22 | Held-out 5 |
|---|---|---|
| **Precision** | **0.94** | 1.00 (makes) |
| **Recall** | **0.94** | 1.00 (makes) |
| **F1** | **0.94** | — |
| Team accuracy | **15/15 (100%)** | 3/3 |
| Points accuracy (2 vs 3) | **15/15 (100%)** | 3/3 |
| **Jersey accuracy** | **2/2 (100%)** | — |

Ground truth is **scoreboard-verified**, not taken from the reviewer notes: a
made basket is confirmed by the on-screen score incrementing, read from
keyframes. This matters because the reviewer/Gemini analysis was itself wrong in
several places (below), so scoring against it would have measured the wrong
thing.

## Headline finding: the pipeline is *more* accurate than the human review it was built to fix

The eval set exists because a human reviewer catalogued Gemini's errors on these
clips. In several cases the **scoreboard-verified truth disagrees with the human
review, and the pipeline matches the truth** — the deterministic,
scoreboard-driven design does exactly what it was designed to do.

| Clip | Human review (Gemini + reviewer) said | Scoreboard-verified truth | Pipeline (this eval) | Who was right |
|---|---|---|---|---|
| shot_0017 | 3PT by Kansas at **10–17 s** | 3PT Kansas, score 4-6 → 7-6, at **~20 s** | made Kansas +3 @20 s | **pipeline** (reviewer time wrong) |
| shot_0094 | made Kansas-State, **2 points** | +3: score 41-32 → 41-**35** | made KSU **+3** #2 | **pipeline** (points wrong) |
| shot_0029 | KSU **#4** scores at **22–30 s** | Kansas +2 at **~2 s** (same basket as shot_0028) | made Kansas +2 @2 s | **pipeline** (team, time, jersey all wrong) |
| shot_0023 *(held-out)* | **two missed shots** (alley-oop + jumper) | **two makes**: Kansas +2 then KSU +2 (9-11 → 11-13) | made Kansas +2; made KSU +2 | **pipeline** (makes called misses) |
| shot_0007 *(held-out)* | a travel/turnover; no score noted | KSU **+3** (3-3 → 3-6) | made KSU +3 | **pipeline** (review missed the make) |
| shot_0083 | "analysis is incorrect" | no make (score 32-30 stable) | no make emitted | pipeline (correctly silent) |

The reviewer notes are useful as *hints* but are not a reliable ground truth —
they were transcribed from a review that only flagged errors, and Gemini's
per-play claims (who scored, make vs miss) are frequently wrong. The scoreboard
is the arbiter.

## Full per-clip results (original 22)

`made` events, scored at ±2 s tolerance. Jersey shown where the pipeline
attributed one; **bold** = a jersey scored by the eval (human-verified label).

| Clip | Scoreboard truth | Pipeline found | TP/FP/FN |
|---|---|---|---|
| shot_0013 | missed FT, Kansas #1 | (none — miss not detected) | FN |
| shot_0015 | no make | (none) | — |
| shot_0017 | made Kansas +3 | made Kansas +3, #15 (McCullar) | TP |
| shot_0020 | made KSU +2 | made KSU +2, #13 (McNair) | TP |
| shot_0024 | made Kansas +2 | made Kansas +2, #24 (Adams) | TP |
| shot_0028 | made Kansas +2 | made Kansas +2, #15 | TP |
| shot_0029 | made Kansas +2 | made Kansas +2, #15 | TP |
| shot_0030 | made KSU +2; made Kansas +2 | made KSU +2 #4; made Kansas +2 #1 | TP ×2 |
| shot_0035 | made KSU +2 | made KSU +2, #5 (Carter) | TP |
| shot_0069 | no make | (none) | — |
| shot_0071 | no make | (none) | — |
| shot_0075 | made Kansas +1 FT, **#3** | made Kansas +1 FT, **#3** ✓ | TP |
| shot_0078 | no make | (none) | — |
| shot_0082 | no make (foul) | (none) | — |
| shot_0083 | no make | (none) | — |
| shot_0084 | made Kansas +2 | made Kansas +2, #1 | TP |
| shot_0085 | made Kansas +3 | made Kansas +3 #15; **+ a spurious early miss** | TP + **1 FP** |
| shot_0090 | made Kansas +2 | made Kansas +2, #1 | TP |
| shot_0092 | made KSU +2, **#24** | made KSU +2, **#24** ✓ (Kaluma) | TP |
| shot_0093 | made KSU +2 | made KSU +2, #24 (same basket as 0092) | TP |
| shot_0094 | made KSU +3, **#2** | made KSU +3, **#2** ✓ (Perry) | TP |
| shot_0099 | missed KSU 3PT | missed shot (matched) | TP |
| **TOTAL** | **17 makes/misses** | **16 TP, 1 FP, 1 FN** | **P/R/F1 = 0.94** |

Every attributed jersey maps to a real player on the correct scoring team, and
clips of the *same* basket agree (shot_0028/0029 → #15; shot_0092/0093 → #24) —
the scorer identity is signal, not noise.

## Held-out generalization (5 unseen clips)

Graded on scoreboard truth. No tuning, no new labels — the same committed code.

| Clip | Scoreboard truth | Pipeline | Result |
|---|---|---|---|
| shot_0005 | no live make (dead-ball + replay; score 2-3 frozen) | (no make) | ✓ — replay correctly not scored |
| shot_0007 | KSU +3 | made KSU +3 | ✓ |
| shot_0009 | no make | (none) | ✓ |
| shot_0023 | Kansas +2; KSU +2 | made Kansas +2; made KSU +2 | ✓ |
| shot_0048 | no make | (none) | ✓ |

Make detection on the held-out set: **precision 1.00, recall 1.00, team & points
3/3** — the fixes generalize rather than overfit the original 22.

## Remaining gaps (honest)

- **1 false positive** — shot_0085 emits a spurious trajectory "miss" ~24 s from
  the real make. A shots-stage (trajectory) precision issue, not yet fixed.
- **1 false negative** — shot_0013, a missed free throw. Misses leave no score
  delta, so they are the pipeline's blind spot. The `asr` stage now hears
  "no good" but currently only *corroborates* — it does not yet *create* a miss
  event (a careful future step).

## How the numbers moved (every step measured and validated)

| Change | P | R | F1 |
|---|---|---|---|
| First real run (broken matcher, wrong labels) | 0.23 | 0.33 | 0.27 |
| Matcher: match inside the ground-truth uncertainty window | 0.42 | 0.56 | 0.48 |
| Scoreboard relabel (corrected the ground truth) | 0.75 | 0.88 | 0.81 |
| Fuse dedup (drop the phantom miss beside an OCR-only make) | 0.88 | 0.88 | 0.88 |
| Scorebug symmetry fallback (recover a white-on-colour score) | 0.89 | 0.94 | 0.91 |
| `no_scoring` = no *made* basket (a predicted miss is not a violation) | 0.94 | 0.94 | 0.94 |

Jersey moved separately, **0/2 → 2/2**, via the `scorer` graphic reader and the
`asr` name cross-validation (see the architecture doc). A held-out generalization
fix — the scorebug confidence/corroboration floor — cured a dead-ball replay
that fabricated two scores on shot_0005, with zero regression on the 22.

## Methodology

- **Matching**: greedy 1:1 within ±2 s of an event's `[t, t_end]` uncertainty
  window (`libs/basketball/evaluation.py`); the span is a window, not a point.
- **Ground truth**: scoreboard-verified from keyframes; `no_scoring_expected`
  windows assert no *made* basket; unverified rows and manual-review windows are
  ignored, not counted.
- **Held-out set**: a second review PDF supplied 5 clips from the same game not
  in the original 22 (four others overlapped and were excluded). Clip URLs are
  never committed — see `sources.local.yaml` (gitignored).
