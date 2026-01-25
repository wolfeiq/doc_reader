import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from '@/components/Providers';
import { Sidebar } from '@/components/layout';
import { cn } from '@/lib/utils';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Pluno - Documentation Update Assistant',
  description: 'AI-powered documentation update suggestions',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={cn(inter.className, 'min-h-screen bg-background')}>
        <Providers>
          <Sidebar />
          <main className="ml-64 min-h-screen transition-all duration-300">
            <div className="container mx-auto p-6">
              {children}
            </div>
          </main>
        </Providers>
      </body>
    </html>
  );
}
