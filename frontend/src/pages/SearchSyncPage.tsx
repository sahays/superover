import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  DatabaseZap,
  Check,
  Upload,
  Trash2,
  Loader2,
  AlertCircle,
  RefreshCw,
  Eye,
} from 'lucide-react'
import { searchApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { VideoSearchPlayer } from '@/components/search/video-search-player'

interface SyncStatusItem {
  result_id: string
  video_id: string
  video_filename: string | null
  scene_job_id: string | null
  chunk_index: number | null
  sync_status: 'not_synced' | 'pending' | 'ready' | 'error'
  sync_error: string | null
  text_preview: string | null
  text_content: string | null
}

export default function SearchSyncPage() {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [previewItem, setPreviewItem] = useState<SyncStatusItem | null>(null)

  const { data: items, isLoading } = useQuery<SyncStatusItem[]>({
    queryKey: ['search-sync-status'],
    queryFn: () => searchApi.getSyncStatus(),
    refetchInterval: (query) => {
      const data = query.state.data
      if (data?.some((item) => item.sync_status === 'pending')) {
        return 5000
      }
      return false
    },
  })

  const syncMutation = useMutation({
    mutationFn: (resultIds: string[]) => searchApi.syncResults(resultIds),
    onSuccess: (data) => {
      toast.success(
        `Submitted ${data.synced_count} result(s) for indexing`
      )
      if (data.errors?.length > 0) {
        toast.error(`${data.errors.length} error(s) during sync`)
      }
      setSelected(new Set())
      queryClient.invalidateQueries({ queryKey: ['search-sync-status'] })
    },
    onError: () => {
      toast.error('Failed to sync results')
    },
  })

  const resyncMutation = useMutation({
    mutationFn: (resultIds: string[]) => searchApi.syncResults(resultIds, true),
    onSuccess: (data) => {
      toast.success(
        `Re-indexing ${data.synced_count} result(s) with improved embeddings`
      )
      queryClient.invalidateQueries({ queryKey: ['search-sync-status'] })
    },
    onError: () => {
      toast.error('Failed to re-index results')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (resultId: string) => searchApi.deleteSyncedResult(resultId),
    onSuccess: () => {
      toast.success('Removed from search index')
      queryClient.invalidateQueries({ queryKey: ['search-sync-status'] })
    },
    onError: () => {
      toast.error('Failed to remove from search index')
    },
  })

  const notSyncedItems =
    items?.filter((item) => item.sync_status === 'not_synced') || []
  const pendingItems =
    items?.filter((item) => item.sync_status === 'pending') || []
  const readyItems =
    items?.filter((item) => item.sync_status === 'ready') || []
  const errorItems =
    items?.filter((item) => item.sync_status === 'error') || []

  const toggleSelect = (resultId: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(resultId)) {
        next.delete(resultId)
      } else {
        next.add(resultId)
      }
      return next
    })
  }

  const selectAllUnsynced = () => {
    setSelected(new Set(notSyncedItems.map((item) => item.result_id)))
  }

  const handleSync = () => {
    if (selected.size === 0) return
    syncMutation.mutate(Array.from(selected))
  }

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Search Sync</h1>
          <p className="text-muted-foreground mt-1">
            Manage which scene results are indexed for semantic search
          </p>
        </div>
        {notSyncedItems.length > 0 && (
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={selectAllUnsynced}>
              Select All ({notSyncedItems.length})
            </Button>
            <Button
              onClick={handleSync}
              disabled={selected.size === 0 || syncMutation.isPending}
            >
              <Upload className="mr-2 h-4 w-4" />
              {syncMutation.isPending
                ? 'Syncing...'
                : `Sync Selected (${selected.size})`}
            </Button>
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-4 mb-8">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Results</CardDescription>
            <CardTitle className="text-3xl">{items?.length || 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Searchable</CardDescription>
            <CardTitle className="text-3xl text-green-600">
              {readyItems.length}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Generating Embeddings</CardDescription>
            <CardTitle className="text-3xl text-amber-600">
              {pendingItems.length}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Not Synced</CardDescription>
            <CardTitle className="text-3xl text-gray-500">
              {notSyncedItems.length}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {isLoading ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">Loading scene results...</p>
          </CardContent>
        </Card>
      ) : items && items.length > 0 ? (
        <div className="space-y-6">
          {/* Not Synced Results */}
          {notSyncedItems.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Not Synced</CardTitle>
                <CardDescription>
                  {notSyncedItems.length} result(s) not yet in the search index
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {notSyncedItems.map((item) => (
                    <SyncItemCard
                      key={item.result_id}
                      item={item}
                      selectable
                      selected={selected.has(item.result_id)}
                      onToggle={() => toggleSelect(item.result_id)}
                      onPreview={() => setPreviewItem(item)}
                    />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Pending Embeddings */}
          {pendingItems.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  Generating Embeddings
                  <Loader2 className="h-4 w-4 animate-spin text-amber-600" />
                </CardTitle>
                <CardDescription>
                  {pendingItems.length} result(s) — embeddings generating in
                  BigQuery. This page refreshes automatically.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {pendingItems.map((item) => (
                    <SyncItemCard
                      key={item.result_id}
                      item={item}
                      cardClassName="border-amber-200 bg-amber-50/50 dark:border-amber-900 dark:bg-amber-950/20"
                      badge={
                        <Badge
                          variant="outline"
                          className="border-amber-400 text-amber-700 dark:text-amber-400"
                        >
                          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                          Pending
                        </Badge>
                      }
                      onPreview={() => setPreviewItem(item)}
                    />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Error Results */}
          {errorItems.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-destructive">
                  <AlertCircle className="h-5 w-5" />
                  Errors
                </CardTitle>
                <CardDescription>
                  {errorItems.length} result(s) failed embedding generation
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {errorItems.map((item) => (
                    <SyncItemCard
                      key={item.result_id}
                      item={item}
                      cardClassName="border-red-200 bg-red-50/50 dark:border-red-900 dark:bg-red-950/20"
                      badge={
                        <Badge variant="destructive">
                          <AlertCircle className="mr-1 h-3 w-3" />
                          Error
                        </Badge>
                      }
                      onPreview={() => setPreviewItem(item)}
                      onDelete={() => deleteMutation.mutate(item.result_id)}
                      deleteDisabled={deleteMutation.isPending}
                    />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Ready / Searchable Results */}
          {readyItems.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Searchable</CardTitle>
                    <CardDescription>
                      {readyItems.length} result(s) indexed and searchable
                    </CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      resyncMutation.mutate(
                        readyItems.map((item) => item.result_id)
                      )
                    }
                    disabled={resyncMutation.isPending}
                  >
                    <RefreshCw className={`mr-2 h-4 w-4 ${resyncMutation.isPending ? 'animate-spin' : ''}`} />
                    {resyncMutation.isPending ? 'Re-indexing...' : 'Re-index All'}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {readyItems.map((item) => (
                    <SyncItemCard
                      key={item.result_id}
                      item={item}
                      cardClassName="border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/20"
                      badge={
                        <Badge className="bg-green-600">
                          <Check className="mr-1 h-3 w-3" />
                          Searchable
                        </Badge>
                      }
                      onPreview={() => setPreviewItem(item)}
                      onDelete={() => deleteMutation.mutate(item.result_id)}
                      deleteDisabled={deleteMutation.isPending}
                    />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <DatabaseZap className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-lg font-semibold">
              No scene results yet
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Run scene analysis first to generate results that can be synced
              for search.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Embedded Text Preview Dialog */}
      <Dialog open={!!previewItem} onOpenChange={() => setPreviewItem(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="truncate">
              {previewItem?.video_filename || previewItem?.video_id}
            </DialogTitle>
            <DialogDescription>
              Text sent to BigQuery for embedding generation
            </DialogDescription>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto">
            <pre className="whitespace-pre-wrap text-sm font-mono rounded-lg bg-slate-50 dark:bg-slate-900 p-4">
              {previewItem?.text_content || previewItem?.text_preview}
            </pre>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function SyncItemCard({
  item,
  selectable,
  selected,
  onToggle,
  badge,
  cardClassName,
  onPreview,
  onDelete,
  deleteDisabled,
}: {
  item: SyncStatusItem
  selectable?: boolean
  selected?: boolean
  onToggle?: () => void
  badge?: React.ReactNode
  cardClassName?: string
  onPreview: () => void
  onDelete?: () => void
  deleteDisabled?: boolean
}) {
  return (
    <Card
      className={
        selectable
          ? `cursor-pointer transition-colors ${selected ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'}`
          : cardClassName || ''
      }
      onClick={selectable ? onToggle : undefined}
    >
      <CardContent className="p-4 space-y-3">
        {/* Video Player */}
        <div className="rounded-md overflow-hidden">
          <VideoSearchPlayer videoId={item.video_id} />
        </div>

        {/* Header row */}
        <div className="flex items-start gap-3">
          {selectable && <Checkbox checked={selected} className="mt-1" />}
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-medium truncate">
                {item.video_filename || item.video_id}
              </p>
              <div className="flex items-center gap-1 shrink-0">
                {badge}
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  onClick={(e) => { e.stopPropagation(); onPreview() }}
                >
                  <Eye className="h-4 w-4" />
                </Button>
                {onDelete && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive"
                    onClick={(e) => { e.stopPropagation(); onDelete() }}
                    disabled={deleteDisabled}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
            {item.chunk_index != null && (
              <Badge variant="secondary" className="text-xs mt-1">
                Chunk {item.chunk_index}
              </Badge>
            )}
            {item.sync_error && (
              <p className="text-xs text-destructive mt-1">{item.sync_error}</p>
            )}
            <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
              {item.text_preview}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
