/**
 * Environment variable access with validation
 * Next.js replaces NEXT_PUBLIC_* at build time, so we validate lazily
 */

// API configuration - falls back to empty string for SSR/build, validated at runtime
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://docreader-production-b979.up.railway.app/api';

// Debug: log API_BASE on client-side
if (typeof window !== 'undefined') {
  console.log('API_BASE:', API_BASE);
  console.log('NEXT_PUBLIC_API_URL:', process.env.NEXT_PUBLIC_API_URL);
}

// Validate at runtime when actually making API calls (client-side only)
export function validateEnv(): void {
  if (typeof window !== 'undefined' && !API_BASE) {
    console.error(
      'NEXT_PUBLIC_API_URL is not set. Make sure it is defined in .env or .env.local and restart the dev server.'
    );
  }
}
