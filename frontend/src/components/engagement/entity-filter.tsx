import { useMemo } from 'react'
import { Users, Sparkles, MapPin, Box, Heart } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { entityColor, withAlpha } from '@/lib/engagement-moment'

export interface EngagementEntity {
  name: string
  kind: string
  appearances: { start_sec: number; end_sec: number }[]
  mention_count: number
}

interface EntityFilterProps {
  entities: EngagementEntity[]
  /** Currently selected entity names (any kind). */
  selected: Set<string>
  onToggle: (name: string) => void
  /** Optional: average score to compare selection against. */
  overallAvg?: number
  selectionAvg?: number
}

const KIND_ICONS: Record<string, typeof Users> = {
  character: Users,
  emotion: Heart,
  event: Sparkles,
  location: MapPin,
  object: Box,
}

export function EntityFilter({
  entities,
  selected,
  onToggle,
  overallAvg,
  selectionAvg,
}: EntityFilterProps) {
  const sorted = useMemo(
    () => [...entities].sort((a, b) => b.mention_count - a.mention_count).slice(0, 30),
    [entities]
  )

  if (sorted.length === 0) return null

  const deltaPct =
    overallAvg !== undefined && selectionAvg !== undefined && overallAvg > 0
      ? ((selectionAvg - overallAvg) / overallAvg) * 100
      : null

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-1.5">
        {sorted.map((e) => {
          const Icon = KIND_ICONS[e.kind] || Users
          const isOn = selected.has(e.name)
          const color = entityColor(e.name, e.kind)
          return (
            <button
              key={`${e.kind}-${e.name}`}
              onClick={() => onToggle(e.name)}
              className={cn(
                'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors',
                isOn
                  ? 'text-foreground'
                  : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
              )}
              style={
                isOn
                  ? { borderColor: color, backgroundColor: withAlpha(color, 0.16), boxShadow: `inset 0 0 0 1px ${color}` }
                  : undefined
              }
              title={`${e.kind} · ${e.mention_count} mentions`}
            >
              <span
                className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: color }}
              />
              <Icon className="h-3 w-3" />
              <span className="max-w-[160px] truncate">{e.name}</span>
              <span className="rounded-full bg-muted/70 px-1 text-[10px] tabular-nums">
                {e.mention_count}
              </span>
            </button>
          )
        })}
      </div>

      {selected.size > 0 && deltaPct !== null && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/30 px-3 py-2 text-sm">
          <span className="text-muted-foreground">
            Avg engagement during selected:
          </span>
          <span className="font-mono font-semibold">
            {selectionAvg?.toFixed(3)}
          </span>
          <Badge
            variant={deltaPct >= 0 ? 'default' : 'destructive'}
            className={cn(
              'tabular-nums',
              deltaPct >= 0 ? 'bg-green-600' : ''
            )}
          >
            {deltaPct >= 0 ? '+' : ''}
            {deltaPct.toFixed(1)}% vs overall
          </Badge>
          <span className="text-xs text-muted-foreground">
            (overall: {overallAvg?.toFixed(3)})
          </span>
        </div>
      )}
    </div>
  )
}
