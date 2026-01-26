'use client';

import { useCallback, useRef, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useQueryStore } from '@/stores';
import { queryKeys } from './useApi';
import { parseSSEChunk } from '@/lib/utils';
import { queryApi } from '@/lib/api';

export function useQueryStream() {
  const queryClient = useQueryClient();
  const abortControllerRef = useRef<AbortController | null>(null);
  
  const { startStreaming, addStep, addSuggestion, setCompleted, setError } = useQueryStore();

  const cleanup = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  const startStream = useCallback(async (queryId: string, useCelery = true) => {
    cleanup();
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    startStreaming();

    try {
      const response = await queryApi.processStream(
        queryId, 
        abortController.signal, 
        useCelery
      );

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      if (!response.body) throw new Error('Response body is null');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        
        const { remainingBuffer, messages } = parseSSEChunk(buffer, chunk);
        buffer = remainingBuffer;

        for (const { event, data } of messages) {
          switch (event) {
            case 'task_started':
              if (data.task_id) startStreaming(data.task_id);
              break;
            case 'status':
              addStep({ type: 'status', data });
              break;
            case 'tool_call':
              addStep({ type: 'tool_call', data });
              break;
            case 'search_complete':
              addStep({ type: 'search', data });
              break;
            case 'suggestion':
              addStep({ type: 'suggestion', data });
              addSuggestion(data);
              break;
            case 'completed':
              setCompleted(data);
              queryClient.invalidateQueries({ queryKey: queryKeys.query(queryId) });
              queryClient.invalidateQueries({ queryKey: queryKeys.queries });
              cleanup(); 
              return;
            case 'error':
              setError(data.error || 'An error occurred');
              cleanup();
              return;
          }
        }
      }
    } catch (error: any) {
      if (error.name !== 'AbortError') {
        console.error('Stream error:', error);
        setError(error.message || 'Connection failed');
      }
      cleanup();
    }
  }, [cleanup, startStreaming, addStep, addSuggestion, setCompleted, setError, queryClient]);

  useEffect(() => cleanup, [cleanup]);

  return { startStream, stopStream: cleanup };
}