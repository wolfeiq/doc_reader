'use client';

import { useRouter } from 'next/navigation';
import { useQueryStore } from '@/stores';
import { useCreateQuery, useQueryStream } from '@/hooks';
import { QueryInput, StreamingProgress, RecentQueries } from '@/components/query';
import { Button } from '@/components/ui';
import { cn } from '@/lib/utils';

export default function QueryPage() {
  const router = useRouter();
  const { setCurrentQuery, streamingStatus, currentQueryId } = useQueryStore();
  const createQuery = useCreateQuery();
  const { startStream } = useQueryStream();

  const handleSubmit = async (queryText: string) => {
    const query = await createQuery.mutateAsync({ query_text: queryText }); 
    setCurrentQuery(query.id, queryText);
    startStream(query.id, true);
  };

  const isProcessing = streamingStatus === 'streaming';
  const isCompleted = streamingStatus === 'completed';

  return (
    <div className="w-full max-w-3xl mx-auto py-10 md:py-20 flex flex-col items-center">
      <header className="mb-8 md:mb-16 text-center space-y-4 px-2">
        <h1 className="text-3xl md:text-6xl text-slate-100 font-medium leading-tight">
          Documentation Assistant
        </h1>
        <p className="text-base md:text-lg text-slate-400/70 font-light max-w-lg mx-auto">
          AI-driven dependency analysis for your documentation suite.
        </p>
      </header>

      <div className="w-full space-y-6">
        <div className={cn(
          "transition-all duration-500 rounded-2xl md:rounded-3xl glass-panel p-1.5 md:p-2 shadow-2xl",
          isProcessing ? "opacity-40" : "opacity-100"
        )}>
          <QueryInput 
            onSubmit={handleSubmit} 
            isLoading={createQuery.isPending || isProcessing} 
          />
        </div>

        {!isProcessing && !isCompleted && (
          <div className="flex justify-center animate-[slideUpFade_1s_ease_both] delay-200 px-2">
            <div className="px-4 py-2.5 md:py-2 rounded-2xl md:rounded-full bg-white/[0.01] shadow-[inset_0_1px_1px_rgba(255,255,255,0.03)] border border-white/[0.02] flex flex-col md:flex-row items-center gap-2 md:gap-3 text-center md:text-left">
              <span className="text-[9px] md:text-[10px] uppercase tracking-[0.2em] text-primary-400/60 font-bold">Example</span>
              <p className="text-xs md:text-sm text-slate-500 italic leading-relaxed">
                "Update all authentication sections to reflect OAuth2 flow."
              </p>
            </div>
          </div>
        )}

        <div className="flex flex-col items-center pt-4 w-full">
          <StreamingProgress />

          {isCompleted && currentQueryId && (
            <Button 
              className="w-full md:w-auto mt-4 rounded-full px-10 py-7 md:py-6 text-md font-heading bg-primary-600 hover:bg-primary-500 shadow-lg active:scale-95 transition-all"
              onClick={() => router.push(`/review?query=${currentQueryId}`)}
            >
              Review Suggestions →
            </Button>
          )}
        </div>
      </div>

      {!isProcessing && !isCompleted && (
        <div className="w-full mt-10 md:mt-16 opacity-40 hover:opacity-90 transition-opacity duration-500">
          <RecentQueries />
        </div>
      )}
    </div>
  );
}