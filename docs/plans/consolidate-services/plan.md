# Plan: Consolidate 4 Cloud Run Services → 2

## Context

Currently the project deploys 4 Cloud Run services: API, frontend (Next.js), media worker (FFmpeg), and AI worker (Gemini). This plan consolidates to 2 services:

1. **API service** — FastAPI serves both the REST API and the React SPA (Vite build). Eliminates CORS entirely.
2. **Unified worker** — Merges media + AI workers. Replaces FFmpeg with Transcoder API. No local file processing — everything reads/writes GCS directly.

---

## Epic 1: Frontend — Next.js → Vite SPA served by FastAPI

All pages are already `'use client'` (zero SSR), making this straightforward.

### 1.1 Restructure `frontend/` directory

Move source files from `frontend/` root into `frontend/src/`:
```
frontend/src/
  main.tsx              # NEW — ReactDOM.createRoot + BrowserRouter
  App.tsx               # NEW — Routes + Providers + AppLayout
  globals.css           # MOVED from app/globals.css
  providers.tsx         # MOVED from app/providers.tsx
  vite-env.d.ts         # NEW — Vite type declarations
  pages/                # NEW — extracted from app/ directories
    HomePage.tsx            ← app/page.tsx
    MediaPage.tsx           ← app/media/page.tsx
    MediaJobDetailPage.tsx  ← app/media/[job-id]/page.tsx
    SceneAnalysisPage.tsx   ← app/scene-analysis/page.tsx
    SceneDetailPage.tsx     ← app/scene/[id]/page.tsx
    PromptsPage.tsx         ← app/prompts/page.tsx
    EditPromptPage.tsx      ← app/prompts/[prompt_id]/page.tsx
  components/           # MOVED from components/
  lib/                  # MOVED from lib/
```

### 1.2 New config files

- **`frontend/index.html`** — Vite entry. Metadata from `layout.tsx`. Load Inter font via Google Fonts `<link>` tag (replaces `next/font/google`).
- **`frontend/vite.config.ts`** — Plugin: `@vitejs/plugin-react`. Alias: `@ → ./src`. Dev proxy: `/api` → `http://localhost:8000`.
- **`frontend/src/App.tsx`** — React Router routes:

| Next.js path | React Router path |
|---|---|
| `/` | `/` |
| `/media` | `/media` |
| `/media/[job-id]` | `/media/:jobId` |
| `/scene-analysis` | `/scene-analysis` |
| `/scene/[id]` | `/scene/:id` |
| `/prompts` | `/prompts` |
| `/prompts/[prompt_id]` | `/prompts/:promptId` |

### 1.3 Migrate Next.js APIs → React Router equivalents

Across ~18 files:
- Remove all `'use client'` directives
- `import Link from 'next/link'` → `import { Link } from 'react-router-dom'` (prop: `href` → `to`) — 12 files
- `usePathname()` → `useLocation().pathname` — `sidebar.tsx`
- `useRouter().push()` → `useNavigate()` — `MediaJobDetailPage`, `EditPromptPage`
- `useParams()` / `use(params)` → React Router `useParams()` — 3 dynamic pages
- `Inter` from `next/font/google` → Google Fonts CDN `<link>` in `index.html`

### 1.4 API client — relative URLs

**`frontend/src/lib/api-client.ts`**: Remove `NEXT_PUBLIC_API_URL`. Set `baseURL: ''` (relative). All `/api/*` calls work same-origin.

### 1.5 Package.json changes

**Remove**: `next`, `eslint-config-next`
**Add**: `vite`, `@vitejs/plugin-react`, `react-router-dom`
**Scripts**: `dev` → `vite`, `build` → `tsc && vite build`, `preview` → `vite preview`

### 1.6 Update config files

- `tsconfig.json` — Remove Next.js plugin, change `jsx: "preserve"` → `"react-jsx"`, paths to `./src/*`
- `tailwind.config.ts` — Content paths to `./index.html`, `./src/**/*.{ts,tsx}`
- `components.json` — Set `rsc: false`, update CSS path
- `.eslintrc.json` — Replace `next/core-web-vitals` with `@typescript-eslint` + `react-hooks`

### 1.7 FastAPI serves the SPA

**`api/main.py`** changes:
1. Mount `/assets` → `StaticFiles(directory=frontend/dist/assets)` (Vite build output)
2. Add catch-all `GET /{path:path}` → serves `index.html` for SPA routing (skip `/api/*` and `/health` paths)
3. Remove root `/` JSON endpoint (SPA now serves at `/`)
4. Remove CORS middleware entirely (same origin). Keep minimal localhost CORS for local dev only.

### 1.8 Dockerfile.api — multi-stage with frontend build

```
Stage 1 (node:18-alpine): npm ci + vite build → dist/
Stage 2 (python:3.9-slim): pip install + copy api/libs + COPY --from=stage1 dist → frontend/dist
```

No FFmpeg in API image. No separate frontend Dockerfile.

### 1.9 Files to delete

- `frontend/next.config.ts`, `frontend/next-env.d.ts`
- `frontend/Dockerfile`, `frontend/.dockerignore`
- `frontend/app/` directory (contents moved to `src/pages/`)

---

## Epic 2: Unified Worker — FFmpeg → Transcoder API

### 2.1 New module: `libs/transcoder/`

- **`client.py`** — `TranscoderClient` wrapping `google.cloud.video.transcoder_v1`:
  - `submit_media_job(input_gcs_uri, output_gcs_prefix, config)` → submits compression + audio extraction. Returns Transcoder job name.
  - `submit_chunking_job(input_gcs_uri, output_gcs_prefix, chunk_duration, total_duration)` → uses EditAtom per time segment, each with its own MuxStream output. Returns job name.
  - `get_job_status(job_name)` → returns state (PENDING/RUNNING/SUCCEEDED/FAILED), error, output URIs
  - `extract_metadata_from_job(job_name)` → extracts input stream info (duration, resolution, codec, fps, bitrate) from completed job response
  - `get_transcoder_client()` — `@lru_cache` singleton

- **`config_mapping.py`** — Maps app config → Transcoder API params:
  - Resolution string → height pixels
  - CRF → approximate bitrate (Transcoder API uses bitrate, not CRF)
  - Audio format → codec settings (AAC, MP3)
  - Preset → H.264 profile mapping

### 2.2 Database changes (`libs/database.py`)

- Add `TRANSCODING = "transcoding"` to `MediaJobStatus` enum (new state: Transcoder API job submitted, awaiting completion)
- Add `update_media_job_transcoder(job_id, transcoder_job_name, phase)` — stores job reference for polling
- Add `get_transcoding_media_jobs(limit)` — queries status=TRANSCODING

### 2.3 Unified worker: `workers/unified_worker.py`

Merges `media_worker.py` and `ai_worker.py` into one polling loop:

```
poll cycle:
  1. _check_transcoding_jobs()    # poll Transcoder API for in-flight media jobs
  2. _process_pending_media_jobs() # submit new media jobs to Transcoder API (PENDING → TRANSCODING)
  3. _process_pending_image_jobs() # Gemini image adaptation (same as current ai_worker)
  4. _process_pending_scene_jobs() # Gemini scene analysis (modified: no local chunking)
  sleep(poll_interval)
```

**Media job flow becomes non-blocking:**
- Submit Transcoder job → status = TRANSCODING → return to poll loop
- Next cycle: check status → if SUCCEEDED: extract metadata + update results → COMPLETED

**Scene job chunking via Transcoder API:**
- Submit chunking job with EditAtoms → blocking wait with poll loop for completion
- Build chunks list from Transcoder output paths
- Pass GCS URIs to scene processor (no local files)

### 2.4 Scene processor updates

**`libs/scene_processing/sequential.py`** and **`parallel.py`**:
- Remove `storage.download_file()` calls — chunks are already in GCS
- Remove local file cleanup in `finally` blocks
- Pass `gcs_path` to `analyzer.analyze_chunk()` (already supported: `scene_analyzer.py:157-159`)
- Make `media_path` parameter optional (default `None`) in `SceneAnalyzer.analyze_chunk()`

### 2.5 Config changes (`config.py`)

Add:
- `transcoder_location: str = "asia-south1"` (must match GCS bucket region)
- `transcoder_job_timeout_seconds: int = 600`

### 2.6 API schema updates (`api/models/schemas.py`, `api/routes/media.py`)

- Add `TRANSCODING` to recognized job statuses
- Update `get_media_presets()` — remove FFmpeg-specific presets (ultrafast/fast/etc.), keep resolution/CRF/audio options
- Add optional `transcoder_job_name` field to `MediaJobResponse`

### 2.7 Dependency changes (`requirements.txt`)

```diff
- ffmpeg-python==0.2.0
+ google-cloud-video-transcoder>=1.0.0
```

### 2.8 New `Dockerfile.worker` (replaces both worker Dockerfiles)

```dockerfile
FROM python:3.9-slim
# NO ffmpeg install — saves ~200-300MB
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY config.py libs/ workers/ ./
CMD ["python", "workers/unified_worker.py"]
```

### 2.9 Files to delete

- `libs/video_processing/` — entire directory (metadata.py, compressor.py, chunker.py, audio.py, manifest.py)
- `libs/media_processor/` — entire directory (processor.py)
- `workers/media_worker.py`, `workers/ai_worker.py`
- `Dockerfile.media-worker`, `Dockerfile.ai-worker`

---

## Epic 3: Deployment Updates

### 3.1 `deploy.sh` — 2 services instead of 4

```
./deploy.sh [api|worker|all] [--skip-checks] [--skip-push]
```

- Remove `frontend`, `media-worker`, `ai-worker` options
- Add `worker` option (replaces `workers`)
- Remove frontend deployment section (baked into API image)
- Remove CORS update step (no longer needed)
- Replace sections 3+4 (two workers) with single unified worker deployment
- Add `TRANSCODER_LOCATION` to `BACKEND_ENVS`
- Update summary output (2 services)

### 3.2 GCP setup prerequisites

- Enable Transcoder API: `gcloud services enable transcoder.googleapis.com`
- Grant worker service account `roles/transcoder.admin`
- Ensure Transcoder API location matches GCS bucket region
- After migration: delete old Cloud Run services (`gcloud run services delete`)

### 3.3 Update `.env.example` and `CLAUDE.md`

---

## Verification

1. **Local frontend dev**: `cd frontend && npm run dev` → Vite on :3000 proxies `/api` to :8000
2. **Production-like local**: `cd frontend && npm run build` then `python api/main.py` → SPA + API on :8000
3. **Media job**: Create media job → verify Transcoder API job submitted → poll until COMPLETED → check GCS outputs
4. **Scene analysis**: Create scene job → verify chunking via Transcoder API → Gemini receives GCS URIs → results saved
5. **Image adaptation**: Create image job → Gemini processes → results in GCS
6. **Run existing tests**: `pytest` (update mocks for Transcoder API)
7. **Docker build**: `docker build -f Dockerfile.api .` — verify multi-stage build includes frontend dist
8. **Deploy**: `./deploy.sh all` → 2 Cloud Run services running
