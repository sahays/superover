# Branding & Visual Asset Processing Sequence Diagram

This diagram documents the workflow for brand asset management, automated safe-zone detection, logo overlay rules, and production rendering.

```mermaid
sequenceDiagram
    autonumber
    actor User as "Brand Manager / Editor"
    participant Frontend as "Next.js UI (/branding)"
    participant API as "FastAPI Gateway (/api/v1/branding)"
    participant Analyzer as "Brand & Safe-Zone Analyzer"
    participant Gemini as "Gemini Vision Model"
    participant Renderer as "Compositing Engine (FFmpeg / ImageMagick)"
    participant Storage as "Cloud Storage (GCS)"
    participant DB as "Firestore DB"

    User->>Frontend: Upload Brand Assets (Logos, Watermarks, Fonts) & Set Rules
    Frontend->>API: POST /api/v1/branding/assets
    API->>Storage: Store Brand Assets
    Storage-->>API: Asset GCS URIs
    API->>DB: Save Brand Profile Config

    User->>Frontend: Apply Branding to Video / Image Asset
    Frontend->>API: POST /api/v1/branding/apply (Media ID, Brand Profile ID)
    API->>Analyzer: Analyze Target Media Layout
    Analyzer->>Gemini: Detect Subject Regions, High Contrast Areas & Safe Zones
    Gemini-->>Analyzer: Return Safe Coordinates & Contrast Mask

    Analyzer->>Renderer: Generate Overlay Spec (Logo Position, Opacity, Padding)
    Renderer->>Storage: Fetch Brand Assets & Source Media
    Storage-->>Renderer: File Streams
    Renderer->>Renderer: Render Branded Composite Media Output
    Renderer->>Storage: Upload Branded Deliverable File
    Storage-->>Renderer: Return Output GCS Link

    API->>DB: Record Branded Output Record
    API-->>Frontend: Return Branded Media Link
    Frontend-->>User: Preview Branded Media Asset
```

## Key Technical Steps

1. **Brand Profile Management**: Ingests company logos, typography, color palettes, and positioning guidelines.
2. **AI Safe-Zone Detection**: Uses Gemini visual reasoning to detect clutter-free, non-essential regions for logo positioning.
3. **Automated Compositing**: Renders dynamic watermarks and overlays using FFmpeg / image processing tools.
