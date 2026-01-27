/**
 * Zustand State Management
 * ========================
 *
 * This module contains all Zustand stores for the application.
 * We use Zustand instead of Redux because:
 * - Simpler API with less boilerplate
 * - No context providers needed (direct imports)
 * - Built-in TypeScript support
 * - Lightweight bundle size (~1KB)
 *
 * Store Organization:
 * -------------------
 * 1. UIStore - Theme, sidebar, display preferences (persisted)
 * 2. QueryStore - Current query processing state (ephemeral)
 * 3. SuggestionStore - Suggestion selection/editing state (ephemeral)
 *
 * Why Separate Stores?
 * --------------------
 * Splitting by domain prevents unnecessary re-renders.
 * Components only subscribe to the stores they need.
 *
 * Performance Pattern - Selectors:
 * --------------------------------
 * We export selector hooks instead of using the store directly.
 * This prevents re-renders when unrelated state changes:
 *
 *   BAD:  const { theme, sidebarOpen } = useUIStore();
 *         // Re-renders when ANY UIStore property changes
 *
 *   GOOD: const theme = useTheme();
 *         // Only re-renders when theme changes
 *
 * Production Considerations:
 * --------------------------
 * - Add Zustand DevTools for debugging (zustand/middleware)
 * - Consider immer middleware for complex state updates
 * - Add state migration for persisted stores (version field)
 * - Consider splitting streaming state to separate store if it grows
 */

'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { SSESuggestionEvent, SSECompletedEvent } from '@/types';

// =============================================================================
// UI Store - User interface preferences (persisted to localStorage)
// =============================================================================

interface UIState {
  theme: 'light' | 'dark' | 'system';
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  diffMode: 'split' | 'unified';
  setDiffMode: (mode: 'split' | 'unified') => void;
  shortcutsModalOpen: boolean;
  setShortcutsModalOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      theme: 'system',
      setTheme: (theme) => set({ theme }),
      sidebarOpen: true,
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      diffMode: 'split',
      setDiffMode: (mode) => set({ diffMode: mode }),
      shortcutsModalOpen: false,
      setShortcutsModalOpen: (open) => set({ shortcutsModalOpen: open }),
    }),
    {
      name: 'ui-storage',
      partialize: (state) => ({
        theme: state.theme,
        sidebarOpen: state.sidebarOpen,
        diffMode: state.diffMode,
      }),
    }
  )
);


// =============================================================================
// Query Store - Query processing and streaming state (ephemeral)
// =============================================================================
// This store manages the real-time state during query processing.
// It receives updates from SSE events and drives the progress UI.

/** Current state of the SSE streaming connection */
export type StreamingStatus = 'idle' | 'connecting' | 'streaming' | 'completed' | 'error';

/**
 * A step in the query processing pipeline.
 * Displayed in the StreamingProgress component.
 */
interface StreamingStep {
  type: 'status' | 'tool_call' | 'search' | 'suggestion';
  timestamp: Date;
  data: Record<string, unknown>;
}

interface QueryState {
  currentQueryId: string | null;
  currentQueryText: string;
  streamingStatus: StreamingStatus;
  taskId: string | null;
  steps: StreamingStep[];
  incomingSuggestions: SSESuggestionEvent[];
  error: string | null;
  completionData: SSECompletedEvent | null;
  
  setCurrentQuery: (id: string | null, text?: string) => void;
  startStreaming: (taskId?: string) => void;
  addStep: (step: Omit<StreamingStep, 'timestamp'>) => void;
  addSuggestion: (suggestion: SSESuggestionEvent) => void;
  setCompleted: (data: SSECompletedEvent) => void;
  setError: (error: string) => void;
  reset: () => void;
}

const initialQueryState = {
  currentQueryId: null,
  currentQueryText: '',
  streamingStatus: 'idle' as StreamingStatus,
  taskId: null,
  steps: [],
  incomingSuggestions: [],
  error: null,
  completionData: null,
};

export const useQueryStore = create<QueryState>((set) => ({
  ...initialQueryState,

  setCurrentQuery: (id, text = '') =>
    set({
      currentQueryId: id,
      currentQueryText: text,
      streamingStatus: 'idle',
      steps: [],
      incomingSuggestions: [],
      error: null,
      completionData: null,
    }),

  startStreaming: (taskId) =>
    set({
      streamingStatus: 'streaming',
      taskId: taskId || null,
      steps: [],
      incomingSuggestions: [],
      error: null,
    }),

  addStep: (step) =>
    set((state) => ({
      steps: [...state.steps, { ...step, timestamp: new Date() }],
    })),

  addSuggestion: (suggestion) =>
    set((state) => ({
      incomingSuggestions: [...state.incomingSuggestions, suggestion],
    })),

  setCompleted: (data) =>
    set({
      streamingStatus: 'completed',
      completionData: data,
    }),

  setError: (error) =>
    set({
      streamingStatus: 'error',
      error,
    }),

  reset: () => set(initialQueryState),
}));


interface SuggestionState {
  selectedId: string | null;
  editingId: string | null;
  editedText: string;
  
  setSelected: (id: string | null) => void;
  startEditing: (id: string, text: string) => void;
  setEditedText: (text: string) => void;
  cancelEditing: () => void;
}

export const useSuggestionStore = create<SuggestionState>((set) => ({
  selectedId: null,
  editingId: null,
  editedText: '',

  setSelected: (id) => set({ selectedId: id }),
  startEditing: (id, text) => set({ editingId: id, editedText: text }),
  setEditedText: (text) => set({ editedText: text }),
  cancelEditing: () => set({ editingId: null, editedText: '' }),
}));


// ============================================
// SELECTORS - Use these to prevent unnecessary re-renders
// ============================================

// UI Store Selectors
export const useTheme = () => useUIStore((s) => s.theme);
export const useSetTheme = () => useUIStore((s) => s.setTheme);
export const useSidebarOpen = () => useUIStore((s) => s.sidebarOpen);
export const useToggleSidebar = () => useUIStore((s) => s.toggleSidebar);
export const useDiffMode = () => useUIStore((s) => s.diffMode);
export const useSetDiffMode = () => useUIStore((s) => s.setDiffMode);
export const useShortcutsModal = () => useUIStore((s) => ({
  isOpen: s.shortcutsModalOpen,
  setOpen: s.setShortcutsModalOpen,
}));

// Query Store Selectors (excluding streaming internals)
export const useCurrentQueryId = () => useQueryStore((s) => s.currentQueryId);
export const useCurrentQueryText = () => useQueryStore((s) => s.currentQueryText);
export const useStreamingStatus = () => useQueryStore((s) => s.streamingStatus);
export const useStreamingError = () => useQueryStore((s) => s.error);
export const useCompletionData = () => useQueryStore((s) => s.completionData);
export const useIncomingSuggestions = () => useQueryStore((s) => s.incomingSuggestions);
export const useStreamingSteps = () => useQueryStore((s) => s.steps);

// Combined selectors for common patterns
export const useStreamingProgress = () => useQueryStore((s) => ({
  status: s.streamingStatus,
  steps: s.steps,
  suggestions: s.incomingSuggestions,
  error: s.error,
  completionData: s.completionData,
}));

// Query Store Actions
export const useQueryActions = () => useQueryStore((s) => ({
  setCurrentQuery: s.setCurrentQuery,
  startStreaming: s.startStreaming,
  addStep: s.addStep,
  addSuggestion: s.addSuggestion,
  setCompleted: s.setCompleted,
  setError: s.setError,
  reset: s.reset,
}));

// Suggestion Store Selectors
export const useSelectedSuggestionId = () => useSuggestionStore((s) => s.selectedId);
export const useEditingSuggestionId = () => useSuggestionStore((s) => s.editingId);
export const useEditedText = () => useSuggestionStore((s) => s.editedText);

// Combined selector for editing state
export const useSuggestionEditor = () => useSuggestionStore((s) => ({
  editingId: s.editingId,
  editedText: s.editedText,
  startEditing: s.startEditing,
  setEditedText: s.setEditedText,
  cancelEditing: s.cancelEditing,
}));

// Suggestion Store Actions
export const useSuggestionActions = () => useSuggestionStore((s) => ({
  setSelected: s.setSelected,
  startEditing: s.startEditing,
  setEditedText: s.setEditedText,
  cancelEditing: s.cancelEditing,
}));