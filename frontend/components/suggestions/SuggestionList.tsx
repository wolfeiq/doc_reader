'use client';

import { useMemo } from 'react';
import { FileText } from 'lucide-react';
import { SuggestionCard } from './SuggestionCard';
import type { Suggestion, SuggestionListProps } from '@/types';


export function SuggestionList({ suggestions, onAccept, onReject, onSave, isLoading }: SuggestionListProps) {

  const grouped = useMemo(() => {
    const groups: Record<string, Suggestion[]> = {};
    suggestions.forEach((s) => {
      const path = s.file_path || 'Unknown';
      if (!groups[path]) groups[path] = [];
      groups[path].push(s);
    });
    return groups;
  }, [suggestions]);

  if (!suggestions.length) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <FileText className="h-12 w-12 text-muted-foreground mb-4" />
        <h3 className="text-lg font-medium">No suggestions yet</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Start a query to generate documentation update suggestions
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([path, items]) => (
        <div key={path} className="space-y-3">
          <h3 className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <FileText className="h-4 w-4" /> {path}
          </h3>
          <div className="space-y-4">
            {items.map((s) => (
              <SuggestionCard key={s.id} suggestion={s} onAccept={onAccept} onReject={onReject} onSave={onSave} isLoading={isLoading} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
