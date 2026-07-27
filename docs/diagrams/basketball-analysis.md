# Basketball Multimodal Video Analysis Sequence Diagram

This diagram documents the end-to-end AI analysis workflow for sports (basketball) video content, performing ASR speech recognition, scorebug OCR detection, jersey/player identification, shot detection, and automated play-by-play synthesis.

```mermaid
sequenceDiagram
    autonumber
    actor User as "Sports Analyst / Editor"
    participant Frontend as "Next.js UI"
    participant API as "FastAPI Gateway"
    participant BasketballLib as "Basketball Pipeline (libs/basketball)"
    participant ASR as "Speech-to-Text Engine"
    participant Gemini as "Gemini 2.5 Pro Vision Model"
    participant Cache as "Evaluation & Timeline Cache"
    participant DB as "Firestore DB / BigQuery"

    User->>Frontend: Select Basketball Match Video & Start Analysis
    Frontend->>API: POST /api/v1/basketball/analyze (Video ID, Config)
    API->>BasketballLib: Trigger Multimodal Pipeline

    par Audio Speech Processing
        BasketballLib->>ASR: Extract Commentary Audio & Run Speech-to-Text
        ASR-->>BasketballLib: Return Timestamped Transcript & Key Phrases
    and Visual & OCR Processing
        BasketballLib->>Gemini: Detect Scorebug, Clock, Quarter & Team Scores
        Gemini-->>BasketballLib: Return Scorebug Timeline Data
    and Player & Shot Detection
        BasketballLib->>Gemini: Identify Jersey Numbers, Shot Locations & Outcomes
        Gemini-->>BasketballLib: Return Player Tracking & Shot Matrices
    end

    BasketballLib->>BasketballLib: Consolidate Play-by-Play (PBP), Shots & Timeline
    BasketballLib->>Cache: Cache Intermediate Stages & Evaluation Metrics
    BasketballLib->>DB: Store Play-by-Play Events & Shot Charts

    API-->>Frontend: Return Analysis Summary & Timeline ID
    Frontend->>API: GET /api/v1/basketball/timeline/{id}
    API->>DB: Fetch Timeline & Shot Events
    DB-->>API: Return Structured Match Data
    Frontend-->>User: Interactive Basketball Match Timeline, Shot Chart & Player Stats
```

## Key Technical Steps

1. **Commentary ASR Integration**: Transcribes speech to capture play calls, referee announcements, and player names.
2. **Scorebug Visual OCR**: Periodically samples video frames to read live scores, shot clocks, and period indicators.
3. **Jersey & Shot Matrix**: Detects player jersey numbers and maps field goal attempts onto shot location charts.
4. **Timeline Synthesis**: Combines vision, speech, and OCR into a unified interactive match timeline.
