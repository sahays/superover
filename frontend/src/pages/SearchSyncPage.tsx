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
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'

interface SyncStatusItem {
  result_id: string
  video_id: string
  video_filename: string | null
  scene_job_id: string | null
  chunk_index: number | null
  sync_status: 'not_synced' | 'pending' | 'ready' | 'error'
  sync_error: string | null
  text_preview: string | null
}

export default function SearchSyncPage() {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const { data: items, isLoading } = useQuery<SyncStatusItem[]>({
    queryKey: ['search-sync-status'],
    queryFn: () => searchApi.getSyncStatus(),
    // Auto-refresh every 5s while there are pending items
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
                    <SyncCard
                      key={item.result_id}
                      item={item}
                      selected={selected.has(item.result_id)}
                      onToggle={() => toggleSelect(item.result_id)}
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
                    <Card
                      key={item.result_id}
                      className="border-amber-200 bg-amber-50/50 dark:border-amber-900 dark:bg-amber-950/20"
                    >
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">
                              {item.video_filename || item.video_id}
                            </p>
                            {item.chunk_index != null && (
                              <Badge
                                variant="secondary"
                                className="text-xs mt-1"
                              >
                                Chunk {item.chunk_index}
                              </Badge>
                            )}
                          </div>
                          <Badge
                            variant="outline"
                            className="border-amber-400 text-amber-700 dark:text-amber-400 shrink-0"
                          >
                            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                            Pending
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-2">
                          {item.text_preview}
                        </p>
                      </CardContent>
                    </Card>
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
                    <Card
                      key={item.result_id}
                      className="border-red-200 bg-red-50/50 dark:border-red-900 dark:bg-red-950/20"
                    >
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">
                              {item.video_filename || item.video_id}
                            </p>
                            {item.sync_error && (
                              <p className="text-xs text-destructive mt-1">
                                {item.sync_error}
                              </p>
                            )}
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <Badge variant="destructive">
                              <AlertCircle className="mr-1 h-3 w-3" />
                              Error
                            </Badge>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-muted-foreground hover:text-destructive"
                              onClick={() =>
                                deleteMutation.mutate(item.result_id)
                              }
                              disabled={deleteMutation.isPending}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-2">
                          {item.text_preview}
                        </p>
                      </CardContent>
                    </Card>
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
                    <Card
                      key={item.result_id}
                      className="border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/20"
                    >
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">
                              {item.video_filename || item.video_id}
                            </p>
                            {item.chunk_index != null && (
                              <Badge
                                variant="secondary"
                                className="text-xs mt-1"
                              >
                                Chunk {item.chunk_index}
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <Badge className="bg-green-600">
                              <Check className="mr-1 h-3 w-3" />
                              Searchable
                            </Badge>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-muted-foreground hover:text-destructive"
                              onClick={() =>
                                deleteMutation.mutate(item.result_id)
                              }
                              disabled={deleteMutation.isPending}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-2">
                          {item.text_preview}
                        </p>
                      </CardContent>
                    </Card>
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
    </div>
  )
}

function SyncCard({
  item,
  selected,
  onToggle,
}: {
  item: SyncStatusItem
  selected: boolean
  onToggle: () => void
}) {
  return (
    <Card
      className={`cursor-pointer transition-colors ${
        selected ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
      }`}
      onClick={onToggle}
    >
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <Checkbox checked={selected} className="mt-1" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium truncate">
              {item.video_filename || item.video_id}
            </p>
            {item.chunk_index != null && (
              <Badge variant="secondary" className="text-xs mt-1">
                Chunk {item.chunk_index}
              </Badge>
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
