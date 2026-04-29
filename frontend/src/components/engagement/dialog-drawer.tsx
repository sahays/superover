import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { engagementApi } from '@/lib/api-client'
import { formatDuration, cn } from '@/lib/utils'

interface DialogDrawerProps {
  jobId: string
  /** When non-null, drawer opens centered on this timestamp. */
  activeTimestamp: number | null
  onClose: () => void
}

const CONTEXT_BEFORE = 5
const CONTEXT_AFTER = 5

export function DialogDrawer({ jobId, activeTimestamp, onClose }: DialogDrawerProps) {
  const open = activeTimestamp !== null

  const { data: cues, isLoading } = useQuery({
    queryKey: ['engagement-cues', jobId],
    queryFn: () => engagementApi.getCues(jobId),
    enabled: open,
    staleTime: 60_000,
  })

  // Find the cue whose range contains activeTimestamp (or the nearest preceding cue),
  // then take ±N cues of context around it.
  const window = useMemo(() => {
    if (!cues || activeTimestamp === null) return null
    if (cues.length === 0) return { active: -1, slice: [] }

    let activeIdx = cues.findIndex(
      (c) => activeTimestamp >= c.start_sec && activeTimestamp <= c.end_sec
    )
    if (activeIdx === -1) {
      // No exact hit — take the cue with the closest start time.
      let closest = 0
      let closestDelta = Math.abs(cues[0].start_sec - activeTimestamp)
      for (let i = 1; i < cues.length; i++) {
        const delta = Math.abs(cues[i].start_sec - activeTimestamp)
        if (delta < closestDelta) {
          closest = i
          closestDelta = delta
        }
      }
      activeIdx = closest
    }
    const start = Math.max(0, activeIdx - CONTEXT_BEFORE)
    const end = Math.min(cues.length, activeIdx + CONTEXT_AFTER + 1)
    return { active: activeIdx, slice: cues.slice(start, end), startIdx: start }
  }, [cues, activeTimestamp])

  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-full max-w-md">
        <SheetHeader>
          <SheetTitle>
            Dialog around {activeTimestamp !== null ? formatDuration(activeTimestamp) : ''}
          </SheetTitle>
          <SheetDescription>
            What was on screen at that moment, plus surrounding context.
          </SheetDescription>
        </SheetHeader>

        <div className="mt-4 flex-1 space-y-2 overflow-y-auto pr-1">
          {isLoading && (
            <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading cues…
            </div>
          )}

          {!isLoading && (!window || window.slice.length === 0) && (
            <div className="py-12 text-center text-sm text-muted-foreground">
              No dialog cues recorded for this job.
            </div>
          )}

          {window?.slice.map((cue, i) => {
            const absIdx = (window.startIdx ?? 0) + i
            const isActive = absIdx === window.active
            return (
              <div
                key={`${cue.start_sec}-${i}`}
                className={cn(
                  'rounded-lg border px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'border-primary/50 bg-primary/5'
                    : 'border-border bg-background'
                )}
              >
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="font-mono">
                    {formatDuration(cue.start_sec)}–{formatDuration(cue.end_sec)}
                  </span>
                  {cue.kind && cue.kind !== 'dialogue' && (
                    <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] uppercase">
                      {cue.kind}
                    </span>
                  )}
                  {cue.speaker && (
                    <span className="font-medium text-foreground">{cue.speaker}</span>
                  )}
                </div>
                <p className="mt-1 leading-relaxed">{cue.text}</p>
              </div>
            )
          })}
        </div>
      </SheetContent>
    </Sheet>
  )
}
