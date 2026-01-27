/**
 * API Hooks - React Query Data Fetching
 * ======================================
 *
 * This module provides React Query hooks for all API operations.
 * React Query handles caching, background refetching, and loading states.
 *
 * Why React Query?
 * ----------------
 * - Automatic caching with configurable stale times
 * - Background refetching keeps data fresh
 * - Optimistic updates for instant UI feedback
 * - Built-in loading/error states
 * - Devtools for debugging cache state
 *
 * Query Key Strategy:
 * -------------------
 * We use hierarchical keys for targeted invalidation:
 * - ['queries'] - All queries (list invalidation)
 * - ['queries', id] - Specific query (detail invalidation)
 * - ['documents', id, 'preview'] - Nested resources
 *
 * Optimistic Updates:
 * -------------------
 * Mutations use optimistic updates for instant feedback:
 * 1. onMutate: Update cache immediately, save previous state
 * 2. onError: Rollback to previous state if API fails
 * 3. onSettled: Refetch to ensure consistency
 *
 * This pattern makes the UI feel instant while maintaining data integrity.
 *
 * Production Considerations:
 * --------------------------
 * - Configure staleTime/cacheTime per query based on data volatility
 * - Add retry logic for network failures
 * - Consider prefetching for predictable navigation
 * - Add global error handling with QueryClient config
 * - Monitor cache hit rates for optimization
 */

'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryApi, suggestionApi, documentApi, historyApi } from '@/lib/api';
import type { QueryCreate, SuggestionUpdate, UserAction, QueryDetail, Suggestion } from '@/types';

/**
 * Query key factory for consistent cache key generation.
 *
 * Using `as const` ensures type safety and enables autocomplete.
 * Factory pattern allows dynamic keys while maintaining structure.
 */
export const queryKeys = {
  queries: ['queries'] as const,
  query: (id: string) => ['queries', id] as const,
  documents: ['documents'] as const,
  document: (id: string) => ['documents', id] as const,
  documentPreview: (id: string) => ['documents', id, 'preview'] as const,
  history: ['history'] as const,
};

export function useQueries(params?: { skip?: number; limit?: number; status?: string }) {
  return useQuery({
    queryKey: [...queryKeys.queries, params],
    queryFn: () => queryApi.list(params),
  });
}

export function useQueryDetail(id: string) {
  return useQuery({
    queryKey: queryKeys.query(id),
    queryFn: () => queryApi.get(id),
    enabled: !!id,
  });
}

export function useCreateQuery() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: QueryCreate) => queryApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.queries });
    },
  });
}

export function useDeleteQuery() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => queryApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.queries });
    },
  });
}

export function useDocuments() {
  return useQuery({
    queryKey: queryKeys.documents,
    queryFn: () => documentApi.list(),
  });
}

export function useDocument(id: string) {
  return useQuery({
    queryKey: queryKeys.document(id),
    queryFn: () => documentApi.get(id),
    enabled: !!id,
  });
}

export function useDocumentPreview(id: string) {
  return useQuery({
    queryKey: queryKeys.documentPreview(id),
    queryFn: () => documentApi.preview(id),
    enabled: !!id,
  });
}

export function useHistory(params?: { limit?: number; action?: UserAction }) {
  return useQuery({
    queryKey: [...queryKeys.history, params],
    queryFn: () => historyApi.list(params),
  });
}

export function useAcceptSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => suggestionApi.accept(id),
    onMutate: async (id: string) => {
      // Cancel any outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ predicate: (q) => q.queryKey[0] === 'queries' });

      // Snapshot current query data for rollback
      const queryCache = queryClient.getQueriesData<QueryDetail>({ queryKey: queryKeys.queries });

      // Optimistically update all matching queries
      queryClient.setQueriesData<QueryDetail>(
        { predicate: (q) => q.queryKey[0] === 'queries' && q.queryKey.length > 1 },
        (old) => {
          if (!old?.suggestions) return old;
          return {
            ...old,
            suggestions: old.suggestions.map((s: Suggestion) =>
              s.id === id ? { ...s, status: 'ACCEPTED' as const } : s
            ),
          };
        }
      );

      return { queryCache };
    },
    onError: (_err, _id, context) => {
      // Rollback on error
      if (context?.queryCache) {
        context.queryCache.forEach(([key, data]) => {
          queryClient.setQueryData(key, data);
        });
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey[0] === 'queries' || query.queryKey[0] === 'documents'
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.history });
    },
  });
}

export function useRejectSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => suggestionApi.reject(id),
    onMutate: async (id: string) => {
      await queryClient.cancelQueries({ predicate: (q) => q.queryKey[0] === 'queries' });

      const queryCache = queryClient.getQueriesData<QueryDetail>({ queryKey: queryKeys.queries });

      queryClient.setQueriesData<QueryDetail>(
        { predicate: (q) => q.queryKey[0] === 'queries' && q.queryKey.length > 1 },
        (old) => {
          if (!old?.suggestions) return old;
          return {
            ...old,
            suggestions: old.suggestions.map((s: Suggestion) =>
              s.id === id ? { ...s, status: 'REJECTED' as const } : s
            ),
          };
        }
      );

      return { queryCache };
    },
    onError: (_err, _id, context) => {
      if (context?.queryCache) {
        context.queryCache.forEach(([key, data]) => {
          queryClient.setQueryData(key, data);
        });
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey[0] === 'queries' || query.queryKey[0] === 'documents'
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.history });
    },
  });
}

export function useUpdateSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SuggestionUpdate }) =>
      suggestionApi.update(id, data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ predicate: (q) => q.queryKey[0] === 'queries' });

      const queryCache = queryClient.getQueriesData<QueryDetail>({ queryKey: queryKeys.queries });

      queryClient.setQueriesData<QueryDetail>(
        { predicate: (q) => q.queryKey[0] === 'queries' && q.queryKey.length > 1 },
        (old) => {
          if (!old?.suggestions) return old;
          return {
            ...old,
            suggestions: old.suggestions.map((s: Suggestion) =>
              s.id === id
                ? {
                    ...s,
                    ...(data.edited_text !== undefined && { edited_text: data.edited_text }),
                    ...(data.status !== undefined && { status: data.status }),
                  }
                : s
            ),
          };
        }
      );

      return { queryCache };
    },
    onError: (_err, _vars, context) => {
      if (context?.queryCache) {
        context.queryCache.forEach(([key, data]) => {
          queryClient.setQueryData(key, data);
        });
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey[0] === 'queries' || query.queryKey[0] === 'documents'
      });
    },
  });
}