import { useQuery } from '@tanstack/react-query';
import { documentApi } from '@/lib/api';
import type { DocumentPreview } from '@/types';

export function useDocumentPreview(documentId: string) {
  return useQuery<DocumentPreview>({
    queryKey: ['document-preview', documentId],
    queryFn: () => documentApi.preview(documentId),
    enabled: !!documentId,
  });
}