'use client';

import { Search, FileText, Lightbulb, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useStreamingProgress } from '@/stores';
import { Card, Badge } from '../ui';

export function StreamingProgress() {
  const { status: streamingStatus, steps, suggestions: incomingSuggestions, error, completionData } = useStreamingProgress();

  if (streamingStatus === 'idle') return null;

  const searches = steps.filter((s) => s.type === 'search').length;
  const toolCalls = steps.filter((s) => s.type === 'tool_call').length;

  return (
    <Card>
      <div className="flex items-center gap-3 border-b p-4">
        {streamingStatus === 'streaming' && (
          <Loader2 className="h-5 w-5 text-primary-500 animate-spin" />
        )}
        {streamingStatus === 'completed' && (
          <CheckCircle className="h-5 w-5 text-green-500" />
        )}
        {streamingStatus === 'error' && (
          <AlertCircle className="h-5 w-5 text-red-500" />
        )}
        <span className="font-medium">
          {streamingStatus === 'streaming' && 'Analyzing...'}
          {streamingStatus === 'completed' && 'Completed'}
          {streamingStatus === 'error' && 'Error'}
        </span>
        {completionData && (
          <Badge variant="success" className="ml-auto">
            {completionData.total_suggestions} suggestions
          </Badge>
        )}
      </div>

      <div className="p-4 space-y-3">
        <div className="flex gap-4 text-sm">
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            <span>{searches} searches</span>
          </div>
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <span>{toolCalls} operations</span>
          </div>
          <div className="flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-muted-foreground" />
            <span>{incomingSuggestions.length} suggestions</span>
          </div>
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        {streamingStatus === 'streaming' && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="flex gap-1">
              <span className="typing-dot h-2 w-2 rounded-full bg-primary-500" />
              <span className="typing-dot h-2 w-2 rounded-full bg-primary-500" />
              <span className="typing-dot h-2 w-2 rounded-full bg-primary-500" />
            </span>
            <span>Processing...</span>
          </div>
        )}

        {incomingSuggestions.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase">Found</p>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {incomingSuggestions.map((s) => (
                <div key={s.suggestion_id} className="flex items-center gap-2 rounded-lg bg-muted/50 p-2 text-sm">
                  <Lightbulb className="h-4 w-4 text-yellow-500" />
                  <div className="flex-1 min-w-0">
                    <p className="truncate font-medium">{s.section_title || 'Untitled'}</p>
                    <p className="truncate text-xs text-muted-foreground">{s.file_path}</p>
                  </div>
                  <Badge variant={s.confidence >= 0.9 ? 'success' : s.confidence >= 0.7 ? 'warning' : 'default'}>
                    {Math.round(s.confidence * 100)}%
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
