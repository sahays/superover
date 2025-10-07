'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { Eye, FileText } from 'lucide-react';

export function AppHeader() {
  const pathname = usePathname();

  const navigation = [
    { name: 'Scene Analyzer', href: '/scene-analyzer', icon: Eye },
    { name: 'Files', href: '/files', icon: FileText },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center">
        <div className="mr-4 flex">
          <Link href="/" className="mr-6 flex items-center space-x-2">
            <div className="h-6 w-6 rounded bg-primary text-white flex items-center justify-center font-bold text-sm">
              S
            </div>
            <span className="hidden font-bold sm:inline-block">
              Super Over Alchemy
            </span>
          </Link>
          <nav className="flex items-center space-x-6 text-sm font-medium">
            {navigation.map((item) => {
              const Icon = item.icon;
              const isActive = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-2 transition-colors hover:text-foreground/80',
                    isActive ? 'text-foreground' : 'text-foreground/60'
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
}
