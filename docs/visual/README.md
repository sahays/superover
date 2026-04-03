# Super Over Alchemy

AI-powered video analysis platform built on Google Gemini.

> **Problem:** Analyzing video content at scale requires expensive tools and manual effort to extract structured insights from scenes.
> **Solution:** Super Over Alchemy automates video analysis using Gemini for structured scene extraction, media compression, and semantic search — all orchestrated through a FastAPI backend on Cloud Run with a React frontend and Firestore for state.

---

## Home

Dashboard with workflow selection cards for all platform features.

![](home.png)

---

## Media Processing

Upload videos and run compression, audio extraction, and image adaptation jobs. Track processing status with real-time progress.

[List](#media-list) · [Detail](#media-detail)

### Media List
![](media.png)

### Media Detail
Job info, configuration, and results in a single view.
![](media-detail.png)

---

## Scene Analysis

AI-powered scene analysis using Gemini structured output. Upload a video, select a prompt, and get structured scene-by-scene analysis with cost tracking.

[List](#scene-analysis-list) · [Detail](#scene-detail) · [Results](#scene-results)

### Scene Analysis List
![](scene-analysis.png)

### Scene Detail
Analysis results with download options, metadata accordions for job details, video metadata, and processing info.
![](scene-detail.png)

### Scene Results
Full analysis output with cost breakdown, token counts, and chunked content.

![](scene-results-header.png)

![](scene-results-content.png)

---

## Prompts

Manage AI prompt templates that drive each analysis step. Create, edit, and configure response types and JSON schemas for Gemini.

[List](#prompts-list) · [Create](#prompts-create) · [Detail](#prompts-detail)

### Prompts List
![](prompts.png)

### Create Prompt
![](prompts-create.png)

### Prompt Detail
![](prompts-detail.png)

---

## Search

Conversational semantic video search powered by Gemini and BigQuery. Search your video library with natural language queries and get relevance-ranked results with clip previews.

![](search.png)
