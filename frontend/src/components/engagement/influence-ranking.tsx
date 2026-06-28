import { cn } from '@/lib/utils'
import type { EntityDelta } from '@/lib/engagement-influence'
import { entityColor } from '@/lib/engagement-moment'

interface Props {
  title: string
  description?: string
  items: EntityDelta[]
  selected?: Set<string>
  /** Entities present at the current playhead — badged "on now". */
  activeNames?: Set<string>
  onToggle?: (name: string) => void
  emptyText?: string
}

/**
 * Ranked list of entities by their influence on the BARC rating (delta vs
 * overall average). Green = lifts the rating, red = drags it down. Bars are
 * scaled to the largest absolute delta in the set.
 */
export function InfluenceRanking({
  title,
  description,
  items,
  selected,
  activeNames,
  onToggle,
  emptyText = 'Not enough data to rank.',
}: Props) {
  const maxAbs = items.reduce((m, i) => Math.max(m, Math.abs(i.deltaPct)), 0) || 1

  return (
    <div>
      <h3 className="text-sm font-semibold">{title}</h3>
      {description && <p className="mb-2 text-xs text-muted-foreground">{description}</p>}
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{emptyText}</p>
      ) : (
        <div className="space-y-1.5">
          {items.map((item) => {
            const positive = item.deltaPct >= 0
            const widthPct = (Math.abs(item.deltaPct) / maxAbs) * 100
            const isSelected = selected?.has(item.name)
            const isActive = activeNames?.has(item.name)
            return (
              <button
                key={`${item.kind}-${item.name}`}
                onClick={() => onToggle?.(item.name)}
                className={cn(
                  'flex w-full items-center gap-3 rounded-md border px-2.5 py-1.5 text-left transition-colors',
                  isSelected ? 'border-primary/40 bg-muted/50' : 'hover:bg-muted/40',
                  isActive && 'ring-1 ring-primary/50'
                )}
              >
                <span className="flex w-32 shrink-0 items-center gap-1.5 truncate text-sm font-medium capitalize" title={item.name}>
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: entityColor(item.name, item.kind) }}
                    title={item.kind}
                  />
                  {isActive && (
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" title="on screen now" />
                  )}
                  <span className="truncate">{item.name}</span>
                </span>
                <span className="relative flex-1">
                  <span
                    className={cn('block h-2 rounded-full', positive ? 'bg-green-600' : 'bg-red-600')}
                    style={{ width: `${widthPct}%` }}
                  />
                </span>
                <span
                  className={cn(
                    'w-16 shrink-0 text-right font-mono text-xs tabular-nums',
                    positive ? 'text-green-600' : 'text-red-600'
                  )}
                >
                  {positive ? '+' : ''}
                  {item.deltaPct.toFixed(1)}%
                </span>
                <span className="w-10 shrink-0 text-right text-[10px] text-muted-foreground">
                  n={item.sampleSize}
                </span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
