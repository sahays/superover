/**
 * Client-side engagement-influence deltas, mirroring the backend
 * `compute_entity_deltas` in libs/engagement/recommendations.py.
 *
 * For each entity (character / emotion / event), compute the average primary
 * BARC score during its appearance ranges vs the overall average. Entities with
 * too few in-range samples are dropped (delta too noisy to be actionable).
 */

export interface EntityAppearance {
  start_sec: number
  end_sec: number
}

export interface InfluenceEntity {
  name: string
  kind: string
  appearances: EntityAppearance[]
  mention_count: number
  avg_intensity?: number | null
}

export interface EntityDelta {
  name: string
  kind: string
  deltaPct: number
  avgDuring: number
  sampleSize: number
  coverageSec: number
}

export function computeEntityDeltas(
  entities: InfluenceEntity[] | undefined,
  points: [number, number][] | undefined,
  minSampleSize = 2
): EntityDelta[] {
  if (!entities?.length || !points?.length) return []

  const overall = points.reduce((sum, [, s]) => sum + s, 0) / points.length
  if (overall === 0) return []

  const out: EntityDelta[] = []
  for (const ent of entities) {
    if (!ent.appearances?.length) continue
    const during = points.filter(([t]) =>
      ent.appearances.some((r) => t >= r.start_sec && t <= r.end_sec)
    )
    if (during.length < minSampleSize) continue
    const avgDuring = during.reduce((sum, [, s]) => sum + s, 0) / during.length
    const coverageSec = ent.appearances.reduce((sum, r) => sum + (r.end_sec - r.start_sec), 0)
    out.push({
      name: ent.name,
      kind: ent.kind,
      deltaPct: ((avgDuring - overall) / overall) * 100,
      avgDuring,
      sampleSize: during.length,
      coverageSec,
    })
  }

  // Strongest absolute movers first.
  return out.sort((a, b) => Math.abs(b.deltaPct) - Math.abs(a.deltaPct))
}
