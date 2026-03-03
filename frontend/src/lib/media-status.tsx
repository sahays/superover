import { Badge } from '@/components/ui/badge'
import { CheckCircle, XCircle, Loader2 } from 'lucide-react'
import { MediaJobStatus } from '@/lib/types'

export function getMediaStatusBadge(status: MediaJobStatus, progress?: { step?: string }) {
  switch (status) {
    case MediaJobStatus.COMPLETED:
      return (
        <Badge variant="default" className="bg-green-600">
          <CheckCircle className="mr-1 h-3 w-3" />
          Completed
        </Badge>
      )
    case MediaJobStatus.PROCESSING: {
      const stepLabel = progress?.step
        ? progress.step.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())
        : 'Processing'
      return (
        <Badge variant="default" className="bg-blue-600">
          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          {stepLabel}
        </Badge>
      )
    }
    case MediaJobStatus.FAILED:
      return (
        <Badge variant="destructive">
          <XCircle className="mr-1 h-3 w-3" />
          Failed
        </Badge>
      )
    case MediaJobStatus.PENDING:
      return <Badge variant="outline">Pending</Badge>
    default:
      return <Badge variant="outline">{status}</Badge>
  }
}
