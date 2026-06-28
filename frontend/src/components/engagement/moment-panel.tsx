import { useMemo } from 'react'
import { MessageSquare, MapPin } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn, formatDuration } from '@/lib/utils'
import type { InfluenceEntity } from '@/lib/engagement-influence'
import {
  type SceneSummary,
  type Cue,
  sceneAt,
  entitiesAt,
  nearestScore,
  nearestCue,
  emotionColor,
  entityColor,
  sentimentClass,
} from '@/lib/engagement-moment'

interface Props {
  timestamp: number | null
  points?: [number, number][]
  overallAvg?: number
  scenes?: SceneSummary[]
  entities?: InfluenceEntity[]
  cues?: Cue[]
  selected: Set<string>
  onToggleEntity: (name: string) => void
  onOpenDialog: () => void
}

/**
 * "At this moment" — the connective tissue of the page. Everything here is
 * derived from the shared playhead `timestamp`, so scene, rating, characters,
 * emotions and dialog always describe the same instant.
 */
export function MomentPanel({
  timestamp,
  points,
  overallAvg,
  scenes,
  entities,
  cues,
  selected,
  onToggleEntity,
  onOpenDialog,
}: Props) {
  const t = timestamp
  const scene = useMemo(() => (t == null ? undefined : sceneAt(scenes || [], t)), [scenes, t])
  const present = useMemo(() => entitiesAt(entities, t ?? -1), [entities, t])
  const score = t == null ? undefined : nearestScore(points, t)
  const cue = useMemo(() => (t == null ? undefined : nearestCue(cues, t)), [cues, t])

  const deltaPct =
    score !== undefined && overallAvg !== undefined && overallAvg > 0
      ? ((score - overallAvg) / overallAvg) * 100
      : undefined

  if (t == null) {
    return (
      <div className="flex h-full min-h-[12rem] flex-col items-center justify-center rounded-lg border border-dashed bg-muted/20 p-6 text-center">
        <p className="text-sm font-medium">At this moment</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Press play, or click the timeline / any card to inspect a moment — this
          panel and every section will follow.
        </p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col gap-3 rounded-lg border bg-background p-4">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm text-muted-foreground">{formatDuration(t)}</span>
        {score !== undefined && (
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm">rating {score.toFixed(2)}</span>
            {deltaPct !== undefined && (
              <Badge
                className={cn('tabular-nums', deltaPct >= 0 ? 'bg-green-600' : 'bg-red-600')}
              >
                {deltaPct >= 0 ? '+' : ''}
                {deltaPct.toFixed(0)}%
              </Badge>
            )}
          </div>
        )}
      </div>

      {scene && (
        <div>
          {scene.title && <p className="text-sm font-semibold leading-tight">{scene.title}</p>}
          <p className="mt-0.5 text-sm leading-snug text-muted-foreground">{scene.summary}</p>
          {scene.location && (
            <span className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground">
              <MapPin className="h-3 w-3" />
              {scene.location}
            </span>
          )}
        </div>
      )}

      {present.characters.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            On screen
          </p>
          <div className="flex flex-wrap gap-1.5">
            {present.characters.map((c) => (
              <button
                key={c.name}
                onClick={() => onToggleEntity(c.name)}
                className={cn(
                  'flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs transition-colors',
                  selected.has(c.name)
                    ? 'border-primary/40 bg-primary/10 text-foreground'
                    : 'hover:bg-muted/50'
                )}
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: entityColor(c.name, c.kind) }}
                />
                {c.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {present.emotions.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Mood
          </p>
          <div className="flex flex-wrap gap-1.5">
            {present.emotions.map((e) => (
              <button
                key={e.name}
                onClick={() => onToggleEntity(e.name)}
                className="flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs capitalize transition-colors hover:bg-muted/50"
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: emotionColor(e.name) }}
                />
                {e.name}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-auto">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Dialog
          </p>
          <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={onOpenDialog}>
            <MessageSquare className="mr-1 h-3 w-3" />
            More
          </Button>
        </div>
        {cue ? (
          <p className={cn('mt-1 text-sm leading-snug', sentimentClass(cue.sentiment))}>
            {cue.speaker && <span className="font-semibold">{cue.speaker}: </span>}
            {cue.text}
          </p>
        ) : (
          <p className="mt-1 text-xs text-muted-foreground">No dialog near this moment.</p>
        )}
      </div>
    </div>
  )
}
