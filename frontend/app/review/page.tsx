'use client';

import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { useQueryDetail, useAcceptSuggestion, useRejectSuggestion, useUpdateSuggestion } from '@/hooks';
import { SuggestionList } from '@/components/suggestions';
import { Button } from '@/components/ui';

export default function ReviewPage() {
  const searchParams = useSearchParams();
  const queryId = searchParams.get('query');

  const { data: query, isLoading, error } = useQueryDetail(queryId || '');
  const acceptMutation = useAcceptSuggestion();
  const rejectMutation = useRejectSuggestion();
  const updateMutation = useUpdateSuggestion();

  if (!queryId) {
    return (
      <div className="max-w-4xl mx-auto text-center py-12">
        <h2 className="text-xl font-medium">No query selected</h2>
        <p className="text-muted-foreground mt-2">Start a new query or select one from recent queries.</p>
        <Link href="/"><Button className="mt-4"><ArrowLeft className="h-4 w-4 mr-2" />Go to Query</Button></Link>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto text-center py-12">
        <h2 className="text-xl font-medium text-red-600">Error loading query</h2>
        <Link href="/"><Button className="mt-4" variant="outline"><ArrowLeft className="h-4 w-4 mr-2" />Go Back</Button></Link>
      </div>
    );
  }

  const isActionLoading = acceptMutation.isPending || rejectMutation.isPending || updateMutation.isPending;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <Link href="/" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-2">
          <ArrowLeft className="h-4 w-4" /> Back to Query
        </Link>
        <h1 className="text-2xl font-bold">Review Suggestions</h1>
        <p className="text-muted-foreground mt-1 truncate">{query?.query_text}</p>
      </div>

      <SuggestionList
        suggestions={query?.suggestions || []}
        onAccept={(id) => acceptMutation.mutate(id)}
        onReject={(id) => rejectMutation.mutate(id)}
        onSave={(id, text) => updateMutation.mutate({ id, data: { edited_text: text } })}
        isLoading={isActionLoading}
      />
    </div>
  );
}
