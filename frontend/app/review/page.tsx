'use client';

import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Loader2, Sparkles } from 'lucide-react';
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
      <div className="max-w-4xl mx-auto flex flex-col items-center justify-center py-24 text-center">
        <div className="w-16 h-16 rounded-3xl bg-white/5 flex items-center justify-center mb-6 border border-white/10 shadow-2xl">
          <Sparkles className="h-8 w-8 text-slate-700 opacity-50" />
        </div>
        <h2 className="text-2xl font-heading text-slate-100 mb-2">No Query Selected</h2>
        <p className="text-slate-400 font-light max-w-xs mx-auto mb-8">
          Start a new documentation analysis or select one from your history.
        </p>
        <Link href="/">
          <Button variant="default" className="rounded-full px-8 py-6">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Go to Assistant
          </Button>
        </Link>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary-500/50" />
        <p className="text-slate-500 font-light italic">Generating suggestions...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto flex flex-col items-center justify-center py-24 text-center">
        <h2 className="text-xl font-heading text-red-400 mb-6">Error loading analysis</h2>
        <Link href="/">
          <Button variant="outline" className="rounded-full px-8 py-6 border-white/10 hover:bg-white/5">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Go Back
          </Button>
        </Link>
      </div>
    );
  }

  const isActionLoading = acceptMutation.isPending || rejectMutation.isPending || updateMutation.isPending;

  return (
    <div className="max-w-5xl mx-auto space-y-10 py-10 px-4">
      <div className="text-center space-y-4 animate-[slideUpFade_0.6s_ease_both]">
        <Link 
          href="/" 
          className="inline-flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500 hover:text-primary-400 transition-colors mb-2"
        >
          <ArrowLeft className="h-3 w-3" /> Back to Analysis
        </Link>
        
        <h1 className="text-slate-100 flex items-center justify-center gap-3">
          Review Suggestions
        </h1>
        
        {query?.query_text && (
          <div className="glass-panel inline-block px-6 py-3 rounded-2xl border border-white/5 shadow-xl">
             <p className="text-sm text-slate-400 font-light italic leading-relaxed">
              &quot;{query.query_text}&quot;
            </p>
          </div>
        )}
      </div>

      <div className="animate-[slideUpFade_0.8s_ease_both] delay-200">
        <SuggestionList
          suggestions={query?.suggestions || []}
          onAccept={(id) => acceptMutation.mutate(id)}
          onReject={(id) => rejectMutation.mutate(id)}
          onSave={(id, text) => updateMutation.mutate({ id, data: { edited_text: text } })}
          isLoading={isActionLoading}
        />
      </div>
    </div>
  );
}