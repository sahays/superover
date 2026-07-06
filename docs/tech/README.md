# Super Over Alchemy - Documentation

AI-powered video analysis platform using Google Gemini.

## Core Documentation

- **[Main README](../readme.md)** - Complete project overview, setup instructions, and usage guide
- **[Demo Video Transcript](demo-video-transcript.md)** - 2-minute demo script for recording walkthrough

## Architecture & Workflows

- **[Media Worker Sequence Diagram](media-worker-sequence.md)** - Video compression and audio extraction workflow
- **[Scene Worker Sequence Diagram](scene-worker-sequence.md)** - AI-powered scene analysis with Gemini integration
- **[Subtitle 2-Pass Sequence Diagram](subtitle-2pass-sequence.md)** - Chirp 3 ASR (timing) + Gemini (text) two-pass subtitle/transcription pipeline
- **[Evaluation Strategy](evaluation-strategy.md)** - Best practices for evaluating subtitle/LLM outputs: the eval ladder (deterministic/golden → random picker → LLM-judge), dataset design, and run/prompt-version tracing
- **[Search Latency Optimization](search-latency-optimization.md)** - Avatar-mode conversation search rework: curator LLM removal, BigQuery → Bigtable KNN migration (~4s → ~0.2-0.5s)

## Visual Guides

- **[Screenshots Walkthrough](screenshots/README.md)** - Feature-by-feature UI guide with annotated screenshots

## Quick Links

- **GitHub Repository:** [Add your repository URL]
- **Demo Video:** [Will be added after recording]
