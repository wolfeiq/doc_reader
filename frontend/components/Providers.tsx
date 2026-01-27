/**
 * Application Providers
 * =====================
 *
 * This component wraps the application with all necessary context providers.
 * Currently provides React Query, but can be extended for other providers.
 *
 * Provider Stack:
 * ---------------
 * - QueryClientProvider: React Query data fetching
 * - (Future) ThemeProvider: Dark/light mode
 * - (Future) AuthProvider: User authentication
 * - (Future) ToastProvider: Notifications
 *
 * QueryClient Configuration:
 * --------------------------
 * - staleTime: 60s - Data considered fresh for 1 minute
 * - retry: 1 - Only retry failed requests once
 * - refetchOnWindowFocus: false - Don't refetch when tab gains focus
 *
 * Why useState for QueryClient?
 * -----------------------------
 * Using useState ensures the QueryClient is only created once per component
 * lifecycle, even with React's Strict Mode double-rendering in development.
 * This prevents cache inconsistencies and memory leaks.
 *
 * Production Considerations:
 * --------------------------
 * - Add ReactQueryDevtools for debugging (remove in production)
 * - Configure global error handler for failed queries
 * - Add auth provider with token refresh logic
 * - Consider adding Suspense boundary for loading states
 */

'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';

/**
 * Root providers component wrapping the application.
 * Initializes React Query client with app-wide defaults.
 */
export function Providers({ children }: { children: ReactNode }) {
  // Create QueryClient in useState to ensure single instance
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,  // Consider data fresh for 1 minute
            retry: 1,              // Retry failed requests once
            refetchOnWindowFocus: false, // Don't refetch on tab focus
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {/* Production: Add <ReactQueryDevtools /> here for debugging */}
    </QueryClientProvider>
  );
}
