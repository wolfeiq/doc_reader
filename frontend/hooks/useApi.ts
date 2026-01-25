'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryApi, suggestionApi, documentApi, historyApi } from '@/lib/api';
import type { QueryCreate, SuggestionUpdate } from '@/types';

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

export function useHistory(params?: { limit?: number; action?: string }) {
  return useQuery({
    queryKey: [...queryKeys.history, params],
    queryFn: () => historyApi.list(params),
  });
}

export function useAcceptSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => suggestionApi.accept(id),
    onSuccess: () => {
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
    onSuccess: () => {
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
    onSuccess: () => {
      queryClient.invalidateQueries({ 
        predicate: (query) => query.queryKey[0] === 'queries' || query.queryKey[0] === 'documents'
      });
    },
  });
}