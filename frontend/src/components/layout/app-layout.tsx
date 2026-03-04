import { useEffect } from 'react'
import { Sidebar } from './sidebar'
import { useBranding } from '@/hooks/use-branding'

interface AppLayoutProps {
  children: React.ReactNode
}

export function AppLayout({ children }: AppLayoutProps) {
  const { data: branding } = useBranding()

  useEffect(() => {
    const title = branding?.app_title || 'Superover'
    const subtitle = branding?.subtitle || 'Video Analysis Platform'
    document.title = `${title} - ${subtitle}`
  }, [branding?.app_title, branding?.subtitle])

  return (
    <div className="min-h-screen bg-[var(--color-bg-primary)]">
      <Sidebar />
      <main className="ml-64">
        {children}
      </main>
    </div>
  )
}
