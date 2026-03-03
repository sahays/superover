import { Button } from '@/components/ui/button'

interface ChunkDurationSelectorProps {
  chunkDuration: number
  onChunkDurationChange: (duration: number) => void
  mediaType: 'video' | 'audio'
  mediaDuration?: number
}

export function ChunkDurationSelector({
  chunkDuration,
  onChunkDurationChange,
  mediaType,
  mediaDuration,
}: ChunkDurationSelectorProps) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">
        Chunk Duration (seconds)
      </label>

      <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300">
        <p className="font-medium mb-1">Chunking splits your media into segments for analysis.</p>
        <p className="mb-1">Recommended:</p>
        <ul className="list-disc list-inside space-y-0.5 ml-2">
          <li>Audio &lt; 5 hours: No chunking (default)</li>
          <li>Video &lt; 1 hour: No chunking (default)</li>
          <li>Longer files: Use chunking to stay within limits</li>
        </ul>
        <p className="mt-2 text-slate-600 dark:text-slate-400">
          Note: No chunking gives you 4× better API quota usage and avoids timestamp ordering issues.
        </p>
      </div>

      <div className="flex items-center gap-4">
        <input
          type="number"
          min="0"
          step="1"
          value={chunkDuration}
          onChange={(e) => onChunkDurationChange(parseInt(e.target.value) || 0)}
          className="flex h-10 w-24 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        />
        <div className="flex-1 space-y-1">
          <p className="text-sm text-muted-foreground">
            {chunkDuration === 0
              ? `No chunking - analyze entire ${mediaType} as one piece`
              : `Split ${mediaType} into ${chunkDuration}-second chunks for analysis`
            }
          </p>
          {mediaDuration && chunkDuration > 0 && (
            <p className="text-xs text-muted-foreground">
              Estimated {Math.ceil(mediaDuration / chunkDuration)} chunks
            </p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-2 mt-2">
        <Button type="button" variant="outline" size="sm" onClick={() => onChunkDurationChange(0)}>
          No chunks (recommended)
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={() => onChunkDurationChange(60)}>
          60s
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={() => onChunkDurationChange(120)}>
          120s
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={() => onChunkDurationChange(300)}>
          5 min
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={() => onChunkDurationChange(600)}>
          10 min
        </Button>
      </div>
    </div>
  )
}
