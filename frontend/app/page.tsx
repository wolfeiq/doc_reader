'use client';

import { useRouter } from 'next/navigation';
import { useQueryStore } from '@/stores';
import { useCreateQuery, useQueryStream } from '@/hooks';
import { QueryInput, StreamingProgress, RecentQueries } from '@/components/query';
import { Button } from '@/components/ui';

export default function QueryPage() {
  console.log('🔵 QueryPage rendered');
  
  const router = useRouter();
  const { setCurrentQuery, streamingStatus, currentQueryId } = useQueryStore();
  const createQuery = useCreateQuery();
  const { startStream } = useQueryStream();

  const handleSubmit = async (queryText: string) => {
    console.log('🟢 handleSubmit called with:', queryText);
    
    try {
      const query = await createQuery.mutateAsync({ query_text: queryText });
      console.log('🟢 Query created:', query);
      
      setCurrentQuery(query.id, queryText);
      startStream(query.id, true);
    } catch (error) {
      console.error('🔴 Error:', error);
    }
  };

  const isProcessing = streamingStatus === 'streaming';

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Add test button */}
      <button 
        onClick={() => {
          console.log('🟢 TEST BUTTON CLICKED!');
          alert('Test button works!');
        }}
        style={{ 
          background: 'red', 
          color: 'white', 
          padding: '10px 20px',
          border: 'none',
          cursor: 'pointer'
        }}
      >
        TEST BUTTON - CLICK ME
      </button>

      <div>
        <h1 className="text-3xl font-bold">Documentation Update Assistant</h1>
        <p className="text-muted-foreground mt-2">
          Describe the changes you need, and I&apos;ll analyze your documentation to suggest updates.
        </p>
      </div>

      <QueryInput onSubmit={handleSubmit} isLoading={createQuery.isPending || isProcessing} />

      <StreamingProgress />

      {streamingStatus === 'completed' && currentQueryId && (
        <div className="flex justify-center">
          <Button onClick={() => router.push(`/review?query=${currentQueryId}`)}>
            Review Suggestions →
          </Button>
        </div>
      )}

      {!isProcessing && streamingStatus !== 'completed' && <RecentQueries />}
    </div>
  );
}