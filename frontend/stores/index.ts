'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { SSESuggestionEvent, SSECompletedEvent } from '@/types';

// =============================================================================
// UI Store - Theme, Sidebar, Modals
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
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      diffMode: 'split',
      setDiffMode: (diffMode) => set({ diffMode }),
      shortcutsModalOpen: false,
      setShortcutsModalOpen: (shortcutsModalOpen) => set({ shortcutsModalOpen }),
    }),
    {
      name: 'pluno-ui',
      partialize: (state) => ({
        theme: state.theme,
        sidebarOpen: state.sidebarOpen,
        diffMode: state.diffMode,
      }),
    }
  )
);

// =============================================================================
// Query Store - Streaming State
// =============================================================================

export type StreamingStatus = 'idle' | 'connecting' | 'streaming' | 'completed' | 'error';

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

export const useQueryStore = create<QueryState>((set) => ({
  currentQueryId: null,
  currentQueryText: '',
  streamingStatus: 'idle',
  taskId: null,
  steps: [],
  incomingSuggestions: [],
  error: null,
  completionData: null,

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

  reset: () =>
    set({
      currentQueryId: null,
      currentQueryText: '',
      streamingStatus: 'idle',
      taskId: null,
      steps: [],
      incomingSuggestions: [],
      error: null,
      completionData: null,
    }),
}));

// =============================================================================
// Suggestion Store - Selection & Editing
// =============================================================================

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
