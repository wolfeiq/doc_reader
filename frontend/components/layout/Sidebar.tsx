'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { MessageSquare, FileCheck, FolderOpen, History, ChevronLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUIStore } from '@/stores';
import { Button } from '../ui';

const navItems = [
  { href: '/', icon: MessageSquare, label: 'Query' },
  { href: '/documents', icon: FolderOpen, label: 'Documents' },
  { href: '/history', icon: History, label: 'History' },
];

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar } = useUIStore();

  return (
    <aside
      className={cn(
        'h-screen border-r bg-card/80 backdrop-blur-xl transition-all duration-300 flex flex-col',
        sidebarOpen ? 'w-64' : 'w-20',
        className
      )}
    >
      <div className="flex h-16 items-center justify-between border-b px-4 shrink-0">
        <div className={cn(
          "h-9 w-9 rounded-xl bg-primary-600 flex items-center justify-center shadow-lg shadow-primary-500/20",
          !sidebarOpen && "mx-auto"
        )}>
           <span className="text-white font-bold text-lg">P</span>
        </div>
        
        {sidebarOpen && (
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className="hidden md:flex"
          >
            <ChevronLeft className="h-5 w-5" />
          </Button>
        )}
      </div>

      <nav className="flex-1 space-y-2 p-3 overflow-y-auto mt-4">
        {navItems.map((item) => {
          const isActive = pathname === item.href || 
            (item.href !== '/' && pathname.startsWith(item.href));
          
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200',
                isActive
                  ? 'bg-primary-500/10 text-primary-400 border border-primary-500/20'
                  : 'text-muted-foreground hover:bg-white/5 hover:text-white'
              )}
            >
              <item.icon className={cn("h-5 w-5 flex-shrink-0", isActive && "text-primary-400")} />
              {sidebarOpen && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {!sidebarOpen && (
        <div className="p-4 border-t border-white/5 hidden md:block text-center">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className="mx-auto"
          >
            <ChevronLeft className="h-5 w-5 rotate-180" />
          </Button>
        </div>
      )}
    </aside>
  );
}