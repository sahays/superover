import { MediaJobStatus } from '@/lib/types'

interface JobProgressSectionProps {
  status: MediaJobStatus
  progress?: { step?: string; percent?: number } | null
  errorMessage?: string | null
}

export function JobProgressSection({ status, progress, errorMessage }: JobProgressSectionProps) {
  return (
    <>
      {status === MediaJobStatus.PROCESSING && progress && (
        <div className="space-y-2 rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium capitalize">{progress.step?.replace('_', ' ')}</span>
            <span className="font-semibold">{progress.percent}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-gray-200">
            <div
              className="h-full bg-blue-600 transition-all duration-300"
              style={{ width: `${progress.percent}%` }}
            />
          </div>
        </div>
      )}
      {status === MediaJobStatus.FAILED && errorMessage && (
        <div className="rounded-lg bg-red-50 p-4 dark:bg-red-900/20">
          <h4 className="font-semibold text-red-900 dark:text-red-100">Error</h4>
          <p className="mt-1 text-sm text-red-800 dark:text-red-200">{errorMessage}</p>
        </div>
      )}
    </>
  )
}
