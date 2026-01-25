'use client';

import { useState } from 'react';
import { Send } from 'lucide-react';
import { Button } from '../ui';
import { cn } from '@/lib/utils';

const EXAMPLES = [
  'Update all references from "Runner" to "AgentRunner"',
  'Add deprecation notice to the old API endpoints',
  'Update code examples to use async/await syntax',
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
            'w-full rounded-lg border bg-background px-4 py-3 text-sm',
            'placeholder:text-muted-foreground resize-none',
            'focus:outline-none focus:ring-2 focus:ring-primary-500',
            'disabled:opacity-50'
          )}
        />
        <div className="flex justify-end">
          <Button type="submit" disabled={!query.trim() || isLoading} isLoading={isLoading}>
            <Send className="mr-2 h-4 w-4" />
            Analyze
          </Button>
        </div>
      </form>

      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">Try an example:</p>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((example, i) => (
            <button
              key={i}
              onClick={() => setQuery(example)}
              disabled={isLoading}
              className="rounded-full border px-3 py-1 text-xs hover:bg-accent disabled:opacity-50"
            >
              {example.length > 35 ? example.slice(0, 35) + '...' : example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
