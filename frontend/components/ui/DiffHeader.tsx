'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { Section } from '@/types';
import { AlertCircle, Check, X } from 'lucide-react';


export function DiffHeader({ section }: { section: Section }) {
  const styles = {
    pending: 'bg-amber-500/10 text-amber-200 border-amber-500/20',
    accepted: 'bg-green-500/10 text-green-200 border-green-500/20',
    rejected: 'bg-red-500/10 text-red-200 border-red-500/20',
    none: 'bg-white/5 text-slate-200 border-white/10'
  };
  return (
    <div className={cn("px-6 py-4 border-b flex items-center justify-between", styles[section.change_type as keyof typeof styles])}>
      <div className="flex items-center gap-3">
        {section.change_type === 'pending' && <AlertCircle className="h-4 w-4" />}
        {section.change_type === 'accepted' && <Check className="h-4 w-4" />}
        {section.change_type === 'rejected' && <X className="h-4 w-4" />}
        <h3 className="font-medium text-sm">{section.section_title || 'Untitled Section'}</h3>
      </div>
      <span className="text-[10px] font-bold uppercase tracking-[0.2em] opacity-60">{section.change_type}</span>
    </div>
  );
}