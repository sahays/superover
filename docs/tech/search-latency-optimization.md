# Conversation Search Latency Optimization (Avatar Mode)

**Date:** 2026-07-02
**Status:** Implemented and verified locally on the Bigtable backend. **Not yet deployed** — Cloud Run still runs the previous pipeline until the env flip described in [Rollout](#rollout--rollback).

## Intent

Avatar-mode conversation search (`/search/avatar`) felt slow: the user speaks, the avatar acks and small-talks, but result cards and narration trailed by several seconds. The goal was to cut end-to-end REST latency from ~4s to well under 1s without degrading result quality, keeping an instant rollback path.

## Baseline (measured from production logs)

`POST /api/search/videos` ran a strictly sequential pipeline. Per-stage timing from ~55 production queries (`scripts/fetch-logs.sh -f 'textPayload:"Search pipeline latency"'`):

| Stage | Median | Range | Share |
|---|---|---|---|
| Query interpreter (Gemini Flash LLM) | 0ms (fast-path ~75% of queries) | 0.2–2.5s when it ran | tail spikes |
| BigQuery `AI.SEARCH` | ~1.4s | 0.9–1.9s | ~35% |
| Curator (Gemini Flash LLM) | ~2.4s | 1.2–5.2s | ~55% |
| **Total REST** | **~4.0s** | 2.5–7s | |

Plus ~1.2s fixed client-side delay (`AUTO_STOP_MS` pause detection) before the pipeline fires.

Two structural observations drove the design:

1. **The curator's output was consumed by another LLM.** Its `response_text` existed only to be narrated by the Gemini Live avatar — an LLM writing prose for an LLM to paraphrase. The Live model can narrate from a structured list directly.
2. **BigQuery is a query engine, not a serving store.** The ~1.4s is mostly job overhead, a floor that no query tuning removes.

## Design

### 1. Remove the curator LLM from the request path (−~2.4s)

- `libs/search_ranking.py` ranks deterministically: dedupe to the best (lowest-distance) chunk per video, top-5 by distance, `clip` vs `full_video` from the chunk's timestamps, confidence from a linear distance ramp.
- **Relevance filtering** — the curator's real value (it returned 0 recs for chitchat like "Hi Jay, how are you?" despite 20 BQ rows) — is replaced by a display distance threshold: only rows with `distance < SEARCH_DISPLAY_MAX_DISTANCE` become cards.
- **Narration** moved to the avatar itself. The frontend (`avatar-search-panel.tsx`) builds a structured `[SEARCH_RESULTS]` list (title, reason, clip range, confidence) from `recommendations[]`; the rewritten phase-3 rules in `SEARCH_MODE_OVERLAY` (`libs/avatar_service.py`) make the Live model judge relevance and narrate only the strongest matches. `response_text` in the API response is now always empty (field kept for schema compatibility).
- `libs/gemini/search_curator.py` is unused but kept on disk during burn-in.

### 2. Replace BigQuery with Bigtable KNN (~1.4s → 20–50ms)

- `libs/bigtable/client.py` mirrors the BQ client's method surface and is selected by `SEARCH_BACKEND` (`bigquery` | `bigtable`) in `config.py` — a one-env-var rollback.
- Vector search via GoogleSQL `execute_query`: `COSINE_DISTANCE(TO_VECTOR32(d['embedding']), TO_VECTOR32(@qvec)) … ORDER BY distance LIMIT k`. Embeddings are stored as big-endian float32 bytes (the `TO_VECTOR32` encoding). Row key = `result_id`; owner/video scoping are SQL `WHERE` clauses (KNN is a full scan regardless, fine at this corpus size — 54 rows).
- Bigtable does not generate embeddings, so `libs/gemini/embeddings.py` calls the Gemini embeddings API explicitly: **`gemini-embedding-001` @ 768 dims**, `RETRIEVAL_DOCUMENT` at sync time / `RETRIEVAL_QUERY` at search time, re-normalized (truncated dims aren't unit-norm).
- Sync semantics change: embedding is synchronous, so `/search/sync` marks Firestore `ready` immediately (no `pending` → poll cycle as with BQ's async `AI.EMBED`).
- **Scene-level rows restore clip recommendations** (added same day): the curator used to localize clips semantically from `scenes[]`; deterministic ranking can't. Sync now writes one row per timed scene (key `result_id#s{i}`, text = genre + scene summary + people via `libs/scene_clips.py`, timestamps = scene start/end) alongside the whole-video row — KNN retrieves the specific moment and ranking emits `clip` recs naturally. Corpus went 54 → 468 rows; KNN stays ~50ms. Housekeeping (`get_synced_result_ids`, `delete_synced_result`) treats base+scene rows as one logical result.
- **Sync-time title/cast enrichment** (added same day): analyses label people by character ("Sonu"), never the actor, so actor-name queries had nothing to match on. One Gemini Flash call per video at sync (`libs/gemini/enrichment.py`) produces a "Title: … Cast: …" blurb, prepended to the embedding text of every row. Off the hot path — search latency unchanged. Fixed e.g. "Find Sunil Grover shows": Sunflower/United Kacche clips now top-3 at distance 0.29–0.31 (was 4th at 0.397).

### 3. Drop the interpreter LLM for text queries (kills the 0.2–2.5s tail)

`gemini-embedding-001` is multilingual, so on the Bigtable backend raw Hindi/mixed text embeds directly — no English-rewrite LLM. Audio input still goes through the interpreter (transcription). Verified: a Hindi query returned 5 correct thriller recommendations with zero LLM calls.

### 4. Regional embedding endpoint (found during verification)

The `global` Vertex endpoint gave erratic embedding latency (0.4–1.8s). The regional endpoint co-located with the service (`asia-south1`) is a stable ~200ms. New `embedding_region` setting, defaulting to `gcp_region`.

## Threshold calibration

Cosine distances are model-specific. With `gemini-embedding-001` on this corpus (`scripts/migrate_bq_to_bigtable.py --stats`):

- Genuine keyword-style queries ("political thrillers", "Zee 5 shows"): best matches **0.32–0.40**
- Mood-phrased queries ("I am heartbroken, can you suggest…", "cooking drama show"): best matches **0.40–0.43**
- Chitchat ("Hi Jay, how are you?"): nothing below **0.404** — the bands overlap, so no absolute threshold separates chitchat from mood queries.

→ `SEARCH_DISPLAY_MAX_DISTANCE=0.44` (production value) favors recall: mood-phrased queries get cards; chitchat may show a few loose cards, which is acceptable because the avatar Live model judges the `[SEARCH_RESULTS]` list itself and narrates "nothing fits" when appropriate. A stricter 0.40 gives zero-card chitchat at the cost of zero-card mood queries. The old BQ/text-embedding-005 space clusters at 0.95–1.12; if rolling back, use ~1.05. Recalibrate with `--stats` whenever the embedding model or corpus changes materially.

## Results (verified locally, Bigtable backend)

| | Before (prod logs) | After (local, warm) |
|---|---|---|
| Interpreter | 0–2.5s | 0ms (text) |
| Vector search | ~1.4s (BQ) | ~200ms embed + 20–50ms KNN |
| Curate/rank | ~2.4s (LLM) | ~2ms (deterministic) |
| **Total REST** | **~4.0s median** | **166–484ms** (~20× faster warm) |

Also verified: owner scoping on real data (`zee` sees zee+untagged only; same for `sony`), chitchat → 0 cards, Hindi → correct results, `SEARCH_BACKEND=bigquery` rollback path intact. 27 unit/API tests cover ranking, the Bigtable client (mocked), and the route.

## Migration runbook

Infra (one-time; done 2026-07-02 on `random-poc-479104`):

```bash
gcloud services enable bigtableadmin.googleapis.com bigtable.googleapis.com
gcloud bigtable instances create superover-search \
    --display-name="Superover Search" \
    --cluster-config=id=superover-search-c1,zone=asia-south1-a,nodes=1   # ~$475/month
python scripts/migrate_bq_to_bigtable.py --create-table
python scripts/migrate_bq_to_bigtable.py            # idempotent; --force to rewrite
python scripts/migrate_bq_to_bigtable.py --stats "political thrillers" "Zee 5 shows"
```

The migration re-embeds `text_content` for every BQ row — **vectors are not portable across embedding models**, so the BQ `AI.EMBED`/text-embedding-005 vectors are discarded. The BQ table is left untouched (rollback + re-migration source).

## Rollout / rollback

**Deployed to production 2026-07-02** (`superover-frontend-00166` code + `00167` config revision): `SEARCH_BACKEND=bigtable`, `SEARCH_DISPLAY_MAX_DISTANCE=0.44`. `deploy.sh` passes the search/embedding env vars from `.env` via `BACKEND_ENVS` (note: `--set-env-vars` replaces the service env wholesale — new settings must be added there). Verified live: 185–275ms totals on real queries, Devanagari Hindi with `interpret=0ms`, chitchat narrated away by the avatar.

Rollback options:
- Config-only: set `SEARCH_BACKEND=bigquery` (and threshold ~1.05) on the service — same code, old backend.
- Full: route traffic back to the pre-change revision, e.g. `gcloud run services update-traffic superover-frontend --region asia-south1 --to-revisions superover-frontend-00165-mgv=100`.

No data loss in either direction; the BQ table remains intact and re-syncable.

## Operational notes

- The sync `BigtableDataClient` runs a non-daemon event-loop thread — short-lived scripts must call `BigtableClient.close()` or they hang at exit (the API service never closes it).
- `google-auth` was upgraded to ≥2.55 in the venv; 2.48 crashed in the GCE-metadata fallback (`'Request' object has no attribute 'session'`).
- On the dev VM the user ADC file is expired; run scripts/server with `CLOUDSDK_CONFIG=<empty dir>` to force metadata-SA auth.
- Future scale note: Bigtable KNN here is exact (full scan). Fine for hundreds–thousands of rows; at much larger corpus sizes revisit (row-key prefix partitioning by owner, or a dedicated ANN service).
