import type {
  Query,
  QueryDetail,
  QueryCreate,
  Suggestion,
  SuggestionUpdate,
  SuggestionActionResponse,
  DocumentListItem,
  DocumentPreview,
  EditHistory,
} from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081/api';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
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
    return null as T;
  }

  return response.json();
}

export const queryApi = {
  list: (params?: { skip?: number; limit?: number; status?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.skip) searchParams.set('skip', String(params.skip));
    if (params?.limit) searchParams.set('limit', String(params.limit));
    if (params?.status) searchParams.set('status', params.status);
    const query = searchParams.toString();
    return fetchApi<Query[]>(`/queries/${query ? `?${query}` : ''}`);
  },

  get: (id: string) => fetchApi<QueryDetail>(`/queries/${id}`),

  create: (data: QueryCreate) =>
    fetchApi<Query>('/queries/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    fetchApi<void>(`/queries/${id}`, { method: 'DELETE' }),
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
    const searchParams = new URLSearchParams();
    if (params?.skip) searchParams.set('skip', String(params.skip));
    if (params?.limit) searchParams.set('limit', String(params.limit));
    const query = searchParams.toString();
    return fetchApi<DocumentListItem[]>(`/documents/${query ? `?${query}` : ''}`);
  },

  get: (id: string) => fetchApi<Document>(`/documents/${id}`), // Add this line

  preview: (id: string) => fetchApi<DocumentPreview>(`/documents/${id}/preview`),

  delete: (id: string) =>
    fetchApi<void>(`/documents/${id}`, { method: 'DELETE' }),
};


export const historyApi = {
  list: (params?: {
    skip?: number;
    limit?: number;
    document_id?: string;
    action?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.skip) searchParams.set('skip', String(params.skip));
    if (params?.limit) searchParams.set('limit', String(params.limit));
    if (params?.document_id) searchParams.set('document_id', params.document_id);
    if (params?.action) searchParams.set('action', params.action);
    const query = searchParams.toString();
    return fetchApi<EditHistory[]>(`/history/${query ? `?${query}` : ''}`);
  },
};


export { ApiError };
