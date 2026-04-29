import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { TrendingUp, TrendingDown, ArrowRight, Sparkles } from 'lucide-react'
import { formatDuration, cn } from '@/lib/utils'

export interface Recommendation {
  recommendation: string
  rationale: string
  expected_lift: 'low' | 'medium' | 'high'
  evidence?: {
    entity?: string
    delta_pct?: number
    sample_size?: number
    anchor_timestamps?: number[]
  }
}

export interface MinuteCallout {
  minute_start_sec: number
  minute_end_sec: number
  what_happened: string
  why_it_dipped: string
  alternative: string
}

export interface RecommendationsPayload {
  headline?: string
  do_more_of?: Recommendation[]
  do_less_of?: Recommendation[]
  per_minute_callouts?: MinuteCallout[]
}

interface Props {
  data: RecommendationsPayload
  onAnchorClick?: (timestamp: number) => void
}

const LIFT_CLASSES: Record<string, string> = {
  high: 'bg-green-600',
  medium: 'bg-yellow-600',
  low: 'bg-slate-500',
}

export function RecommendationsPanel({ data, onAnchorClick }: Props) {
  const moreOf = data.do_more_of || []
  const lessOf = data.do_less_of || []
  const minutes = data.per_minute_callouts || []

  if (
    !data.headline &&
    moreOf.length === 0 &&
    lessOf.length === 0 &&
    minutes.length === 0
  ) {
    return null
  }

  return (
    <Card className="border-primary/20">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <CardTitle className="text-lg">Recommendations</CardTitle>
        </div>
        {data.headline && (
          <CardDescription className="text-base font-medium text-foreground">
            {data.headline}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-6">
        {(moreOf.length > 0 || lessOf.length > 0) && (
          <div className="grid gap-4 lg:grid-cols-2">
            <RecommendationColumn
              title="Do more of"
              icon={TrendingUp}
              accent="text-green-600"
              borderClass="border-green-600/30"
              items={moreOf}
              onAnchorClick={onAnchorClick}
            />
            <RecommendationColumn
              title="Do less of"
              icon={TrendingDown}
              accent="text-red-600"
              borderClass="border-red-600/30"
              items={lessOf}
              onAnchorClick={onAnchorClick}
            />
          </div>
        )}

        {minutes.length > 0 && (
          <div>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Per-minute callouts
            </h3>
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {minutes.map((m, i) => (
                <button
                  key={i}
                  onClick={() => onAnchorClick?.(m.minute_start_sec)}
                  className="group rounded-lg border bg-background p-3 text-left transition-colors hover:border-primary/40 hover:bg-muted/40"
                >
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="font-mono text-xs text-muted-foreground">
                      {formatDuration(m.minute_start_sec)}–
                      {formatDuration(m.minute_end_sec)}
                    </span>
                    <ArrowRight className="h-3 w-3 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                  </div>
                  <p className="text-sm font-medium leading-tight">
                    {m.what_happened}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Why it dipped: {m.why_it_dipped}
                  </p>
                  <p className="mt-1.5 text-xs">
                    <span className="font-semibold text-primary">Try: </span>
                    {m.alternative}
                  </p>
                </button>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

interface ColumnProps {
  title: string
  icon: typeof TrendingUp
  accent: string
  borderClass: string
  items: Recommendation[]
  onAnchorClick?: (t: number) => void
}

function RecommendationColumn({
  title,
  icon: Icon,
  accent,
  borderClass,
  items,
  onAnchorClick,
}: ColumnProps) {
  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <Icon className={cn('h-4 w-4', accent)} />
        <h3 className="font-semibold">{title}</h3>
        <span className="text-xs text-muted-foreground">({items.length})</span>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing notable.</p>
      ) : (
        <div className="space-y-3">
          {items.map((rec, i) => (
            <div key={i} className={cn('rounded-lg border p-3', borderClass)}>
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium leading-snug">{rec.recommendation}</p>
                <Badge
                  className={cn('shrink-0 text-[10px]', LIFT_CLASSES[rec.expected_lift])}
                >
                  {rec.expected_lift}
                </Badge>
              </div>
              {rec.rationale && (
                <p className="mt-2 text-xs text-muted-foreground">{rec.rationale}</p>
              )}
              {rec.evidence && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
                  {rec.evidence.entity && (
                    <span className="rounded bg-muted px-1.5 py-0.5 font-medium">
                      {rec.evidence.entity}
                    </span>
                  )}
                  {rec.evidence.delta_pct !== undefined && (
                    <span
                      className={cn(
                        'font-mono tabular-nums',
                        rec.evidence.delta_pct >= 0 ? 'text-green-600' : 'text-red-600'
                      )}
                    >
                      {rec.evidence.delta_pct >= 0 ? '+' : ''}
                      {rec.evidence.delta_pct.toFixed(1)}%
                    </span>
                  )}
                  {rec.evidence.sample_size !== undefined && (
                    <span className="text-muted-foreground">
                      n={rec.evidence.sample_size}
                    </span>
                  )}
                </div>
              )}
              {rec.evidence?.anchor_timestamps && rec.evidence.anchor_timestamps.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {rec.evidence.anchor_timestamps.map((t, j) => (
                    <button
                      key={j}
                      onClick={() => onAnchorClick?.(t)}
                      className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
                    >
                      {formatDuration(t)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
