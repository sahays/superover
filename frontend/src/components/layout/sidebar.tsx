import { Link, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useEffect, useState } from 'react'
import {
  Home,
  Video,
  FileText,
  Clapperboard,
  Search,
  DatabaseZap,
  Palette,
  Sun,
  Moon,
} from 'lucide-react'
import { useBranding } from '@/hooks/use-branding'

interface NavItem {
  title: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  description: string
}

const featureItems: NavItem[] = [
  {
    title: 'Home',
    href: '/',
    icon: Home,
    description: 'Dashboard and overview',
  },
  {
    title: 'Media Processing',
    href: '/media',
    icon: Video,
    description: 'Upload and compress videos',
  },
  {
    title: 'Scene Analysis',
    href: '/scene-analysis',
    icon: Clapperboard,
    description: 'AI-powered scene analysis',
  },
  {
    title: 'Search',
    href: '/search',
    icon: Search,
    description: 'Semantic video search',
  },
]

const configItems: NavItem[] = [
  {
    title: 'Prompts',
    href: '/prompts',
    icon: FileText,
    description: 'Manage analysis prompts',
  },
  {
    title: 'Embeddings',
    href: '/search/sync',
    icon: DatabaseZap,
    description: 'Sync results to search index',
  },
  {
    title: 'Branding',
    href: '/branding',
    icon: Palette,
    description: 'Customize app branding',
  },
]

// Hrefs that should only match exactly (not their sub-paths)
const exactMatchOnly = new Set(['/search'])

function isNavActive(pathname: string, href: string): boolean {
  if (href === '/' || exactMatchOnly.has(href)) return pathname === href
  return pathname === href || pathname.startsWith(href + '/')
}

function GoogleLogo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A10.96 10.96 0 0 0 1 12c0 1.77.42 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  )
}

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const Icon = item.icon
  const isActive = isNavActive(pathname, item.href)

  return (
    <Link
      to={item.href}
      className={cn(
        'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
        isActive
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
      )}
    >
      <Icon className="h-5 w-5 flex-shrink-0" />
      <div className="flex flex-col">
        <span>{item.title}</span>
        {!isActive && (
          <span className="text-xs opacity-70">{item.description}</span>
        )}
      </div>
    </Link>
  )
}

function DarkModeToggle() {
  const [isDark, setIsDark] = useState(() => {
    if (typeof window === 'undefined') return true
    const stored = localStorage.getItem('theme')
    if (stored) return stored === 'dark'
    return document.documentElement.classList.contains('dark')
  })

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }, [isDark])

  return (
    <button
      onClick={() => setIsDark(!isDark)}
      className="btn-press flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      <span>{isDark ? 'Light mode' : 'Dark mode'}</span>
    </button>
  )
}

function BrandLogo({ logoUrl }: { logoUrl: string }) {
  const [error, setError] = useState(false)

  useEffect(() => {
    setError(false)
  }, [logoUrl])

  if (logoUrl && !error) {
    return (
      <img
        src={logoUrl}
        alt="Logo"
        className="h-7 w-7 object-contain"
        onError={() => setError(true)}
      />
    )
  }
  return <GoogleLogo className="h-7 w-7" />
}

export function Sidebar() {
  const pathname = useLocation().pathname
  const { data: branding } = useBranding()
  const appTitle = branding?.app_title || 'Superover'
  const subtitle = branding?.subtitle || 'Video Analysis Platform'
  const logoUrl = branding?.logo_url || ''

  return (
    <aside className="nav-frosted fixed left-0 top-0 z-40 h-screen w-64 border-r">
      <div className="flex h-full flex-col">
        {/* Logo/Brand */}
        <div className="flex h-16 items-center border-b px-6">
          <Link to="/" className="flex items-center gap-2">
            <BrandLogo logoUrl={logoUrl} />
            <span className="text-lg font-bold font-heading">{appTitle}</span>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4">
          <div className="stagger-children space-y-1">
            {featureItems.map((item) => (
              <NavLink key={item.href} item={item} pathname={pathname} />
            ))}
          </div>

          {/* Separator */}
          <div className="my-4 border-t" />

          <div className="stagger-children space-y-1">
            <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">
              Configuration
            </p>
            {configItems.map((item) => (
              <NavLink key={item.href} item={item} pathname={pathname} />
            ))}
          </div>
        </nav>

        {/* Footer */}
        <div className="border-t p-4 space-y-2">
          <DarkModeToggle />
          <div className="text-xs text-muted-foreground">
            <p className="font-medium font-heading">{appTitle}</p>
            <p className="mt-1">{subtitle}</p>
          </div>
        </div>
      </div>
    </aside>
  )
}
