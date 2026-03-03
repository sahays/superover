import { toast } from 'sonner'

/**
 * Compatibility wrapper that maps the old { title, description } API
 * to sonner's toast() function. New code should import { toast } from 'sonner' directly.
 */
const useToast = () => {
  return {
    toast: (props: { title?: string; description?: string; variant?: string }) => {
      if (props.variant === 'destructive') {
        toast.error(props.title, { description: props.description })
      } else {
        toast(props.title, { description: props.description })
      }
    },
  }
}

export { useToast, toast }
