import { useMemo } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { EngagementExtremum } from '@/lib/types'
import { formatDuration } from '@/lib/utils'

interface EngagementChartProps {
  points: [number, number][]
  peaks: EngagementExtremum[]
  valleys: EngagementExtremum[]
  scoreLabel?: string
}

export function EngagementChart({ points, peaks, valleys, scoreLabel = 'Engagement' }: EngagementChartProps) {
  const data = useMemo(
    () => points.map(([t, s]) => ({ t, s })),
    [points]
  )

  if (data.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center rounded-lg border bg-muted/30 text-sm text-muted-foreground">
        No timeseries data available
      </div>
    )
  }

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 12, right: 24, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis
            dataKey="t"
            tickFormatter={(v) => formatDuration(Number(v))}
            tick={{ fontSize: 11 }}
            stroke="currentColor"
            className="text-muted-foreground"
          />
          <YAxis
            tick={{ fontSize: 11 }}
            stroke="currentColor"
            className="text-muted-foreground"
          />
          <Tooltip
            labelFormatter={(label) => `t = ${formatDuration(Number(label))}`}
            formatter={(value) => [String(value), scoreLabel]}
            contentStyle={{
              backgroundColor: 'hsl(var(--background))',
              border: '1px solid hsl(var(--border))',
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Line
            type="monotone"
            dataKey="s"
            stroke="hsl(220 90% 56%)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          {peaks.map((p) => (
            <ReferenceDot
              key={`peak-${p.rank}`}
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
  )
}
