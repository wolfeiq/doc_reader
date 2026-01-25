'use client';

import { Providers } from '@/components/Providers';
import { Sidebar } from '@/components/layout';

export function ClientLayout({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <Sidebar />
      <main className="ml-64 min-h-screen transition-all duration-300">
        <div className="container mx-auto p-6">
          {children}
        </div>
      </main>
    </Providers>
  );
}