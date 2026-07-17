# Plan: Basketball Video Analysis CLI

Spec: [`docs/specs/basketball-video-analysis.md`](../../specs/basketball-video-analysis.md)

## Context

Gemini-only prompting misidentifies basketball events (wrong shot outcomes, swapped teams, wrong jersey numbers, imprecise timestamps). This plan builds a local CLI where **deterministic CPU perception owns the timestamps and facts, and Gemini owns only the prose** — the same rule as `docs/tech/cue-points-detection.md`. V1 scope: scoring events (made/missed, team, scorer jersey, 2PT/3PT/FT, second-level timestamps) on 30-second broadcast clips.

## High-Level Design

### Component view

```mermaid
flowchart TB
    CLIP[clip.mp4] --> VID["video.py\nPyAV decode, frame-exact PTS\n2-tier sampling: 5-10 fps base,\nnative fps around rim events"]

    subgraph L1["Layer 1 — CPU perception (ONNX, local)"]
        VID --> SB["scorebug.py\nlocate score bug, per-field crops,\nRapidOCR + majority-vote smoothing\n→ score-change events (team, ±1/2/3)"]
        VID --> DET["detect.py\nYOLO-nano ONNX:\nball / rim / ball-in-basket /\nplayer / number / referee"]
        DET --> SHOTS["shots.py\nball trajectory vs rim\n→ make/miss + shot moment"]
        DET --> TRK["teams.py\nByteTrack player tracks +\nHSV torso clustering → team per track"]
        DET --> JER["jersey.py\nnumber crops → digit classifier\n→ tracklet-level vote"]
    end

    SB --> TL["timeline.py — signal fusion\ntyped events {t, type, team, points,\njersey, confidence, evidence[]}"]
    SHOTS --> TL
    TRK --> TL
    JER --> TL

    TL --> OUT["events JSON (CLI output)"]
    TL --> NAR["narrate.py\nGemini via libs/gemini SceneAnalyzer\nresponse_schema, fact-constrained"]
    NAR --> PROSE["narrated analysis\n(Timestamp / Event Title / Analysis / Category)"]
```

### Run sequence

```mermaid
sequenceDiagram
    participant U as user
    participant CLI as scripts/basketball_analyze.py
    participant V as video.py
    participant P as perception stages
    participant T as timeline.py
    participant G as Gemini (SceneAnalyzer)

    U->>CLI: clip.mp4 [--narrate --debug-video]
    CLI->>V: decode @ 5-10 fps (cached per clip)
    CLI->>P: scorebug + detect (cached per stage)
    P-->>CLI: OCR reads, detections
    CLI->>V: re-decode ±2 s @ native fps around rim events
    CLI->>P: shots / teams / jersey on event windows
    CLI->>T: fuse all signals
    T-->>CLI: event timeline JSON
    opt --narrate
        CLI->>G: timeline + clip (response_schema)
        G-->>CLI: prose constrained to timeline facts
    end
    CLI-->>U: out.json (+ narrated output, debug MP4)
```

### Fusion rules (the accuracy core)

1. A **make** requires trajectory-through-rim OR a `ball-in-basket` detection, confirmed by a score-bug delta within ~2 s.
2. The **timestamp** comes from the ball-through-rim moment; the OCR delta only confirms (the on-screen score lags ~1–2 s).
3. Shot detected but **no score delta → miss**; **score delta but no detected shot → emit the event from OCR alone** (lower confidence, timestamped by delta minus lag).
4. **Points** (1/2/3) come from the score delta; **team** from which side of the bug incremented; **scorer jersey** from the shooter's tracklet vote.
5. Every event carries per-attribute **confidence** and an **evidence list** (which signals contributed); narration hedges or omits attributes below threshold.

### Design decisions

- **Signals own timestamps; the LLM owns meaning** — Gemini never invents an event, timestamp, team, or number.
- **Stage caching** — every stage persists intermediate output (frames, detections, OCR reads) under a per-clip work dir; `--stage <name>` re-runs one stage against cache for fast iteration.
- **Separate `requirements-basketball.txt`** — the cloud services' dependency set stays untouched; this package introduces the repo's first local numeric stack (numpy, av, opencv-headless, onnxruntime, rapidocr, supervision).
- **No Firestore/GCS coupling** — `libs/basketball/` is pure local; only `narrate.py` touches the network (Vertex AI via existing `libs/gemini`).
- **One-time GPU fine-tune, CPU-only inference** — YOLO-nano fine-tuned on the Roboflow 10-class basketball dataset (Colab/hosted training), exported to ONNX/INT8.

## Epics

| Epic | Deliverable | Stories |
|------|-------------|---------|
| [Epic 1 — Foundation](epic-1-foundation/) | CLI skeleton, decode, cache, eval dataset + harness | [story-1-cli-scaffold](epic-1-foundation/story-1-cli-scaffold.md), [story-2-eval-dataset](epic-1-foundation/story-2-eval-dataset.md) |
| [Epic 2 — Scoring signals](epic-2-scoring-signals/) | Score-bug OCR, ball/rim detection, make/miss fusion | [story-1-scorebug-ocr](epic-2-scoring-signals/story-1-scorebug-ocr.md), [story-2-ball-rim-detection](epic-2-scoring-signals/story-2-ball-rim-detection.md), [story-3-shot-outcome-fusion](epic-2-scoring-signals/story-3-shot-outcome-fusion.md) |
| [Epic 3 — Attribution](epic-3-attribution/) | Player tracking, team assignment, jersey numbers | [story-1-tracking-and-teams](epic-3-attribution/story-1-tracking-and-teams.md), [story-2-jersey-numbers](epic-3-attribution/story-2-jersey-numbers.md) |
| [Epic 4 — Synthesis](epic-4-synthesis/) | Shot type, Gemini narration | [story-1-shot-type](epic-4-synthesis/story-1-shot-type.md), [story-2-gemini-narration](epic-4-synthesis/story-2-gemini-narration.md) |

Sequencing: Epic 1 → Epic 2 story 1 gives the first eval numbers with zero ML training. Epics 2–3 stories are independent after detection lands. Epic 4 last.

Out of V1 (tracked in spec): fouls/blocks/turnovers heuristics, play-by-play join, multi-broadcast generalization.
