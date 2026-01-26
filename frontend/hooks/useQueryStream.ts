'use client';

import { useCallback, useRef, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useQueryStore } from '@/stores';
import { queryKeys } from './useApi';
import type { SSESuggestionEvent, SSECompletedEvent } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';

export function useQueryStream() {
  const queryClient = useQueryClient();
  const abortControllerRef = useRef<AbortController | null>(null);

  const { startStreaming, addStep, addSuggestion, setCompleted, setError } =
    useQueryStore();

  const cleanup = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  const startStream = useCallback(
    async (queryId: string, useCelery = true) => {
      cleanup();
      startStreaming();

      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      try {
        const response = await fetch(
          `${API_BASE}/api/queries/${queryId}/process/stream${useCelery ? '?use_celery=true' : ''}`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            signal: abortController.signal,
          }
        );

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error('Response body is null');
        }

        let buffer = '';
        let currentEvent = '';

        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
            console.log('Stream completed');
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          
          buffer = lines.pop() || '';

          for (const line of lines) {

            if (!line.trim() || line.startsWith(':')) continue;

            if (line.startsWith('event:')) {
              currentEvent = line.slice(6).trim();
              continue;
            }

            if (line.startsWith('data:')) {
              const dataStr = line.slice(5).trim();
              
              try {
                const data = JSON.parse(dataStr);
                console.log('Parsed data:', currentEvent, data);
                
                switch (currentEvent) {
                  case 'task_started':
                    if (data.task_id) {
                      startStreaming(data.task_id);
                    }
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
                    addSuggestion(data as SSESuggestionEvent);
                    break;

                  case 'completed':
                    console.log('Stream completed with data:', data);
                    setCompleted(data as SSECompletedEvent);
                    cleanup();
                    queryClient.invalidateQueries({ queryKey: queryKeys.query(queryId) });
                    queryClient.invalidateQueries({ queryKey: queryKeys.queries });
                    
                    return;

                  case 'error':
                    setError(data.error || 'An error occurred');
                    cleanup();
                    return;

                  default:
                    console.warn('Unknown event type:', currentEvent, data);
                }

                currentEvent = '';
              } catch (e) {
                console.error('Error parsing SSE data:', e, dataStr);
              }
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
    },
    [cleanup, startStreaming, addStep, addSuggestion, setCompleted, setError, queryClient]
  );

  useEffect(() => cleanup, [cleanup]);

  return { startStream, stopStream: cleanup };
}