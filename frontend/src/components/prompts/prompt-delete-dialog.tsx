import { Loader2 } from 'lucide-react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import type { Prompt } from '@/lib/types'

interface PromptDeleteDialogProps {
  prompt: Prompt | null
  onConfirm: () => void
  onCancel: () => void
  isDeleting: boolean
}

export function PromptDeleteDialog({ prompt, onConfirm, onCancel, isDeleting }: PromptDeleteDialogProps) {
  return (
    <AlertDialog open={prompt !== null} onOpenChange={(open) => { if (!open) onCancel() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Prompt?</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete &ldquo;{prompt?.name}&rdquo;?
            {prompt && prompt.jobs_count && prompt.jobs_count > 0 ? (
              <span className="mt-2 block font-semibold text-red-600">
                Warning: {prompt.jobs_count} job(s) are using this prompt. Deletion will be blocked.
              </span>
            ) : (
              <span className="mt-2 block">This action cannot be undone.</span>
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm} disabled={isDeleting} className="bg-red-600 hover:bg-red-700">
            {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
