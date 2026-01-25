'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { MessageSquare, FileCheck, FolderOpen, History, Sun, Moon, ChevronLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUIStore } from '@/stores';
import { Button } from '../ui';

const navItems = [
  { href: '/', icon: MessageSquare, label: 'Query' },
  { href: '/review', icon: FileCheck, label: 'Review' },
  { href: '/documents', icon: FolderOpen, label: 'Documents' },
  { href: '/history', icon: History, label: 'History' },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar, theme, setTheme } = useUIStore();

  const cycleTheme = () => {
    const themes: ('light' | 'dark' | 'system')[] = ['light', 'dark', 'system'];
    const idx = themes.indexOf(theme);
    setTheme(themes[(idx + 1) % themes.length]);
  };

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-screen border-r bg-card transition-all duration-300',
        sidebarOpen ? 'w-64' : 'w-16'
      )}
    >
      <div className="flex h-full flex-col">
        {/* Header */}
        <div className="flex h-16 items-center justify-between border-b px-4">
          {sidebarOpen && (
            <h1 className="text-xl font-bold text-primary-600">Pluno</h1>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className={cn(!sidebarOpen && 'mx-auto')}
          >
            <ChevronLeft className={cn('h-5 w-5 transition-transform', !sidebarOpen && 'rotate-180')} />
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 p-2">
          {navItems.map((item) => {
            const isActive = pathname === item.href || 
              (item.href !== '/' && pathname.startsWith(item.href));
            
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  'hover:bg-accent',
                  isActive
                    ? 'bg-primary-100 text-primary-900 dark:bg-primary-900/30 dark:text-primary-100'
                    : 'text-muted-foreground'
                )}
              >
                <item.icon className="h-5 w-5 flex-shrink-0" />
                {sidebarOpen && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Theme toggle */}
        <div className="border-t p-2">
          <Button
            variant="ghost"
            className={cn('w-full justify-start gap-3', !sidebarOpen && 'justify-center')}
            onClick={cycleTheme}
          >
            {theme === 'dark' ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
            {sidebarOpen && <span className="capitalize">{theme}</span>}
          </Button>
        </div>
      </div>
    </aside>
  );
}
