# Engagement Analytics & Peak Detection Sequence Diagram

This document details the sequence flow for content engagement analysis, parsing audience measurement data (e.g. BARC viewership ratings), identifying viewership peak moments, extracting scene context, and generating content recommendations.

```mermaid
sequenceDiagram
    autonumber
    actor User as "Broadcast Analyst"
    participant Frontend as "Next.js Frontend"
    participant API as "FastAPI Gateway (/api/v1/engagement)"
    participant BARC as "BARC Data Parser (libs/engagement)"
    participant PeakEngine as "Peak Detection Engine"
    participant Gemini as "Gemini Scene Context Extractor"
    participant RecsEngine as "Recommendation Engine"
    participant DB as "Firestore DB / BigQuery"

    User->>Frontend: Upload Broadcast Ratings Data (CSV/XML) & Target Video ID
    Frontend->>API: POST /api/v1/engagement/upload-ratings
    API->>BARC: Parse Ratings File & Validate Timecodes
    BARC-->>API: Structured Viewership Time-Series

    API->>PeakEngine: Analyze Ratings Time-Series for Viewership Peaks & Drops
    PeakEngine-->>API: Return Peak Timecode Segments & Spikes

    loop For each detected peak segment
        API->>Gemini: Analyze Video Segment Context (Visuals, Audio, Sentiment)
        Note over Gemini: Identifies why engagement spiked<br/>(e.g., goal scored, dramatic reveal, music entry)
        Gemini-->>API: Return Scene Context & Engagement Drivers
    end

    API->>RecsEngine: Generate Content Optimization Recommendations
    RecsEngine-->>API: Actionable Promo & Editing Recommendations

    API->>DB: Store Engagement Report, Peak Highlights & Recommendations
    DB-->>API: Confirmation

    API-->>Frontend: Return Engagement Analysis Results
    Frontend-->>User: Render Interactive Viewership Graph with Scene Peak Overlays
```

## Key Technical Steps

1. **Rating Time-Series Parsing**: Ingests audience metrics (BARC data) and normalizes timestamps relative to video playback.
2. **Mathematical Peak Detection**: Algorithms detect statistically significant viewership spikes and retention drop-offs.
3. **Multimodal Scene Attribution**: Uses Gemini to explain *why* audience engagement spiked during specific timeframes.
