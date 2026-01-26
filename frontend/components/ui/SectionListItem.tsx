'use client';

import React from 'react';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatRelativeTimeUnique } from '@/lib/utils'; 
import type { Section, ChangeType } from '@/types';

export function SectionListItem({ section, isSelected, onClick }: { section: Section, isSelected: boolean, onClick: () => void }) {
  const getBadgeStyles = (type: ChangeType) => {
    switch (type) {
      case 'pending': return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      case 'accepted': return 'bg-green-500/20 text-green-300 border-green-500/30';
      case 'rejected': return 'bg-red-500/20 text-red-300 border-red-500/30';
      default: return 'bg-white/10 text-slate-400 border-white/10';
    }
  };

  return (
    <button
      onClick={onClick}
      className={cn("w-full text-left px-6 py-5 transition-all relative", isSelected ? "bg-white/[0.08]" : "hover:bg-white/[0.04]")}
    >
      {isSelected && <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary-500 shadow-[0_0_10px_rgba(14,165,233,0.5)]" />}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm text-slate-200 truncate">{section.section_title || 'Untitled Section'}</div>
          <div className="flex items-center gap-3 mt-2">
            <span className={cn("text-[9px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full border", getBadgeStyles(section.change_type))}>{section.change_type}</span>
            {section.changed_at && <span className="text-xs text-slate-500 font-light">{formatRelativeTimeUnique(section.changed_at)}</span>}
          </div>
        </div>
        <ChevronRight className={cn("h-4 w-4 mt-1 transition-colors", isSelected ? 'text-white' : 'text-slate-600')} />
      </div>
    </button>
  );
}