'use client';

import { useState } from 'react';
import './globals.css';
import { Providers } from '@/components/Providers';
import { Sidebar } from '@/components/layout';
import GlobalFlashlight from '@/components/GlobalFlashlight';
import { cn } from '@/lib/utils';
import { Inter, Libre_Baskerville } from 'next/font/google';
import { Menu, X } from 'lucide-react'; 

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });
const libreBaskerville = Libre_Baskerville({
  weight: ['400', '700'],
  subsets: ['latin'],
  variable: '--font-libre',
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <html lang="en" className={`${inter.variable} ${libreBaskerville.variable}`} suppressHydrationWarning>
      <body className={cn(inter.className, 'min-h-screen antialiased text-white selection:bg-white/20 bg-black')}>
        <Providers>
          <GlobalFlashlight />
  
          <button 
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="md:hidden fixed bottom-6 right-6 z-[60] p-4 rounded-full bg-primary-600 text-white shadow-2xl border border-primary-400/20 animate-glow"
          >
            {isSidebarOpen ? <X size={24} /> : <Menu size={24} />}
          </button>

          <div className="relative flex min-h-screen">
            <Sidebar 
              className={cn(
                "fixed inset-y-0 left-0 z-50 w-64 border-r border-white/10 bg-black/40 backdrop-blur-xl transition-transform duration-300 md:translate-x-0",
                isSidebarOpen ? "translate-x-0" : "-translate-x-full"
              )} 
            />

            {isSidebarOpen && (
              <div 
                className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden"
                onClick={() => setIsSidebarOpen(false)}
              />
            )}

            <main className={cn(
              "flex-1 w-full min-h-screen transition-all duration-300",
              "md:ml-64"
            )}>
              <div className="container mx-auto p-4 md:p-8">
                {children}
              </div>
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}