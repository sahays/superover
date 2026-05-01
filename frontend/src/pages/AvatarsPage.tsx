import { Link } from 'react-router-dom'
import { Plus, Trash2, User } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { useAvatars, useDeleteAvatar } from '@/lib/api/avatars'
import { PRESET_CATALOG, STYLE_LABELS } from '@/types/avatar'
import type { Avatar } from '@/types/avatar'

const PRESET_IMAGE_BY_ID: Record<string, string> = Object.fromEntries(
  PRESET_CATALOG.map((p) => [p.id, p.imageUrl]),
)

function thumbnailUrl(record: Avatar): string | null {
  return PRESET_IMAGE_BY_ID[record.preset_name] ?? null
}

export default function AvatarsPage() {
  const { data: avatars, isLoading } = useAvatars()
  const del = useDeleteAvatar()

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-3xl font-bold font-heading">Avatars</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {avatars?.length || 0} avatar{avatars?.length === 1 ? '' : 's'} · open one to start a live conversation
          </p>
        </div>
        <Link to="/avatars/create">
          <Button>
            <Plus className="mr-1.5 h-4 w-4" /> New Avatar
          </Button>
        </Link>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {avatars && avatars.length === 0 && (
        <Card className="p-10 text-center">
          <User className="mx-auto h-10 w-10 text-muted-foreground mb-3" />
          <h3 className="text-lg font-semibold">No avatars yet</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Pick a preset, give it a persona, and start chatting.
          </p>
          <Link to="/avatars/create" className="inline-block mt-4">
            <Button>
              <Plus className="mr-1.5 h-4 w-4" /> Create your first avatar
            </Button>
          </Link>
        </Card>
      )}

      <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 md:grid-cols-4">
        {avatars?.map((record) => {
          const url = thumbnailUrl(record)
          return (
            <Card key={record.id} className="group relative overflow-hidden p-0">
              <Link to={`/avatars/${record.id}`} className="block">
                <div className="aspect-[3/4] bg-muted">
                  {url ? (
                    <img src={url} alt={record.name} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                      <User size={32} />
                    </div>
                  )}
                </div>
                <div className="p-3">
                  <div className="font-medium truncate">{record.name}</div>
                  <div className="text-xs text-muted-foreground mt-0.5 flex items-center justify-between">
                    <span>{STYLE_LABELS[record.style]}</span>
                    <span>{record.voice}</span>
                  </div>
                </div>
              </Link>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <button
                    className="absolute top-2 right-2 rounded-md bg-background/80 p-1.5 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-destructive hover:text-destructive-foreground"
                    aria-label="Delete avatar"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Trash2 size={14} />
                  </button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Delete {record.name}?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This permanently removes the avatar. The persona and voice settings cannot be recovered.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction onClick={() => del.mutate(record.id)}>Delete</AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
