# Image Adaptation ("Adapts") Sequence Diagram

This document illustrates the sequence flow for AI-powered generative image adaptation, converting hero visual assets into targeted aspect ratios and compositions (e.g. 16:9 thumbnails, 2:3 posters, 9:16 story formats) powered by Gemini Vision models.

```mermaid
sequenceDiagram
    autonumber
    actor User as "Client / User"
    participant Frontend as "Next.js Frontend"
    participant API as "FastAPI Gateway (/api/v1/images)"
    participant Storage as "Cloud Storage (GCS)"
    participant Engine as "Adapt Engine (libs/gemini)"
    participant Gemini as "Google Gemini 3 Pro Vision"
    participant DB as "Firestore DB"

    User->>Frontend: Select Source Image & Target Formats (16:9, 9:16, 2:3)
    Frontend->>API: POST /api/v1/images/adapts (Image ID / URL, Target Specs, Prompt Hints)
    API->>Storage: Fetch Source Image Binary
    Storage-->>API: Return Image Buffer

    loop For each requested aspect ratio
        API->>Engine: Prepare Adapt Task (Aspect Ratio, Resolution, Safe Zones)
        Engine->>Gemini: Request Generative Adaptation (Image-to-Image + Composition Prompt)
        Note over Gemini: Analyzes saliency (faces, logo, subject)<br/>Generates recomposed image preserving context
        Gemini-->>Engine: Return Recomposed Image Bytes
        Engine->>Storage: Store Output Image (gs://bucket/adapts/{id}_{format}.jpg)
        Storage-->>Engine: Confirm Storage URL
    end

    API->>DB: Save Adapt Job & Asset Metadata
    DB-->>API: Confirmation
    API-->>Frontend: Return Adapt Job Results & Artifact URLs
    Frontend-->>User: Display Side-by-Side Comparison & Download Options
```

## Key Technical Steps

1. **Saliency Preservation**: Identifies key focal points (characters, products, titles) using Gemini visual reasoning.
2. **Generative Recomposition**: Natively generates requested target aspect ratios without naive stretching or harsh letterboxing.
3. **Storage & Delivery**: Saves resulting high-resolution artifacts to Cloud Storage and updates Firestore records.
