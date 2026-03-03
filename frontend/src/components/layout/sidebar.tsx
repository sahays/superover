import { Link, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import {
  Home,
  Video,
  FileVideo,
  FileText,
  Clapperboard,
  Search,
  DatabaseZap,
} from 'lucide-react'

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
    title: 'Search Sync',
    href: '/search/sync',
    icon: DatabaseZap,
    description: 'Sync results to search index',
  },
]

// Hrefs that should only match exactly (not their sub-paths)
const exactMatchOnly = new Set(['/search'])

function isNavActive(pathname: string, href: string): boolean {
  if (href === '/' || exactMatchOnly.has(href)) return pathname === href
  return pathname === href || pathname.startsWith(href + '/')
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

export function Sidebar() {
  const pathname = useLocation().pathname

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r bg-white dark:bg-slate-900">
      <div className="flex h-full flex-col">
        {/* Logo/Brand */}
        <div className="flex h-16 items-center border-b px-6">
          <Link to="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <FileVideo className="h-5 w-5" />
            </div>
            <span className="text-lg font-bold">Super Over</span>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4">
          <div className="space-y-1">
            {featureItems.map((item) => (
              <NavLink key={item.href} item={item} pathname={pathname} />
            ))}
          </div>

          {/* Separator */}
          <div className="my-4 border-t" />

          <div className="space-y-1">
            <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">
              Configuration
            </p>
            {configItems.map((item) => (
              <NavLink key={item.href} item={item} pathname={pathname} />
            ))}
          </div>
        </nav>

        {/* Footer */}
        <div className="border-t p-4">
          <div className="text-xs text-muted-foreground">
            <p className="font-medium">Super Over Alchemy</p>
            <p className="mt-1">Video Analysis Platform</p>
          </div>
        </div>
      </div>
    </aside>
  )
}
