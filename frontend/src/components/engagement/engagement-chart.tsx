import { useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { EngagementExtremum } from '@/lib/types'
import { formatDuration } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { sceneAt, emotionColor, type SceneSummary } from '@/lib/engagement-moment'

const MARKER_TYPE_LABELS: Record<string, string> = {
  hook: 'Hook',
  reveal: 'Reveal',
  twist: 'Twist',
  cliffhanger: 'Cliffhanger',
  punchline: 'Punchline',
  action_peak: 'Action peak',
  emotional_peak: 'Emotional peak',
  song: 'Song',
}

const LINE_COLORS = [
  'hsl(220 90% 56%)',
  'hsl(280 70% 55%)',
  'hsl(30 90% 55%)',
  'hsl(160 70% 40%)',
  'hsl(340 75% 55%)',
  'hsl(200 75% 45%)',
]

// Horizontal insets so the story ribbon lines up with the chart's plot area.
const AXIS_W = 44 // primary YAxis width
const RIGHT_M = 24 // chart margin.right

interface HighlightRange {
  start: number
  end: number
  label?: string
  /** Per-entity color so the band matches its filter chip. Falls back to green. */
  color?: string
}

export interface EmotionBand {
  start_sec: number
  end_sec: number
  label: string
  intensity?: number | null
}

export interface TimelineMarker {
  start_sec: number
  type: string
  label: string
  kind: 'moment' | 'beat'
}

const MARKER_GLYPHS: Record<string, string> = {
  hook: '⚓',
  reveal: '◆',
  twist: '↺',
  cliffhanger: '⚡',
  punchline: '★',
  action_peak: '▲',
  emotional_peak: '♥',
  song: '♪',
}

function markerGlyph(m: TimelineMarker): string {
  if (m.kind === 'beat') return '▮'
  return MARKER_GLYPHS[m.type] || '•'
}

interface EngagementChartProps {
  /** Multi-metric series; the first key is treated as primary (gets the smoothed overlay + peak/valley dots). */
  metrics: Record<string, [number, number][]>
  primaryMetric?: string
  peaks: EngagementExtremum[]
  valleys: EngagementExtremum[]
  /** Translucent bands drawn over the chart — used for entity-filter chips. */
  highlightRanges?: HighlightRange[]
  /** Per-chunk scene summaries — shown in the hover tooltip. */
  scenes?: SceneSummary[]
  /** Vertical playhead marker (shared timestamp across the page). */
  playhead?: number | null
  /** Horizontal baselines on the primary axis. */
  overallAvg?: number
  targetAvg?: number
  /** Emotion segments for the story ribbon. */
  emotionBands?: EmotionBand[]
  /** Key-moment / story-beat ticks for the story ribbon. */
  markers?: TimelineMarker[]
  /** Entity names currently selected — ribbon bands for these get a stronger outline. */
  selectedNames?: Set<string>
  /** Click handler for any data point — used by the dialog drawer. */
  onPointSelect?: (timestampSec: number) => void
  /** Toggle an emotion's selection by clicking its ribbon band (highlights its spans on the chart). */
  onBandToggle?: (name: string) => void
}

export function EngagementChart({
  metrics,
  primaryMetric,
  peaks,
  valleys,
  highlightRanges = [],
  scenes = [],
  playhead,
  overallAvg,
  targetAvg,
  emotionBands = [],
  markers = [],
  selectedNames,
  onPointSelect,
  onBandToggle,
}: EngagementChartProps) {
  const metricKeys = useMemo(() => Object.keys(metrics), [metrics])
  const primary = primaryMetric || metricKeys[0]

  // Per-metric visibility toggle. Default: every metric visible.
  const [visible, setVisible] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(metricKeys.map((k) => [k, true]))
  )
  const [showSmoothed, setShowSmoothed] = useState(false)

  // Keep visibility in sync if metrics change at runtime (e.g. async load).
  useEffect(() => {
    setVisible((prev) => {
      const next = { ...prev }
      let changed = false
      for (const k of metricKeys) {
        if (!(k in next)) {
          next[k] = true
          changed = true
        }
      }
      return changed ? next : prev
    })
  }, [metricKeys])

  // Build a unified row-per-timestamp dataset. Different metrics may have
  // different sample timestamps; we union them and use null for gaps.
  const data = useMemo(() => {
    const byTime = new Map<number, Record<string, number | null>>()
    for (const [name, points] of Object.entries(metrics)) {
      for (const [t, s] of points) {
        const row = byTime.get(t) || ({ t } as Record<string, number | null>)
        row[name] = s
        byTime.set(t, row)
      }
    }
    return [...byTime.values()].sort((a, b) => (a.t as number) - (b.t as number))
  }, [metrics])

  // Smoothed overlay for the primary metric: rolling-average over ~10% of points.
  const smoothed = useMemo(() => {
    if (!showSmoothed || !primary) return null
    const points = metrics[primary] || []
    if (points.length < 5) return null
    const window = Math.max(5, Math.floor(points.length * 0.1))
    return points.map(([t], i) => {
      const start = Math.max(0, i - Math.floor(window / 2))
      const end = Math.min(points.length, start + window)
      const slice = points.slice(start, end)
      const avg = slice.reduce((sum, [, v]) => sum + v, 0) / slice.length
      return { t, smoothed: avg }
    })
  }, [showSmoothed, primary, metrics])

  const mergedData = useMemo(() => {
    if (!smoothed) return data
    const smoothedByTime = new Map(smoothed.map((p) => [p.t, p.smoothed]))
    return data.map((row) => ({
      ...row,
      __smoothed: smoothedByTime.get(row.t as number) ?? null,
    }))
  }, [data, smoothed])

  // Time domain for positioning the story ribbon under the plot.
  const [timeMin, timeMax] = useMemo<[number, number]>(() => {
    if (data.length === 0) return [0, 1]
    return [data[0].t as number, data[data.length - 1].t as number]
  }, [data])
  const span = timeMax - timeMin || 1
  const pctLeft = (t: number) => `${Math.min(100, Math.max(0, ((t - timeMin) / span) * 100))}%`
  const pctWidth = (a: number, b: number) => `${Math.max(0, ((b - a) / span) * 100)}%`

  // Distinct emotions present (for the Mood legend), first-seen order.
  const distinctEmotions = useMemo(() => {
    const seen = new Set<string>()
    const out: string[] = []
    for (const b of emotionBands) {
      const k = b.label.trim().toLowerCase()
      if (!seen.has(k)) {
        seen.add(k)
        out.push(b.label)
      }
    }
    return out
  }, [emotionBands])

  // Distinct key-moment types present (for the Moments glyph legend).
  const momentTypes = useMemo(() => {
    const seen = new Set<string>()
    const out: string[] = []
    for (const m of markers) {
      if (m.kind === 'beat') continue
      if (!seen.has(m.type)) {
        seen.add(m.type)
        out.push(m.type)
      }
    }
    return out
  }, [markers])

  if (data.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center rounded-lg border bg-muted/30 text-sm text-muted-foreground">
        No timeseries data available
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {/* Toggle pills */}
      <div className="flex flex-wrap items-center gap-2">
        {metricKeys.map((name, i) => {
          const active = !!visible[name]
          const color = LINE_COLORS[i % LINE_COLORS.length]
          return (
            <button
              key={name}
              onClick={() => setVisible((prev) => ({ ...prev, [name]: !prev[name] }))}
              className={cn(
                'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors',
                active
                  ? 'border-foreground/20 bg-muted text-foreground'
                  : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
              )}
            >
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: active ? color : 'transparent', borderColor: color, borderWidth: 1, borderStyle: 'solid' }}
              />
              {name}
            </button>
          )
        })}
        <button
          onClick={() => setShowSmoothed((s) => !s)}
          className={cn(
            'rounded-full border px-2.5 py-1 text-xs font-medium transition-colors',
            showSmoothed
              ? 'border-foreground/20 bg-muted text-foreground'
              : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
          )}
        >
          {showSmoothed ? 'Smoothed (on)' : 'Smoothed (off)'}
        </button>
        {highlightRanges.length > 0 && (
          <Badge variant="outline" className="ml-auto text-xs">
            {highlightRanges.length} range{highlightRanges.length > 1 ? 's' : ''} highlighted
          </Badge>
        )}
      </div>

      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={mergedData}
            margin={{ top: 12, right: 24, left: 0, bottom: 8 }}
            onClick={(state: any) => {
              if (!onPointSelect) return
              const t = state?.activeLabel
              if (typeof t === 'number') onPointSelect(t)
            }}
          >
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="t"
              type="number"
              domain={[timeMin, timeMax]}
              tickFormatter={(v) => formatDuration(Number(v))}
              tick={{ fontSize: 11 }}
              stroke="currentColor"
              className="text-muted-foreground"
            />
            {/* Per-metric Y axes so a 0-1 TVR and a 0-500 Impressions can share the chart.
                Only the primary metric shows its labels; the rest are hidden but still
                auto-scale their lines so each fills the vertical space. */}
            {metricKeys.map((name, i) => {
              const color = LINE_COLORS[i % LINE_COLORS.length]
              const isPrimary = name === primary
              return (
                <YAxis
                  key={`y-${name}`}
                  yAxisId={name}
                  orientation={isPrimary ? 'left' : 'right'}
                  hide={!isPrimary}
                  width={isPrimary ? AXIS_W : 0}
                  tick={{ fontSize: 11, fill: color }}
                  stroke={color}
                  domain={['auto', 'auto']}
                  className="text-muted-foreground"
                />
              )
            })}
            <Tooltip
              cursor={{ stroke: 'hsl(var(--border))' }}
              content={({ active, payload, label }: any) => {
                if (!active || !payload || payload.length === 0) return null
                const t = Number(label)
                const scene = scenes.length > 0 ? sceneAt(scenes, t) : undefined
                return (
                  <div className="max-w-xs rounded-lg border bg-background p-2.5 text-xs shadow-md">
                    <div className="mb-1 font-mono text-muted-foreground">
                      t = {formatDuration(t)}
                    </div>
                    {payload
                      .filter((p: any) => p.dataKey !== '__smoothed' && p.value != null)
                      .map((p: any) => (
                        <div key={p.dataKey} className="flex items-center justify-between gap-3">
                          <span style={{ color: p.color }}>{p.name}</span>
                          <span className="font-mono tabular-nums">{Number(p.value).toFixed(2)}</span>
                        </div>
                      ))}
                    {scene && (
                      <p className="mt-2 border-t pt-2 leading-snug text-foreground">
                        {scene.summary}
                      </p>
                    )}
                  </div>
                )
              }}
            />

            {/* Baselines: overall average + producer target, on the primary axis. */}
            {overallAvg !== undefined && (
              <ReferenceLine
                yAxisId={primary}
                y={overallAvg}
                stroke="hsl(var(--muted-foreground))"
                strokeDasharray="5 4"
                strokeOpacity={0.7}
                label={{ value: 'avg', position: 'insideTopLeft', fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
              />
            )}
            {targetAvg !== undefined && (
              <ReferenceLine
                yAxisId={primary}
                y={targetAvg}
                stroke="hsl(142 71% 45%)"
                strokeDasharray="2 4"
                strokeOpacity={0.8}
                label={{ value: 'target', position: 'insideBottomLeft', fontSize: 10, fill: 'hsl(142 71% 40%)' }}
              />
            )}

            {/* Shared playhead — the spine of the page. */}
            {playhead !== null && playhead !== undefined && (
              <ReferenceLine
                yAxisId={primary}
                x={playhead}
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                ifOverflow="extendDomain"
              />
            )}

            {/* Highlight bands for selected entity ranges (anchored to primary axis).
                Each band is colored to match its filter chip / ribbon band. */}
            {highlightRanges.map((r, i) => {
              const c = r.color || 'hsl(142 71% 45%)'
              return (
                <ReferenceArea
                  key={`hr-${i}`}
                  yAxisId={primary}
                  x1={r.start}
                  x2={r.end}
                  fill={c}
                  fillOpacity={0.28}
                  stroke={c}
                  strokeOpacity={0.9}
                  strokeWidth={1.5}
                  ifOverflow="extendDomain"
                />
              )
            })}

            {/* Lines per metric — each on its own Y axis so scales don't collapse. */}
            {metricKeys.map((name, i) => {
              if (!visible[name]) return null
              const color = LINE_COLORS[i % LINE_COLORS.length]
              return (
                <Line
                  key={name}
                  yAxisId={name}
                  type="monotone"
                  dataKey={name}
                  name={name}
                  stroke={color}
                  strokeWidth={name === primary ? 2 : 1.5}
                  dot={false}
                  connectNulls
                  isAnimationActive={false}
                />
              )
            })}

            {/* Smoothed overlay on the primary axis */}
            {showSmoothed && (
              <Line
                yAxisId={primary}
                type="monotone"
                dataKey="__smoothed"
                name="smoothed"
                stroke="hsl(220 90% 56%)"
                strokeOpacity={0.5}
                strokeDasharray="4 3"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            )}

            {/* Peak / valley markers anchored to the primary axis */}
            {peaks.map((p) => (
              <ReferenceDot
                key={`peak-${p.rank}`}
                yAxisId={primary}
                x={p.timestamp_sec}
                y={p.score ?? 0}
                r={6}
                fill="hsl(142 71% 45%)"
                stroke="white"
                strokeWidth={2}
                ifOverflow="extendDomain"
              />
            ))}
            {valleys.map((v) => (
              <ReferenceDot
                key={`valley-${v.rank}`}
                yAxisId={primary}
                x={v.timestamp_sec}
                y={v.score ?? 0}
                r={6}
                fill="hsl(0 84% 60%)"
                stroke="white"
                strokeWidth={2}
                ifOverflow="extendDomain"
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Story ribbon — emotion bands + key-moment/beat ticks, aligned to the
          plot's time axis via matching horizontal insets. */}
      {(emotionBands.length > 0 || markers.length > 0) && (
        <div style={{ marginLeft: AXIS_W, marginRight: RIGHT_M }} className="select-none space-y-2">
          {emotionBands.length > 0 && (
            <div>
              <p className="mb-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                Mood
              </p>
              <div className="relative h-5 w-full overflow-hidden rounded bg-muted/30">
                {emotionBands.map((b, i) => {
                  const isSel = selectedNames?.has(b.label)
                  const widthPct = ((b.end_sec - b.start_sec) / span) * 100
                  return (
                    <button
                      key={`em-${i}`}
                      onClick={() => {
                        onBandToggle?.(b.label)
                        onPointSelect?.(b.start_sec)
                      }}
                      title={`${b.label} · ${formatDuration(b.start_sec)}–${formatDuration(b.end_sec)}`}
                      className={cn(
                        'absolute top-0 flex h-full items-center overflow-hidden px-1 text-[9px] font-medium capitalize leading-none text-white/95 transition-all hover:opacity-100',
                        isSel && 'z-10 ring-1 ring-inset ring-foreground'
                      )}
                      style={{
                        left: pctLeft(b.start_sec),
                        width: pctWidth(b.start_sec, b.end_sec),
                        backgroundColor: emotionColor(b.label),
                        opacity: 0.4 + 0.5 * (b.intensity ?? 0.5),
                      }}
                    >
                      {widthPct > 7 && <span className="truncate">{b.label}</span>}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
          {markers.length > 0 && (
            <div>
              <p className="mb-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                Moments
              </p>
              <div className="relative h-4 w-full">
                {markers.map((m, i) => (
                  <button
                    key={`mk-${i}`}
                    onClick={() => onPointSelect?.(m.start_sec)}
                    title={`${m.label} · ${formatDuration(m.start_sec)}`}
                    className={cn(
                      'absolute top-0 -translate-x-1/2 text-[11px] leading-none',
                      m.kind === 'beat' ? 'text-muted-foreground/70' : 'text-foreground/80 hover:text-primary'
                    )}
                    style={{ left: pctLeft(m.start_sec) }}
                  >
                    {markerGlyph(m)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Legend — decodes the ribbon colors (emotions) and glyphs (key moments). */}
          {(distinctEmotions.length > 0 || momentTypes.length > 0) && (
            <div className="flex flex-wrap gap-x-3 gap-y-1 pt-0.5 text-[10px] text-muted-foreground">
              {distinctEmotions.map((label) => (
                <span key={`leg-em-${label}`} className="inline-flex items-center gap-1 capitalize">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: emotionColor(label) }}
                  />
                  {label}
                </span>
              ))}
              {momentTypes.map((type) => (
                <span key={`leg-mk-${type}`} className="inline-flex items-center gap-1">
                  <span className="text-foreground/80">{MARKER_GLYPHS[type] || '•'}</span>
                  {MARKER_TYPE_LABELS[type] || type}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
