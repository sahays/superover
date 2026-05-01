import { useParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { AvatarLiveView } from '@/components/avatar/AvatarLiveView'
import { useAvatar } from '@/lib/api/avatars'

export default function AvatarPage() {
  const { id } = useParams<{ id: string }>()
  const { data: avatar, isLoading, error } = useAvatar(id)

  if (isLoading) {
    return (
      <div className="container mx-auto max-w-3xl px-4 py-8 flex items-center gap-2 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading avatar…
      </div>
    )
  }

  if (error || !avatar) {
    return (
      <div className="container mx-auto max-w-3xl px-4 py-8 text-sm text-destructive">
        Avatar not found.
      </div>
    )
  }

  return <AvatarLiveView avatar={avatar} />
}
