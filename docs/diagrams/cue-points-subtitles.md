# Cue Points Detection & 2-Pass Subtitle Pipeline Sequence Diagram

This sequence diagram details the 2-pass subtitle generation and cue points detection workflow, combining Speech-to-Text with Gemini AI pass refinement for high accuracy and context-aware styling.

```mermaid
sequenceDiagram
    autonumber
    actor User as "Video Editor"
    participant Frontend as "Next.js Frontend"
    participant API as "FastAPI API Gateway"
    participant Transcoder as "Audio Transcoder Engine"
    participant ASR as "Pass 1: Speech-to-Text Service"
    participant Gemini as "Pass 2: Gemini Context Alignment Model"
    participant CueEngine as "Cue Points Detection Engine"
    participant Storage as "Cloud Storage (GCS)"
    participant DB as "Firestore DB"

    User->>Frontend: Submit Video for Subtitle & Cue Point Generation
    Frontend->>API: POST /api/v1/subtitles/generate (Video ID, Language, Style Rules)
    API->>Transcoder: Extract Clean Audio Stream from Video
    Transcoder-->>API: Extracted Audio File (WAV/MP3)

    rect rgb(240, 248, 255)
        Note over API, ASR: Pass 1 — Raw Audio Transcription
        API->>ASR: Transcribe Audio File
        ASR-->>API: Raw Transcript with Timestamps & Confidence Scores
    end

    rect rgb(255, 245, 238)
        Note over API, Gemini: Pass 2 — Semantic Context & Style Alignment
        API->>Gemini: Pass 1 Transcript + Video Context + Style Guidelines
        Note over Gemini: Corrects homophones & brand terms<br/>Aligns phrase breaks with natural speech pauses<br/>Extracts visual & narrative Cue Points
        Gemini-->>API: Refined Subtitles & Categorized Cue Points
    end

    API->>CueEngine: Format Subtitle Formats (SRT, VTT, JSON) & Cue Markers
    CueEngine->>Storage: Upload .vtt, .srt, and cue_points.json files
    Storage-->>CueEngine: Return Storage URLs

    API->>DB: Store Subtitle Record & Cue Point Markers
    API-->>Frontend: Return Subtitles & Cue Points Summary
    Frontend-->>User: Display Interactive Player with Subtitle Overlay & Cue Markers
```

## Key Technical Steps

1. **Pass 1 ASR**: Rapidly converts speech to initial timestamped text transcript.
2. **Pass 2 Gemini Refinement**: Uses Gemini visual/narrative awareness to fix typos, align line-breaks naturally, and identify narrative shift cue points.
3. **Multi-Format Export**: Generates standard web captions (`.vtt`, `.srt`) and structured cue point data for automated video editing.
