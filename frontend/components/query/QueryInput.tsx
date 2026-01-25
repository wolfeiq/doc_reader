'use client';

import { useState } from 'react';
import { Send } from 'lucide-react';
import { Button } from '../ui';
import { cn } from '@/lib/utils';

const EXAMPLES = [
  'Update all references from "Runner" to "AgentRunner"',
  'Add deprecation notice to the old API endpoints',
  'Update code examples to use async/await syntax',
  'Generate a quick start guide for new developers',
];

interface QueryInputProps {
  onSubmit: (query: string) => void;
  isLoading?: boolean;
}

export function QueryInput({ onSubmit, isLoading }: QueryInputProps) {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onSubmit(query.trim());
    }
  };

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="space-y-4">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Describe the documentation update you need..."
          disabled={isLoading}
          rows={4}
          className={cn(
            'w-full rounded-lg border bg-background py-6 px-6 text-sm',
            'placeholder:text-muted-foreground/60 resize-none',
            'focus:outline-none focus:ring-2 focus:ring-primary-500',
            'disabled:opacity-50'
          )}
        />
        <div className="flex justify-center">
          <Button type="submit" disabled={!query.trim() || isLoading} isLoading={isLoading}>
            <Send className="mr-2 h-4 w-4" />
            Analyze
          </Button>
        </div>
      </form>

      <div className="space-y-3 px-4"> 
        <span className="text-[9px] md:text-[10px] uppercase tracking-[0.2em] text-primary-400/60 font-bold block">
          Try an Example
        </span>
        
        <div className="flex items-center gap-2 overflow-x-auto pb-2 no-scrollbar">
          {EXAMPLES.map((example, i) => (
            <button
              key={i}
              onClick={() => setQuery(example)}
              disabled={isLoading}
              className="shrink-0 rounded-full border px-4 py-2 text-xs hover:bg-accent hover:text-accent-foreground transition-colors disabled:opacity-50 whitespace-nowrap"
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}