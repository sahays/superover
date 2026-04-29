# Story 1: Analytics + Grounded Recommendations

## Context

The first cut of Engagement Analysis ships top-3 peaks + valleys against a single TVR series. Producers want more depth: **multi-metric overlay** (BARC also gives Impressions and Reach, currently discarded), **click-a-point to read the dialog at that second**, and **filter the chart by character or event** to see how engagement moves around them. They also want a **grounded recommendations engine** — concrete "do more of / do less of" guidance with per-minute callouts, derived from observed deltas in this video, not generic content advice.

A check of the user's existing scene-analysis result was free-text SRT, but the user has agreed to change the scene-analysis output schema to better serve downstream analytics. So instead of mining subtitles, we **define a richer structured schema for `scene_analysis`** containing entities, events, dialog cues, and narrative beats. Engagement analysis reads it directly, with regex mining preserved as a fallback for older free-text jobs.

## User-confirmed choices

- Build all three: **multi-metric chart**, **click-a-point dialog drawer**, **character/event filter chips**.
- **Structured `scene_analysis` schema** as the upstream source of truth. Subtitle mining survives only as a fallback.
- **Recommendations engine** with grounded "to take rating from X to Y, do more of / less of X" guidance + per-minute callouts.

---

## Backend

### 0. New `scene_analysis` response schema (upstream)

**File:** `libs/scene_processing/scene_analysis_schema.py` (new) — single source of truth for the JSON shape Gemini returns for any scene_analysis prompt.

The schema below uses only Gemini-compatible JSON-Schema keywords: `type`, `properties`, `required`, `items`, `enum`, `description`, `minItems`, `maxItems`, `nullable`. No `#` comments (invalid JSON), no `$ref`, no `additionalProperties`, no `oneOf`/`anyOf`. `appearances` uses an array-of-objects rather than array-of-array because Gemini's structured-output parser is reliably strict on the former.

```python
SCENE_ANALYSIS_SCHEMA = {
    "type": "object",
    "required": ["summary", "cues", "entities", "events"],
    "properties": {
        "summary": {
            "type": "string",
            "description": "One-paragraph synopsis of what happens in this chunk (3-6 sentences)."
        },
        "cues": {
            "type": "array",
            "description": "Dialog, narration, and timed audio events covering the chunk.",
            "items": {
                "type": "object",
                "required": ["start_sec", "end_sec", "text", "kind"],
                "properties": {
                    "start_sec": {
                        "type": "number",
                        "description": "Absolute start time in seconds from t=0 of the full source video."
                    },
                    "end_sec": {
                        "type": "number",
                        "description": "Absolute end time in seconds from t=0 of the full source video."
                    },
                    "speaker": {
                        "type": "string",
                        "description": "Speaking character's name for dialogue cues. Empty string if narration, music, sfx, silence, or unknown."
                    },
                    "text": {
                        "type": "string",
                        "description": "Verbatim line for dialogue/narration; bracketed description for non-verbal cues (e.g. '[dramatic orchestral swell]')."
                    },
                    "kind": {
                        "type": "string",
                        "enum": ["dialogue", "narration", "music", "sfx", "silence"]
                    }
                }
            }
        },
        "entities": {
            "type": "array",
            "description": "Named characters, props, and locations that appear in this chunk.",
            "items": {
                "type": "object",
                "required": ["name", "kind", "appearances"],
                "properties": {
                    "name": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": ["character", "object", "location"]
                    },
                    "description": {
                        "type": "string",
                        "description": "Short identifying phrase (e.g. 'young protagonist, blue tunic')."
                    },
                    "appearances": {
                        "type": "array",
                        "description": "Contiguous on-screen ranges within this chunk. Merge ranges within 2 seconds of each other.",
                        "items": {
                            "type": "object",
                            "required": ["start_sec", "end_sec"],
                            "properties": {
                                "start_sec": {"type": "number"},
                                "end_sec": {"type": "number"}
                            }
                        }
                    }
                }
            }
        },
        "events": {
            "type": "array",
            "description": "Tagged narrative or audio events with absolute time bounds.",
            "items": {
                "type": "object",
                "required": ["tag", "start_sec", "end_sec"],
                "properties": {
                    "tag": {
                        "type": "string",
                        "enum": [
                            "action", "dialogue_heavy", "music", "comedy",
                            "tension", "exposition", "climax", "transition",
                            "song", "fight", "romance", "emotional"
                        ]
                    },
                    "description": {
                        "type": "string",
                        "description": "One short sentence anchoring the event in concrete content."
                    },
                    "start_sec": {"type": "number"},
                    "end_sec": {"type": "number"}
                }
            }
        },
        "narrative_beats": {
            "type": "array",
            "description": "Optional. Emit only when a classical story beat clearly starts in this chunk.",
            "items": {
                "type": "object",
                "required": ["beat", "start_sec", "end_sec"],
                "properties": {
                    "beat": {
                        "type": "string",
                        "enum": [
                            "setup", "inciting_incident", "rising_action",
                            "climax", "falling_action", "resolution"
                        ]
                    },
                    "start_sec": {"type": "number"},
                    "end_sec": {"type": "number"}
                }
            }
        }
    }
}
```

**Gemini compatibility checklist** (verified against `google-genai` SDK with Vertex backend, the same path `libs/gemini/scene_analyzer.py` already uses):
- Only types `string`, `number`, `integer`, `boolean`, `array`, `object` appear.
- All `enum` values are strings.
- No `$ref`, `$schema`, `additionalProperties`, `patternProperties`, `oneOf`, `anyOf`, `allOf` — the parser rejects them.
- No comments anywhere; the file is a Python dict literal that is also valid JSON when serialized.
- Optional fields are simply omitted from the parent's `required` array (e.g. `speaker`, `description`, `narrative_beats`). Gemini's parser does not need `nullable: true` here because the model is told in the prompt to return `""` rather than `null` for missing speakers.

Wiring:
- Seed this schema as a `category_schemas` row keyed `scene_analysis` (existing collection — `libs/db/category_schemas.py`). New scene_analysis prompts created via the prompt UI auto-pick it up because the prompt's `response_schema` is resolved through the category default when not explicitly set.
- **All times are absolute video seconds** (not chunk-local) — the existing scene_processing flow knows the chunk start, so it injects "this chunk covers [chunk_start, chunk_end]; emit absolute timestamps in that range" into the prompt template wrapper.
- The seeded prompt text gets a small append: explicit guidance that the response schema is binding and that entities must be re-listed in every chunk where they appear (so timeline merging across chunks works deterministically).

A migration helper extends `seed_default_prompts` to also seed this schema at startup.

#### 0a. The seeded prompt text

A new default prompt of `type = "scene_analysis"` is seeded alongside the schema. The system already wraps every scene-analysis call with chunk metadata (so the model knows the chunk's absolute time range). The prompt itself focuses on **what to extract** and **how to format the response**.

```
You are an expert video scene analyst. You will be shown a chunk of a longer
video. Produce ONE structured JSON object matching the supplied response
schema. No prose outside the JSON.

## Time conventions
- Every timestamp you emit MUST be in absolute video seconds (i.e. measured
  from t=0 of the FULL source video, not from the start of this chunk).
- This chunk covers seconds {chunk_start_sec} to {chunk_end_sec} of the source
  video. All start_sec / end_sec / appearance values you emit must lie inside
  this range.
- Use floats with one decimal where useful (e.g. 73.5). Never invent times for
  things you did not directly observe.

## summary
- One paragraph (3–6 sentences) describing what happens in this chunk in plain
  language. Mention the named characters who actually appear and the dominant
  events (action, dialog, song, etc.).

## cues  (dialog + narration + audio events with timing)
- Emit one cue per discrete spoken line, voiceover, song segment, music cue,
  sound effect, or stretch of pure silence (>3s).
- `text` should be the spoken/sung line verbatim where possible. For non-verbal
  cues, describe in brackets, e.g. "[dramatic orchestral swell]",
  "[crowd cheers]", "[silence]".
- `kind` must be one of: dialogue, narration, music, sfx, silence.
- `speaker` is the on-screen character's name for dialogue cues; "" otherwise.
  Do NOT guess speaker names — leave "" if you are not confident.
- Cues should not overlap. Adjacent cues should be contiguous (next cue's
  start_sec ≈ previous cue's end_sec).

## entities  (recurring named participants and important props/locations)
- List every named character who speaks or is clearly identified on screen in
  this chunk. Also list named locations and meaningful props that recur.
- `kind` must be one of: character, object, location.
- `appearances` is an array of [start_sec, end_sec] pairs giving every
  contiguous range in this chunk where the entity is on screen (or, for an
  off-screen but actively-named character, every range where they are being
  addressed / discussed). Merge ranges that are within 2 seconds of each other.
- `description` is one short sentence (e.g. "young protagonist, blue tunic").
- IMPORTANT: re-list every entity each chunk where it appears. Downstream
  merging unions appearances across chunks; an entity omitted in a chunk is
  treated as absent there.

## events  (tagged narrative / audio events)
- A timed segment with a categorical tag describing what kind of beat it is.
- `tag` must be one of: action, dialogue_heavy, music, comedy, tension,
  exposition, climax, transition, song, fight, romance, emotional.
- A single chunk typically yields 2–10 events. Events may overlap (e.g. a song
  during a fight). Use the tightest time bounds you can.
- `description` is one short sentence anchoring the event in concrete content
  (e.g. "Ganesh confronts the demon king as the score swells").

## narrative_beats  (optional, only when clearly observable)
- If this chunk contains the start of a classical story beat (setup, inciting
  incident, rising action, climax, falling action, resolution), emit it.
- Skip if uncertain. Better to omit than to mislabel.

## Quality bar
- Be specific. "A character speaks" is useless; name them, quote a line.
- Do not invent. If audio is unclear, say "[unclear dialogue]" and lower your
  confidence rather than guessing names.
- Cover the entire chunk. A chunk with no cues or no events is almost always a
  signal you missed something — re-watch and try again.
- Output strictly valid JSON conforming to the response schema. No markdown
  fences, no commentary.
```

The `{chunk_start_sec}` / `{chunk_end_sec}` placeholders are filled by the existing scene-processing wrapper in `libs/scene_processing/sequential.py` (or `parallel.py`) before the call to Gemini — the wrapper already knows each chunk's bounds from the manifest.

### 1. Multi-metric BARC parser

**File:** `libs/engagement/barc_parser.py`

Today the parser picks one score column. Extend `BarcSeries` to also carry every numeric column it can find:

```python
@dataclass
class BarcSeries:
    points: List[Tuple[float, float]]            # primary metric (existing)
    time_column: str
    score_column: str
    metrics: Dict[str, List[Tuple[float, float]]]  # NEW: every numeric column
    anchor_offset_sec: float = 0.0
```

- Detect numeric columns by attempting `_parse_score` on the first non-header row of each column; keep those that parse.
- Apply the same anchor offset to all metric series.
- Order: primary first, then `tvr → impressions → reach → engagement → score → rating`, then any remaining numeric column alphabetically.

Tests in `tests/libs/test_barc_parser.py`:
- `test_real_barc_returns_all_metrics` — feeds the user's real header row, asserts `metrics` contains TVR (%), Impressions ('000s), Reach ('000s), each anchored to t=0.

### 2. Entity / cue extraction

**New file:** `libs/engagement/scene_extract.py`

Single entry point; tries structured-output first, falls back to mining.

```python
@dataclass
class Cue:
    start_sec: float
    end_sec: float
    text: str
    kind: str          # dialogue / narration / music / sfx / silence
    speaker: str = ""

@dataclass
class Entity:
    name: str
    kind: str          # character / object / location / event
    appearances: List[Tuple[float, float]]
    mention_count: int

def extract_from_scene_results(results: List[Dict]) -> Tuple[List[Cue], List[Entity]]:
    """Walk every chunk's result_data. If `cues` / `entities` / `events` keys
    exist (structured schema §0), merge them across chunks. Otherwise fall back
    to subtitle mining of raw_text."""
```

**Structured path** (preferred):
- Concatenate `cues` from every chunk; sort by `start_sec`; dedupe overlapping cues.
- Group `entities` across chunks by normalized name + kind; union their `appearances`; merge ranges within 5s of each other.
- Treat `events` as entities with `kind="event"`, where `appearances = [(start_sec, end_sec)]` per occurrence.

**Fallback path** (regex mining of `raw_text` SRT):
- Parse SRT cue blocks (`\d+\n(time --> time)\n(text)`).
- Bracketed cues (`[dramatic music]`) → events grouped by normalized content.
- Proper-noun tokens appearing ≥ 3 times → character entities; appearance range = the cues mentioning them.

Tests in `tests/libs/test_scene_extract.py`:
- `test_structured_path_merges_entities_across_chunks`
- `test_structured_path_orders_cues`
- `test_fallback_to_srt_when_no_structured_keys`
- `test_fallback_extracts_bracketed_events`
- `test_fallback_filters_below_min_mentions`
- `test_merges_close_appearances`

### 3. Worker: persist new artifacts

**File:** `workers/unified_worker.py` — `_process_engagement_job`

Add to the upload step (alongside `timeseries.json`):

- `gs://results/engagement/{job_id}/timeseries.json` — now the full `metrics` dict, not just primary points.
- `gs://results/engagement/{job_id}/entities.json` — output of `extract_from_scene_results` (structured path or fallback).
- `gs://results/engagement/{job_id}/cues.json` — merged dialog/narration/music cues with `[start, end, text, kind, speaker]`. Powers the click-a-point drawer.

The Firestore `results` payload gets `entities_gcs_path` and `cues_gcs_path` siblings to the existing `timeseries_gcs_path`.

### 4. API additions

**File:** `api/routes/engagement.py`

- `GET /api/engagement/jobs/{job_id}/timeseries` — already exists; just returns the broader `metrics` dict now. Response schema gains `metrics: Dict[str, List[[float, float]]]` while keeping `points` for back-compat.
- `GET /api/engagement/jobs/{job_id}/entities` — returns the merged entity list.
- `GET /api/engagement/jobs/{job_id}/cues` — returns the merged dialog/narration cues for the click-a-point drawer.

Implementation reuses the existing GCS-fetch helper pattern from `get_engagement_timeseries`. Each endpoint just downloads its JSON file from GCS.

Tests in `tests/api/test_engagement.py`:
- `test_timeseries_returns_all_metrics`
- `test_entities_endpoint`
- `test_cues_endpoint`
- `test_cues_404_when_source_missing`

---

## Frontend

### 5. Multi-metric chart

**File:** `frontend/src/components/engagement/engagement-chart.tsx`

- Accept `metrics: Record<string, [number, number][]>` instead of just `points`.
- Render one `<Line>` per metric with distinct colors (Tailwind palette).
- Add a small legend row above the chart with toggle pills (uses existing `Badge` + `useState`); clicking a pill toggles that line's visibility.
- Add a **smoothed overlay** for the primary metric: client-side rolling-window average (window = 10% of points, min 5). Toggleable.
- Keep the peak/valley `<ReferenceDot>`s on the primary line.

### 6. Click-a-point context drawer

**Files:**
- `frontend/src/components/ui/sheet.tsx` (new — install shadcn `sheet`).
- `frontend/src/components/engagement/dialog-drawer.tsx` — uses `Sheet` to render subtitle cues around a selected timestamp.
- Update `engagement-chart.tsx` to call an `onPointSelect(t: number)` prop on chart click (use Recharts `onClick` event from `LineChart`).

The drawer fetches `engagementApi.getCues(jobId)` once (cached by React Query) then displays the cue at `t` ± 5 cues of context, with timestamps, speaker labels, and the active cue highlighted.

### 7. Entity filter chips

**File:** `frontend/src/components/engagement/entity-filter.tsx` (new)

- Row of clickable `Badge`s above the chart: `[Ganesh]  [Shiva]  [music]  [laughter]`. Each chip shows mention count.
- Selecting one or more chips:
  - Adds `<ReferenceArea>` shaded bands on the chart at each entity's appearance ranges (translucent green for active selection).
  - Updates a small stat strip below the chart: "Avg engagement during selected entity scenes: X (vs overall avg Y)" — computed client-side from `metrics.tvr` ∩ appearance ranges.

### 8. Results page wiring

**File:** `frontend/src/pages/EngagementResultsPage.tsx`

Compose the new pieces (recommendations panel sits above the chart):

1. `<RecommendationsPanel ... onAnchorClick={setActiveT} />`
2. `<EntityFilter ... onSelect={setSelectedEntities} />`
3. `<EngagementChart metrics={...} highlightRanges={selectedRanges} onPointSelect={setActiveT} />`
4. `<DialogDrawer open={activeT !== null} t={activeT} />`
5. Existing peak/valley cards stay below.

`engagementApi` (in `frontend/src/lib/api-client.ts`) gains:
```ts
engagementApi.getEntities(jobId)
engagementApi.getCues(jobId)
engagementApi.getRecommendations(jobId)
```

### 9. Recommendations engine — backend

**Why a separate step**: peak/valley explanations tell the producer *why moments worked*, but not *what to change for the whole show*. The recommendations engine looks across the entire video and answers "to lift the average rating from X to Y, do more of these things and less of these others."

#### 9a. Deterministic stats (worker)

**New file:** `libs/engagement/recommendations.py`

```python
def compute_entity_deltas(metrics, entities) -> List[EntityDelta]:
    """For each entity, avg engagement during its appearance ranges vs overall avg.
    Returns delta_pct, sample_size (mention_count), and the underlying numbers."""

def find_low_minutes(timeseries, k=5) -> List[MinuteSlice]:
    """Bucket the primary metric into 60s windows; return the k worst-performing
    windows with their start/end and avg score."""

def find_high_minutes(timeseries, k=5) -> List[MinuteSlice]:
    """Mirror of find_low_minutes — used as positive examples for the LLM."""
```

These are pure functions, fully unit-testable, no Gemini.

#### 9b. Gemini synthesis (worker)

**File:** `libs/gemini/engagement_analyzer.py` — extend `EngagementAnalyzer` with a `recommend(...)` method that takes:
- The deterministic deltas (top-10 positive entities, top-10 negative)
- The k worst minutes + k best minutes (with the cues that span them)
- The original peak/valley contexts already used for explanations
- The video's overall average score and the producer's ambition (default: top quartile of observed minutes)

…and returns a structured response:

```python
{
  "do_more_of": [
    {"recommendation": str, "rationale": str, "evidence": {
        "entity": str | None,
        "delta_pct": float,
        "sample_size": int,
        "anchor_timestamps": [float],
    }, "expected_lift": "low" | "medium" | "high"}
  ],
  "do_less_of": [ ... same shape ... ],
  "per_minute_callouts": [
    {"minute_start": float, "minute_end": float, "what_happened": str,
     "why_it_dipped": str, "alternative": str}
  ],
  "headline": str,   # one sentence summary, e.g. "Lean into Ganesh + Shiva arcs; cut prolonged silence sequences in minutes 12–18."
}
```

The prompt instructs Gemini to **only cite entities/events present in the supplied stats**, never invent. Recommendations must reference specific deltas and timestamps.

#### 9c. Worker integration

In `_process_engagement_job`:
1. After extracting entities and computing peaks/valleys, call `compute_entity_deltas` and `find_low_minutes` / `find_high_minutes`.
2. Call `engagement_analyzer.explain(...)` (existing) — keeps peak/valley explanations.
3. Call `engagement_analyzer.recommend(...)` (new) with deltas + minute buckets + cues for those minutes.
4. Persist both: `results.recommendations` (Firestore) and `gs://results/engagement/{job_id}/recommendations.json` (mirror for cheap re-fetch).

Two Gemini calls per job total — explain peaks/valleys, then synthesize recommendations. ~$0.05–$0.15 per job depending on length.

#### 9d. Tests

- `tests/libs/test_recommendations.py` — covers `compute_entity_deltas` (effect-size math, small-N filtering), `find_low_minutes` (boundary cases, ties), `find_high_minutes`. Pure functions.
- `tests/workers/test_engagement_job.py` — extend the happy-path test to assert `recommend` was called with the expected stats shape and that `results.recommendations` lands in Firestore.

### 10. Recommendations endpoint

**File:** `api/routes/engagement.py`

`GET /api/engagement/jobs/{job_id}/recommendations` — returns the recommendations JSON. Mirrors the timeseries / entities / cues pattern (download from GCS, return parsed JSON).

### 11. Recommendations panel — frontend

**New file:** `frontend/src/components/engagement/recommendations-panel.tsx`

Layout:
- A prominent **headline** strip at the top of the panel (the one-sentence summary from Gemini).
- Two columns of cards: **Do more of** (green accent) and **Do less of** (red accent). Each card:
  - Recommendation (1–2 sentences)
  - Rationale + evidence chip (e.g. `Ganesh · +12% · 14 mentions`)
  - Expected lift badge (`low` / `medium` / `high`)
  - Anchor timestamps render as clickable mini-pills — clicking jumps the chart to that point and opens the dialog drawer (reuses §6).
- Below: **Per-minute callouts** as a horizontally-scrollable list of small cards, each pinned to its minute window.

**File:** `frontend/src/lib/api-client.ts` — add `engagementApi.getRecommendations(jobId)`.
**File:** `frontend/src/lib/types.ts` — Zod schemas for `Recommendation`, `MinuteCallout`, `RecommendationsResponse`.

### 12. Types

**File:** `frontend/src/lib/types.ts`

Add Zod schemas: `EngagementEntity`, `Cue`, `Recommendation`, `MinuteCallout`, `RecommendationsResponse`. Extend `engagementResultsSchema` with `entities_gcs_path`, `cues_gcs_path`, and `recommendations_gcs_path` (all optional for back-compat with older completed jobs).

---

## Files to modify or create

**New (backend):** `libs/scene_processing/scene_analysis_schema.py`, `libs/engagement/scene_extract.py`, `libs/engagement/recommendations.py`, `tests/libs/test_scene_extract.py`, `tests/libs/test_recommendations.py`.

**Modified (backend):** `libs/engagement/barc_parser.py`, `libs/gemini/engagement_analyzer.py`, `libs/engagement/prompts.py`, `libs/db/category_schemas.py` (seed scene_analysis schema), `libs/db/client.py` (extend `seed_default_prompts` to also seed schemas), `workers/unified_worker.py`, `api/routes/engagement.py`, `api/models/schemas/engagement.py`, `tests/libs/test_barc_parser.py`, `tests/api/test_engagement.py`, `tests/workers/test_engagement_job.py`.

**New (frontend):** `frontend/src/components/ui/sheet.tsx` (shadcn), `frontend/src/components/engagement/dialog-drawer.tsx`, `frontend/src/components/engagement/entity-filter.tsx`, `frontend/src/components/engagement/recommendations-panel.tsx`.

**Modified (frontend):** `frontend/src/components/engagement/engagement-chart.tsx`, `frontend/src/pages/EngagementResultsPage.tsx`, `frontend/src/lib/api-client.ts`, `frontend/src/lib/types.ts`.

## Existing primitives reused

- BARC normalization helpers (`_normalize_header`, `_parse_score`, `_parse_timestamp`) in `libs/engagement/barc_parser.py`.
- GCS upload + signed-URL pattern from `_process_engagement_job`.
- Status polling pattern: `useQuery({refetchInterval: 3000})`.
- Recharts `<ReferenceArea>` / `<ReferenceDot>` (already used for peak/valley markers).
- shadcn `Badge`, `Card`, `Sheet`.

## Backwards compatibility

- **New scene_analysis runs** (after the schema is seeded) auto-emit structured JSON. Engagement runs against them use the structured path.
- **Existing scene_analysis jobs** that produced free-text or SRT (like the user's current sample) still work — `scene_extract.extract_from_scene_results` falls through to subtitle mining. Recommendations quality is lower in this path because tags/events are coarser.
- The previously-failed engagement job (`7523e563`) needs no migration. New jobs write the additional GCS artifacts. Frontend uses optional chaining + graceful empty states for any older completed engagement jobs missing the new fields.

## Acceptance criteria

- A scene_analysis job created after this story ships emits JSON matching `SCENE_ANALYSIS_SCHEMA` (entities, cues, events, summary, narrative beats).
- An engagement job created against such a scene_analysis job persists `timeseries.json` (multi-metric), `entities.json`, `cues.json`, and `recommendations.json` to GCS, with sibling paths in Firestore `results`.
- Engagement Results page shows: multi-metric chart, entity chips, recommendations panel, click-a-point drawer.
- Recommendations only cite entities/events present in the deterministic stats; expected_lift, evidence, anchor_timestamps are populated for each card.
- Engagement runs against older free-text scene_analysis jobs still complete (with degraded recommendations quality).

## Edge cases

- BARC CSV missing TVR — falls back to Impressions/Reach as primary, multi-metric chart still renders the available lines.
- Scene job has 0 entities (e.g. heavy dialog with no recurring proper nouns) — entity chip row hides, recommendations skip entity-based cards and rely on event tags + minute callouts.
- Per-minute bucketing produces fewer than k buckets (very short clip) — return whatever buckets exist; recommendations prompt is told to scale advice accordingly.
- Gemini returns recommendations citing entities not in the supplied stats — drop them client-side and log; do not render fabricated advice.
- Older completed engagement jobs that lack `entities_gcs_path` etc. — page renders with the old peak/valley layout only; new sections show graceful empty states.

## Functional tests

- Unit: `pytest tests/libs/ tests/api/test_engagement.py tests/workers/test_engagement_job.py` — existing 29 + ~10 new tests pass.
- Integration: trigger a worker tick against a fixture scene_analysis job emitting structured JSON; assert all four GCS artifacts are written and Firestore `results` carries the sibling paths.
- E2E: run a fresh scene_analysis job → engagement job → load `/engagement/:jobId`; verify multi-metric toggling, entity chip filter shading, click-a-point drawer with active-cue highlight, recommendations panel headline + cards + per-minute callouts, anchor-timestamp pills opening the drawer at the right point.
- Pre-deploy: `./pre-deploy.sh` (ruff, ESLint, vite build) green; then `./deploy.sh all`.
