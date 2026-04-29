import { TrendingUp, TrendingDown } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { EngagementExtremum } from '@/lib/types'
import { formatDuration } from '@/lib/utils'

interface EngagementCardProps {
  item: EngagementExtremum
  kind: 'peak' | 'valley'
}

export function EngagementCard({ item, kind }: EngagementCardProps) {
  const isPeak = kind === 'peak'
  const Icon = isPeak ? TrendingUp : TrendingDown
  const accentClass = isPeak ? 'text-green-600' : 'text-red-600'
  const labelText = isPeak ? `Peak #${item.rank}` : `Valley #${item.rank}`

  const tags = [
    ...(item.key_actors || []).map((t) => ({ label: t, kind: 'actor' as const })),
    ...(item.key_events || []).map((t) => ({ label: t, kind: 'event' as const })),
    ...(item.key_objects || []).map((t) => ({ label: t, kind: 'object' as const })),
  ]

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <Icon className={`h-4 w-4 ${accentClass}`} />
            <CardTitle className="text-base">{labelText}</CardTitle>
          </div>
          <div className="text-right">
            <div className="font-mono text-sm">{formatDuration(item.timestamp_sec)}</div>
            {item.score !== null && item.score !== undefined && (
              <div className="text-xs text-muted-foreground font-mono">
                score {Number(item.score).toFixed(2)}
              </div>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {item.scene_summary && (
          <div>
            <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
              Scene
            </div>
            <p className="text-sm leading-relaxed">{item.scene_summary}</p>
          </div>
        )}
        {item.explanation && (
          <div>
            <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
              Why this {isPeak ? 'peaked' : 'dipped'}
            </div>
            <p className="text-sm leading-relaxed">{item.explanation}</p>
          </div>
        )}
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {tags.map((t, i) => (
              <Badge
                key={`${t.kind}-${i}`}
                variant="outline"
                className="text-xs"
                title={t.kind}
              >
                {t.label}
              </Badge>
            ))}
          </div>
        )}
        {item.chunk_index !== null && item.chunk_index !== undefined && (
          <div className="text-xs text-muted-foreground">
            Drawn from chunk #{item.chunk_index}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
