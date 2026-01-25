'use client';

import { useMemo } from 'react';
import * as Diff from 'diff';
import { cn } from '@/lib/utils';
import { useUIStore } from '@/stores';
import { Button } from '../ui';
import { Columns2, Rows3 } from 'lucide-react';

interface DiffViewerProps {
  original: string;
  modified: string;
}

export function DiffViewer({ original, modified }: DiffViewerProps) {
  const { diffMode, setDiffMode } = useUIStore();
  const diff = useMemo(() => Diff.diffLines(original, modified), [original, modified]);

  return (
    <div className="space-y-2">
      <div className="flex justify-end gap-1">
        <Button variant={diffMode === 'split' ? 'secondary' : 'ghost'} size="sm" onClick={() => setDiffMode('split')}>
          <Columns2 className="h-4 w-4 mr-1" /> Split
        </Button>
        <Button variant={diffMode === 'unified' ? 'secondary' : 'ghost'} size="sm" onClick={() => setDiffMode('unified')}>
          <Rows3 className="h-4 w-4 mr-1" /> Unified
        </Button>
      </div>

      {diffMode === 'split' ? (
        <div className="grid grid-cols-2 gap-0 rounded-lg border overflow-hidden">
          <div className="border-r">
            <div className="bg-muted px-3 py-1 text-xs font-medium text-muted-foreground border-b">Original</div>
            <pre className="p-3 text-sm font-mono overflow-x-auto max-h-80 overflow-y-auto whitespace-pre-wrap">
              {diff.map((part, i) => 
                part.removed ? (
                  <span key={i} className="bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200">{part.value}</span>
                ) : !part.added ? (
                  <span key={i}>{part.value}</span>
                ) : null
              )}
            </pre>
          </div>
          <div>
            <div className="bg-muted px-3 py-1 text-xs font-medium text-muted-foreground border-b">Modified</div>
            <pre className="p-3 text-sm font-mono overflow-x-auto max-h-80 overflow-y-auto whitespace-pre-wrap">
              {diff.map((part, i) => 
                part.added ? (
                  <span key={i} className="bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200">{part.value}</span>
                ) : !part.removed ? (
                  <span key={i}>{part.value}</span>
                ) : null
              )}
            </pre>
          </div>
        </div>
      ) : (
        <div className="rounded-lg border overflow-hidden">
          <pre className="p-3 text-sm font-mono overflow-x-auto max-h-96 overflow-y-auto whitespace-pre-wrap">
            {diff.map((part, i) => (
              <span
                key={i}
                className={cn(
                  part.added && 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200',
                  part.removed && 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200'
                )}
              >
                {part.value}
              </span>
            ))}
          </pre>
        </div>
      )}
    </div>
  );
}
