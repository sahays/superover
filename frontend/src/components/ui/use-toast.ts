// This is a placeholder file. The actual implementation of the Toast component
// would be provided by the shadcn/ui library.

const ToastAction: React.FC<any> = () => null

const useToast = () => {
  return {
    toast: (props: any) => {
      console.log("Toast:", props)
    },
  }
}

export { useToast, ToastAction }
