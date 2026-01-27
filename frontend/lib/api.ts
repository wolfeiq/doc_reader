import type {
  Query,
  QueryDetail,
  QueryCreate,
  Suggestion,
  SuggestionUpdate,
  SuggestionActionResponse,
  DocumentListItem,
  DocumentPreviewUnique,
  EditHistory,
  UserAction,
  Document as DocumentType,
} from '@/types';
import { API_BASE, validateEnv } from './env';

// Validate env on first import (client-side only)
validateEnv();

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  console.log('FETCHING URL:', url);
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new ApiError(response.status, error || response.statusText);
  }

  if (response.status === 204) {
    return undefined as unknown as T;
  }

  return response.json();
}

function buildQueryString(params: Record<string, string | number | undefined>): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      searchParams.set(key, String(value));
    }
  });
  const query = searchParams.toString();
  return query ? `?${query}` : '';
}

export const queryApi = {
  list: (params?: { skip?: number; limit?: number; status?: string }) => {
    const query = buildQueryString(params || {});
    return fetchApi<Query[]>(`/queries${query}`);
  },

  get: (id: string) => fetchApi<QueryDetail>(`/queries/${id}`),

  create: (data: QueryCreate) =>
    fetchApi<Query>('/queries/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    fetchApi<void>(`/queries/${id}`, { method: 'DELETE' }),

  processStream: (id: string, signal: AbortSignal, useCelery = true) => {
    const query = buildQueryString({ 
      use_celery: useCelery ? 'true' : undefined 
    });
    return fetch(`${API_BASE}/queries/${id}/process/stream${query}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      signal,
    });
  },
};

export const suggestionApi = {
  get: (id: string) => fetchApi<Suggestion>(`/suggestions/${id}`),

  update: (id: string, data: SuggestionUpdate) =>
    fetchApi<Suggestion>(`/suggestions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  accept: (id: string) =>
    fetchApi<SuggestionActionResponse>(`/suggestions/${id}/accept`, {
      method: 'POST',
    }),

  reject: (id: string) =>
    fetchApi<SuggestionActionResponse>(`/suggestions/${id}/reject`, {
      method: 'POST',
    }),
};

export const documentApi = {
  list: (params?: { skip?: number; limit?: number }) => {
    const query = buildQueryString(params || {});
    return fetchApi<DocumentListItem[]>(`/documents${query}`);
  },

  get: (id: string) => fetchApi<DocumentType>(`/documents/${id}`),

  preview: (id: string) => fetchApi<DocumentPreviewUnique>(`/documents/${id}/preview`),

  delete: (id: string) =>
    fetchApi<void>(`/documents/${id}`, { method: 'DELETE' }),
};

export const historyApi = {
  list: (params?: {
    skip?: number;
    limit?: number;
    document_id?: string;
    action?: UserAction;
  }) => {
    const query = buildQueryString(params || {});
    return fetchApi<EditHistory[]>(`/history${query}`);
  },
};

export { ApiError };