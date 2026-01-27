'use client';

import { computeWordDiff } from '@/lib/utils';
import type { ChangeType } from '@/types';
import React, { useMemo } from 'react';

/**
 * SectionDiff - Word-level diff viewer for document sections
 * Used in document detail page to show pending/accepted/rejected changes
 */
export function SectionDiff({ original, modified, changeType }: { original: string, modified: string, changeType: ChangeType }) {
  const diff = useMemo(() => computeWordDiff(original, modified), [original, modified]);
  const isRejected = changeType === 'rejected';

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-6 text-[10px] font-bold uppercase tracking-widest">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-red-500/50" />
          <span className="text-red-400 line-through decoration-red-500/50">{isRejected ? 'Proposed (Rejected)' : 'Removed'}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500/50" />
          <span className="text-green-400 underline decoration-green-500/50">{isRejected ? 'Kept' : 'Added'}</span>
        </div>
      </div>

      <div className="font-mono text-sm border border-white/5 rounded-2xl p-6 bg-black/30 leading-relaxed whitespace-pre-wrap text-slate-300 shadow-inner">
        {diff.map((segment, idx) => {
          if (segment.type === 'unchanged') return <span key={idx}>{segment.text}</span>;
          if (segment.type === 'added') return (
            <span key={idx} className="bg-green-500/20 text-green-300 px-0.5 rounded underline decoration-green-500/50 underline-offset-4 font-bold">
              {segment.text}
            </span>
          );
          if (segment.type === 'removed') return (
            <span key={idx} className="bg-red-500/20 text-red-300 px-0.5 rounded line-through decoration-red-500/50 font-bold">
              {segment.text}
            </span>
          );
          return null;
        })}
      </div>

      <details className="group">
        <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-300 select-none transition-colors">View side-by-side comparison</summary>
        <div className="grid grid-cols-2 gap-4 mt-4 animate-[slideUpFade_0.3s_ease_both]">
          <div className="space-y-2">
            <span className="text-[9px] uppercase tracking-widest text-red-400/60 font-bold ml-2">Original State</span>
            <div className="font-mono text-[11px] border border-red-500/10 rounded-xl p-4 bg-red-500/[0.02] text-slate-400 whitespace-pre-wrap max-h-[300px] overflow-y-auto no-scrollbar">{original}</div>
          </div>
          <div className="space-y-2">
            <span className="text-[9px] uppercase tracking-widest text-green-400/60 font-bold ml-2">Proposed State</span>
            <div className="font-mono text-[11px] border border-green-500/10 rounded-xl p-4 bg-green-500/[0.02] text-slate-300 whitespace-pre-wrap max-h-[300px] overflow-y-auto no-scrollbar">{modified}</div>
          </div>
        </div>
      </details>
    </div>
  );
}