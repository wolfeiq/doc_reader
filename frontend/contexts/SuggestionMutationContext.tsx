'use client';

import { createContext, useContext, useCallback, useMemo, type ReactNode } from 'react';
import { useAcceptSuggestion, useRejectSuggestion, useUpdateSuggestion } from '@/hooks/useApi';

interface SuggestionMutationContextValue {
  acceptSuggestion: (id: string) => void;
  rejectSuggestion: (id: string) => void;
  saveSuggestion: (id: string, text: string) => void;
  isLoading: boolean;
}

const SuggestionMutationContext = createContext<SuggestionMutationContextValue | null>(null);

export function SuggestionMutationProvider({ children }: { children: ReactNode }) {
  const acceptMutation = useAcceptSuggestion();
  const rejectMutation = useRejectSuggestion();
  const updateMutation = useUpdateSuggestion();

  const acceptSuggestion = useCallback(
    (id: string) => acceptMutation.mutate(id),
    [acceptMutation]
  );

  const rejectSuggestion = useCallback(
    (id: string) => rejectMutation.mutate(id),
    [rejectMutation]
  );

  const saveSuggestion = useCallback(
    (id: string, text: string) => updateMutation.mutate({ id, data: { edited_text: text } }),
    [updateMutation]
  );

  const isLoading = acceptMutation.isPending || rejectMutation.isPending || updateMutation.isPending;

  const value = useMemo(
    () => ({
      acceptSuggestion,
      rejectSuggestion,
      saveSuggestion,
      isLoading,
    }),
    [acceptSuggestion, rejectSuggestion, saveSuggestion, isLoading]
  );

  return (
    <SuggestionMutationContext.Provider value={value}>
      {children}
    </SuggestionMutationContext.Provider>
  );
}

export function useSuggestionMutations() {
  const context = useContext(SuggestionMutationContext);
  if (!context) {
    throw new Error('useSuggestionMutations must be used within a SuggestionMutationProvider');
  }
  return context;
}
