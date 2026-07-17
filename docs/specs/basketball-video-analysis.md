# Basketball Video Analysis CLI — Research Findings & Implementation Plan

Status: **draft for review** (2026-07-17)

## Context

We are building a basketball broadcast-video analysis tool. Gemini (3.1 Pro, prompt-only) was already tried and produces inaccurate results. A human review of Gemini's outputs on ~20 thirty-second clips (Kansas vs Kansas State college game, `shot_NNNN.mp4` segments) catalogs the recurring errors; they are distilled into the taxonomy below. The goal: a tool that detects game events **accurately, with correct timestamps**, starting as a simple local CLI for fast iteration.

Implementation plan with high-level design: `docs/plans/basketball-video-analysis/plan.md`.

## Error taxonomy from human review (what the tool must fix)

Every reviewer-flagged error falls into one of these classes:

| # | Failure class | Examples from review |
|---|---------------|----------------------|
| 1 | **Shot outcome wrong** (says made when missed, or vice versa) | shot_0013 "Hunter misses the shot"; shot_0020 "There was no scoring" |
| 2 | **Missed scoring events entirely** | shot_0028 "21–29 was an actual scoring action missed"; shot_0030, shot_0035, shot_0084, shot_0085 |
| 3 | **Offense/defense team swapped** | shot_0015, shot_0071, shot_0092, shot_0093 |
| 4 | **Wrong team credited with score** | shot_0017 "Score is actually scored by Kansas"; shot_0094 |
| 5 | **Wrong player / jersey number** | shot_0029 "Jersey #4 was the scorer"; shot_0075, shot_0078, shot_0090 |
| 6 | **Wrong shot type** (3PT vs 2PT etc.) | shot_0024 "not a three-pointer"; shot_0099 "should have been missed 3 point attempt" |
| 7 | **Imprecise/wrong event timing** | shot_0082 "Foul is only towards the end" |
| 8 | **Generally incorrect play narrative** | shot_0069, shot_0083 |

Implication: the highest-value signals are (a) **did the ball go through the hoop, and when**, (b) **which basket/direction → which team**, (c) **jersey number of the shooter**, (d) **shooter's position vs 3PT line** at release. These are all *perception* tasks that specialized detectors do better than a VLM narrating pixels.

## Scoping decisions (confirmed)

1. **Scoring events first** — V1 targets made/missed shots, timestamps, scoring team, jersey number, 2PT vs 3PT. Fouls/blocks/turnovers later.
2. **Hybrid architecture** — CPU models produce verified facts (event, timestamp, team, jersey, shot type); Gemini only writes narrative prose constrained by those facts.
3. **Lives inside this repo** — reuse config pattern, Gemini wrapper, pytest setup.
4. **Eval set = the reviewed clips** — the ~20 `shot_NNNN.mp4` clips; ground-truth labels built from the reviewer notes plus one manual viewing pass (the review only flags errors — it is not a complete event list per clip).

## Research findings

### Why Gemini-only fails (published evidence)

- Apple's VBenchComp (NeurIPS 2025 WS) shows video-LLM benchmark scores largely come from language priors and shuffle-invariant perception — video LLMs are not doing the temporal reasoning that second-accurate event detection requires.
- SPORTU benchmark (arXiv 2410.08474): best VLM scores ~52.6% on hard sports-video tasks (foul detection, rule application).
- BARD (CVIU 2026, 60 NBA games, 14.7k clips with jersey numbers + team colors) benchmarks Gemini 2.5 Pro on structured basketball recognition and finds it underperforms — the closest published replication of our own experiment.
- Grounded-VideoLLM / TimeExpert (ICCV 2025): timestamps must be engineered into the architecture; they don't emerge from prompting.
- The field's consensus fix is hybrid: specialist detectors produce structured facts, the LLM narrates (LLM-IAVC ICCV 2025; KEANet 2024; SoccerAgent ACM MM 2025 — beats end-to-end VLMs).

### The problem's academic name: action spotting / precise event spotting (PES)

- Survey: arXiv 2505.03991 (2025). SOTA architectures: T-DEED (CVPRW 2024, sport-agnostic, won SoccerNet Ball Action Spotting, mAP@1s = 73.4) and E2E-Spot (ECCV 2022, frame-accurate, trains on one GPU). SoccerNet 2025 added team-aware spotting (team attribution inside the spotting head).
- Basketball datasets with exactly our taxonomy: NCAA dataset (CVPR 2016; 257 games; 11 classes = {3PT,2PT,FT,layup,dunk}×{success,failure}+steal — purpose-built models hit only ~0.44–0.52 mAP), Basketball-51 (10.3k clips, {2PT,3PT,mid,FT}×{make,miss}, 79% acc but mid-range make/miss recall ~35%), NSVA (32k NBA clips — salient-player-ID success rate 4.63, i.e. "who scored" from pixels alone is brutally hard), MultiSports, FineSports, SpaceJam.

### Scoreboard OCR as ground truth — published prior art, not a hack

- Harris (UNC), arXiv 2411.00862: YOLOv8 finds clock/score-bug regions, PaddleOCR reads them, monotonic-clock constraint denoises; **93.81% of frames read perfectly before post-processing**; trained across NBA/NCAA/high-school broadcasts. Joined to play-by-play, this yields second-accurate timestamps, scoring team, scorer, and the 1/2/3-point delta.
- This is how basketball video datasets were themselves labeled (NSVA, BARD, VC-NBA-2022 all align clock OCR / play-by-play). ACM MM 2016 (Bettadapura et al.) did play-by-play/video alignment a decade ago. ScoreSight (OSS) validates the fixed-ROI + per-field OCR + temporal-voting design.
- Known caveats: bug disappears during replays/graphics wipes; on-screen score can lag the actual make by ~1–2 s (carry-forward and re-sync logic is standard).

### Jersey numbers

- Koshkina & Elder (CVPRW 2024, code: `mkoshkina/jersey-number-pipeline`): legibility classifier → pose-guided crop → fine-tuned PARSeq → tracklet-level probabilistic vote = 87.45% (SoccerNet). Key insight: the number is legible in only a small fraction of frames — per-frame VLM reading is structurally disadvantaged vs tracklet aggregation. ~90% tracklet accuracy is the realistic broadcast ceiling (SoccerNet 2023 winner: 90.1%).
- Roboflow found a tiny ResNet-32 two-digit classifier (93%) beats a fine-tuned VLM (86%) on 3.6k NBA crops — for basketball (0–99), a small digit classifier + temporal voting is both more accurate and far cheaper than general OCR.

### Team assignment

- Koshkina et al. (CVPRW 2021, contrastive unsupervised): 94% from a single frame, 97% within ~17 s of video — team clustering can be bootstrapped within one 30-second clip, fixing offense/defense swaps at the perception level. Cheaper first pass: HSV torso-pixel clustering; SigLIP+KMeans fallback (roboflow/sports approach); filter referees via detector class; map cluster→team name via score-bug abbreviations.

### CPU-only components (all inference local)

- **Detector**: nano YOLO is the CPU sweet spot — YOLO26n ~39 ms/frame, YOLO11n ~56 ms/frame at 640px ONNX on a 2 GHz Xeon; OpenVINO/INT8 gives ~2x more. The ball is tiny in broadcast frames → higher input res or cropped regions for ball/rim.
- **Pretrained basketball data (don't start from scratch)**: Roboflow Universe `basketball-player-detection-3` (roboflow-jvuqo) — 10 classes including `ball`, `rim`, **`ball-in-basket`** (direct made-shot signal), `number`, `player-in-possession`, `player-jump-shot`, `player-layup-dunk`, `player-shot-block`, `referee`; built on broadcast NBA footage. Also `basketball-court-detection-2` (33 court landmarks) for homography → 2PT/3PT.
- **Made-shot detection**: no maintained broadcast-grade OSS exists (avishah3's 97%-claim tracker is single-hoop phone footage; chonyy's repos are dead). Proven recipe to implement (~few hundred lines): ball passes from above-rim through inner-rim to below within N frames = make; `ball-in-basket` as a second signal; score-bug delta as the third and most reliable confirmation.
- **Score-bug OCR**: RapidOCR (Apache 2.0, ONNX, ~0.2 s/image CPU, much faster on small crops).
- **Tracking**: `supervision` ByteTrack (MIT, active) for players; custom trajectory buffer for the ball (Kalman pedestrian assumptions don't fit ballistic flight); reset tracks at camera cuts.
- **Action recognition (later phases)**: MoViNet-A0-Stream (the only CPU-designed family, ~3.7 ms/frame mobile CPU) or TSM-R18; fine-tune on SpaceJam (~32.5k basketball clips). Fouls/turnovers are the least-solved — use free-throw-scene + possession-change heuristics, not raw action recognition.
- **Decode**: PyAV (frame-exact PTS timestamps — critical since outputs are timestamps; OpenCV seeking is unreliable). Two-tier sampling: base pass 5–10 fps; re-decode ±2 s at native fps around rim events (ball crosses the rim plane in ~100–150 ms = 3–4 frames at 30 fps).
- **Budget**: 30 s clip on 8-core x86 ≈ 10–20 s detection + ~5 s everything else. Fine for batch; near-realtime at 5 fps sampling.
- **Architecture to copy**: roboflow/sports (MIT, active; basketball court keypoints + jersey OCR), swapping GPU-sized parts (RF-DETR, SAM2) for YOLO-nano + ByteTrack.

### Reusable pieces already in this repo

- **`libs/gemini/scene_analyzer.py`** is standalone-ready: imports only `config.settings` + `libs/gemini/common.py` (no Firestore/GCS), takes local bytes via `types.Part.from_bytes`, supports `response_schema` structured output, MAX_TOKENS continuation, retries, cost calc.
- **Architectural precedent**: `docs/tech/cue-points-detection.md` — two-layer design where deterministic CPU signals produce a typed anchor timeline and Gemini classifies/snaps **without inventing timestamps**. Core rule: *"Signals own the timestamps; the LLM owns the meaning."* This CLI is its video-domain twin. `docs/tech/subtitle-2pass-sequence.md` is the shipped example of the same pattern.
- **`docs/tech/evaluation-strategy.md`** — 3-rung eval ladder (deterministic/golden with timing-IoU → random sampling → LLM judge), proposed `evals/` layout. No harness exists yet; this project builds its first instantiation.
- **Conventions**: argparse scripts in `scripts/`, pydantic-settings config, pytest markers (`unit`/`integration`/…). No local video/ML stack exists anywhere — this package is the repo's first.

## Proposed approach

Two-layer architecture: **deterministic CPU signals own the timestamps and facts; Gemini owns only the prose.**

```
clip.mp4
  │  PyAV decode (frame-exact PTS)
  ▼
┌─ Layer 1: CPU perception (all local, ONNX) ─────────────────────────┐
│ Signal A  Score-bug OCR (RapidOCR): score deltas → made shots with  │
│           exact timestamps, scoring team, 1/2/3 points              │
│ Signal B  Ball/rim YOLO + trajectory: makes AND misses, shot moment │
│ Signal C  Player tracking (ByteTrack) + team clustering (HSV) +     │
│           jersey digits (crop → tiny classifier → tracklet vote)    │
│ Signal D  (later) court homography → 2PT vs 3PT from shooter feet   │
└──────────── fuse → typed event timeline (JSON, confidences) ────────┘
  │
  ▼
Layer 2: Gemini narration (reuse libs/gemini/scene_analyzer.py,
response_schema; prompt embeds the event timeline; rule: snap to
anchors, never invent timestamps or contradict facts)
```

Signal fusion beats any single detector: a "make" requires trajectory-through-rim OR `ball-in-basket`, and is confirmed + point-typed by a score-bug delta within ~2 s. A shot with no score delta = miss (fixes error class 1). A score delta with no narrated event = missed event (fixes class 2).

### New code layout

```
libs/basketball/            # new package — no Firestore/GCS deps
    video.py                # PyAV decode, 2-tier sampling
    scorebug.py             # locate static bug, per-field crops, RapidOCR,
                            #   majority-vote smoothing, score-change events
    detect.py               # ONNX Runtime inference: ball/rim/player/number
    shots.py                # ball-trajectory made/miss logic + ball-in-basket
    teams.py                # HSV torso clustering per track (SigLIP fallback)
    jersey.py               # number-crop digit classifier + tracklet voting
    timeline.py             # fuse signals → typed events {t, type, team,
                            #   points, jersey, confidence, evidence[]}
    narrate.py              # Gemini pass via libs/gemini (SceneAnalyzer)
scripts/basketball_analyze.py   # argparse CLI (repo convention)
evals/basketball/
    datasets/manifest.yaml  # clip URLs + ground-truth events
    build_dataset.py        # download the ~20 review clips
    run_eval.py             # tolerance-window scoring per evaluation-strategy.md
requirements-basketball.txt # numpy, av, opencv-python-headless, onnxruntime,
                            # rapidocr-onnxruntime, supervision
                            # (ultralytics only for train/export — AGPL note)
```

Separate requirements file so the cloud services' dependency set stays untouched. Intermediate artifacts (sampled frames, detections, OCR reads) are cached per clip under a work dir so downstream logic re-runs instantly — the fast-iteration loop.

### Implementation phases

**Phase 0 — Scaffold + eval set (no ML).** CLI skeleton, PyAV decode, `build_dataset.py` downloads the review clips, `manifest.yaml` with ground-truth events (reviewer notes + one manual viewing pass). Metrics: event precision/recall at ±2 s tolerance + attribute accuracy (team/points/jersey).

**Phase 1 — Score-bug OCR (highest value, zero training).** `scorebug.py` per the ScoreSight/Harris recipe. Deliverable: scoring events with exact timestamps, team, points. Addresses error classes 1, 2, 4, 6, 7 — the majority of the reviewer-flagged errors. First eval numbers land here.

**Phase 2 — Ball/rim/player detection + made/miss logic.** Fine-tune YOLO11n (or YOLO26n) on `basketball-player-detection-3`; export ONNX/INT8. The one-time fine-tune needs a few GPU-hours (free Colab or Roboflow hosted training); inference is CPU-only. Detects misses (invisible to OCR) and precise shot moments.

**Phase 3 — Player + team attribution.** ByteTrack via `supervision`; HSV torso clustering (cluster→team name via score-bug abbreviations); jersey `number` crops → small digit classifier → tracklet voting. Fixes error classes 3, 5.

**Phase 4 — Shot type + Gemini narration.** 2PT/3PT primarily from score delta; court homography only if ambiguity remains. `narrate.py` feeds the verified timeline to `SceneAnalyzer.analyze_chunk` with a `response_schema` matching the current output format (Timestamp / Event Title / Analysis / Category) so results are directly comparable to the reviewed Gemini outputs.

**Later (out of V1):** fouls/blocks/turnovers via possession-change + free-throw-scene heuristics and the `player-shot-block` class; optional play-by-play join (clock OCR → ESPN/NCAA feed) for player names with zero vision.

### CLI interface

```bash
python scripts/basketball_analyze.py clip.mp4 -o out.json   # structured events
    --narrate          # add Gemini prose pass
    --debug-video      # annotated MP4 (boxes, trajectories, OCR reads)
    --stage scorebug   # run/re-run a single stage against cache
python evals/basketball/run_eval.py                          # score vs manifest
```

## Verification

1. **Unit tests** (pytest, `unit` marker): score-parse smoothing, trajectory make/miss geometry, timeline fusion — synthetic fixtures, no models needed.
2. **Eval harness** (`run_eval.py`): precision/recall of scoring events at ±2 s vs `manifest.yaml`, plus team/points/jersey accuracy. Run after each phase; numbers must improve monotonically.
3. **Review regression check**: for each reviewer-flagged clip, assert the specific error is fixed — e.g. shot_0013: no made-FT event at 00:21–26; shot_0017: 3PT credited to Kansas; shot_0029: scorer jersey #4; shot_0024: 2PT not 3PT; shot_0028: scoring event detected at 00:21–29.
4. **End-to-end**: `--narrate --debug-video` on 2–3 clips; visually confirm the annotated video and that the Gemini prose contains no fact absent from the timeline.

## Open questions & risks

- **Score-bug presence in the eval clips**: verify early (Phase 0) that the 30 s eval segments retain the broadcast score bug and that it's legible at the encoded resolution. If a clip lacks the bug (replay wipes, crowd cuts), Signal B (ball/rim) is the only make/miss source for that clip — fusion must degrade gracefully.
- **Score-bug lag**: on-screen score updates ~1–2 s after the make; the fusion layer should timestamp events from the ball-through-rim moment when available and use the OCR delta as confirmation, not as the timestamp source.
- **Replays inside segments**: a replayed made basket can double-count via trajectory detection (though not via score delta — another reason fusion wins). Shot-boundary detection to segment camera cuts is cheap insurance.
- **One-time GPU fine-tune**: nano-YOLO training on the ~10-class basketball dataset is impractical on CPU; plan is a few hours on free Colab or Roboflow hosted training, then ONNX export. Inference remains CPU-only.
- **Licensing**: Ultralytics YOLO is AGPL-3.0 (fine for internal tooling; revisit if this ships in a commercial product — RF-DETR/Apache alternatives exist at a CPU-speed cost). Roboflow Universe datasets are typically CC BY 4.0 — confirm per-project license before training.
- **Jersey-number ceiling**: ~90% tracklet-level accuracy is the published broadcast ceiling; the timeline schema carries per-attribute confidence so narration can hedge ("#4" vs omitting the number) below a threshold.
- **Eval-set size**: ~20 clips from one game is enough to iterate but not to generalize (one score-bug layout, two jersey sets). Post-V1: add clips from 2–3 other broadcasts before trusting the numbers.
