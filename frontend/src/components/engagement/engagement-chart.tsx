import { useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { EngagementExtremum } from '@/lib/types'
import { formatDuration } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const LINE_COLORS = [
  'hsl(220 90% 56%)',
  'hsl(280 70% 55%)',
  'hsl(30 90% 55%)',
  'hsl(160 70% 40%)',
  'hsl(340 75% 55%)',
  'hsl(200 75% 45%)',
]

interface HighlightRange {
  start: number
  end: number
  label?: string
}

interface EngagementChartProps {
  /** Multi-metric series; the first key is treated as primary (gets the smoothed overlay + peak/valley dots). */
  metrics: Record<string, [number, number][]>
  primaryMetric?: string
  peaks: EngagementExtremum[]
  valleys: EngagementExtremum[]
  /** Translucent bands drawn over the chart — used for entity-filter chips. */
  highlightRanges?: HighlightRange[]
  /** Click handler for any data point — used by the dialog drawer. */
  onPointSelect?: (timestampSec: number) => void
}

export function EngagementChart({
  metrics,
  primaryMetric,
  peaks,
  valleys,
  highlightRanges = [],
  onPointSelect,
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
                  tick={{ fontSize: 11, fill: color }}
                  stroke={color}
                  domain={['auto', 'auto']}
                  className="text-muted-foreground"
                />
              )
            })}
            <Tooltip
              labelFormatter={(label) => `t = ${formatDuration(Number(label))}`}
              contentStyle={{
                backgroundColor: 'hsl(var(--background))',
                border: '1px solid hsl(var(--border))',
                borderRadius: 8,
                fontSize: 12,
              }}
            />

            {/* Highlight bands for selected entity ranges (anchored to primary axis). */}
            {highlightRanges.map((r, i) => (
              <ReferenceArea
                key={`hr-${i}`}
                yAxisId={primary}
                x1={r.start}
                x2={r.end}
                fill="hsl(142 71% 45%)"
                fillOpacity={0.12}
                stroke="hsl(142 71% 45%)"
                strokeOpacity={0.3}
                ifOverflow="extendDomain"
              />
            ))}

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
    </div>
  )
}
