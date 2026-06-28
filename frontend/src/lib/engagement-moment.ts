/**
 * Shared playhead-derivation helpers for the engagement detail page. All pure
 * functions of a single timestamp `t`, reused by the chart, the "At this moment"
 * panel, and the reactive tabs so every section agrees on what's happening now.
 */

import type { InfluenceEntity } from '@/lib/engagement-influence'

export interface SceneSummary {
  chunk_index?: number
  start_sec: number | null
  end_sec: number | null
  title?: string
  summary: string
  location?: string
}

export interface Cue {
  start_sec: number
  end_sec: number
  text: string
  kind: string
  speaker: string
  sentiment?: string
}

/** Find the scene whose [start,end) covers t; falls back to the last scene before t. */
export function sceneAt(scenes: SceneSummary[], t: number): SceneSummary | undefined {
  let fallback: SceneSummary | undefined
  for (const s of scenes) {
    if (s.start_sec == null) continue
    if (s.end_sec != null && t >= s.start_sec && t < s.end_sec) return s
    if (t >= s.start_sec) fallback = s
  }
  return fallback
}

/** Entities whose appearance ranges contain t, split by kind. */
export function entitiesAt(
  entities: InfluenceEntity[] | undefined,
  t: number
): { characters: InfluenceEntity[]; emotions: InfluenceEntity[]; events: InfluenceEntity[]; all: InfluenceEntity[] } {
  const all = (entities || []).filter((e) =>
    e.appearances?.some((r) => t >= r.start_sec && t <= r.end_sec)
  )
  return {
    characters: all.filter((e) => e.kind === 'character'),
    emotions: all.filter((e) => e.kind === 'emotion'),
    events: all.filter((e) => e.kind === 'event'),
    all,
  }
}

/** Names of entities active at t (for cross-highlighting the influence rows). */
export function activeEntityNames(entities: InfluenceEntity[] | undefined, t: number): Set<string> {
  return new Set(entitiesAt(entities, t).all.map((e) => e.name))
}

/** Nearest timeseries score to t (points assumed sorted by time). */
export function nearestScore(points: [number, number][] | undefined, t: number): number | undefined {
  if (!points?.length) return undefined
  let best = points[0]
  let bestDelta = Math.abs(points[0][0] - t)
  for (const p of points) {
    const d = Math.abs(p[0] - t)
    if (d < bestDelta) {
      best = p
      bestDelta = d
    }
  }
  return best[1]
}

/** Cue covering t, else the nearest by start time. */
export function nearestCue(cues: Cue[] | undefined, t: number): Cue | undefined {
  if (!cues?.length) return undefined
  const hit = cues.find((c) => t >= c.start_sec && t <= c.end_sec)
  if (hit) return hit
  let best = cues[0]
  let bestDelta = Math.abs(cues[0].start_sec - t)
  for (const c of cues) {
    const d = Math.abs(c.start_sec - t)
    if (d < bestDelta) {
      best = c
      bestDelta = d
    }
  }
  return best
}

/** Stable color per emotion label for ribbon bands + chips. */
const EMOTION_COLORS: Record<string, string> = {
  joy: 'hsl(45 90% 55%)',
  humor: 'hsl(50 95% 60%)',
  triumph: 'hsl(140 60% 45%)',
  romance: 'hsl(330 75% 60%)',
  calm: 'hsl(190 50% 55%)',
  neutral: 'hsl(220 10% 60%)',
  surprise: 'hsl(270 70% 60%)',
  suspense: 'hsl(25 85% 55%)',
  tension: 'hsl(15 80% 50%)',
  fear: 'hsl(265 45% 45%)',
  anger: 'hsl(0 75% 50%)',
  sadness: 'hsl(215 65% 55%)',
  disgust: 'hsl(95 40% 45%)',
}

const FALLBACK_EMOTION_COLORS = [
  'hsl(220 70% 55%)',
  'hsl(160 60% 45%)',
  'hsl(290 60% 55%)',
  'hsl(35 80% 55%)',
  'hsl(0 70% 55%)',
]

export function emotionColor(label: string): string {
  const key = label.trim().toLowerCase()
  if (EMOTION_COLORS[key]) return EMOTION_COLORS[key]
  // Deterministic fallback by label hash so unknown labels stay stable.
  let h = 0
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0
  return FALLBACK_EMOTION_COLORS[h % FALLBACK_EMOTION_COLORS.length]
}

/** Distinct hued palette for characters & other named entities. */
const CHARACTER_COLORS = [
  'hsl(220 75% 55%)',
  'hsl(160 60% 42%)',
  'hsl(280 60% 58%)',
  'hsl(35 85% 52%)',
  'hsl(0 70% 58%)',
  'hsl(195 70% 45%)',
  'hsl(320 60% 55%)',
  'hsl(95 45% 45%)',
  'hsl(255 55% 60%)',
  'hsl(15 75% 52%)',
  'hsl(175 55% 40%)',
  'hsl(245 70% 62%)',
]

function hashIndex(key: string, mod: number): number {
  let h = 0
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0
  return h % mod
}

/**
 * One stable color per entity, shared across filter pills, chart highlight bands,
 * the story ribbon, moment-panel chips, and influence rows. Emotions use the fixed
 * emotion palette; everything else hashes its name into a distinct character palette.
 */
export function entityColor(name: string, kind?: string): string {
  if (kind === 'emotion') return emotionColor(name)
  return CHARACTER_COLORS[hashIndex(name.trim().toLowerCase(), CHARACTER_COLORS.length)]
}

/**
 * Add an alpha channel to an `hsl(H S% L%)` color (CSS Color 4 `hsl(... / a)`).
 * Used for translucent fills (chart overlays, selected pills) that must still read
 * as the same hue as the solid swatch.
 */
export function withAlpha(color: string, alpha: number): string {
  return color.replace(/\)\s*$/, ` / ${alpha})`)
}

/** Sentiment → tailwind text color class for dialog tinting. */
export function sentimentClass(sentiment?: string): string {
  if (sentiment === 'positive') return 'text-green-600'
  if (sentiment === 'negative') return 'text-red-600'
  return 'text-foreground'
}
