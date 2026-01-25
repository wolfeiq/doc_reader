'use client';

import { useState } from 'react';
import { History, Check, X, Pencil, RotateCcw, Loader2, FileText, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatDate } from '@/lib/utils';
import { useHistory } from '@/hooks';
import { DiffViewer } from '@/components/suggestions';
import type { EditHistory, UserAction } from '@/types';

const ACTION_CONFIG: Record<UserAction, { icon: typeof Check; label: string; color: string; bg: string }> = {
  ACCEPTED: { icon: Check, label: 'Accepted', color: 'text-green-400', bg: 'bg-green-500/10 border-green-500/20' },
  REJECTED: { icon: X, label: 'Rejected', color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20' },
  EDITED: { icon: Pencil, label: 'Edited', color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/20' },
  REVERTED: { icon: RotateCcw, label: 'Reverted', color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/20' },
};

export default function HistoryPage() {
  const [filter, setFilter] = useState<UserAction | 'all'>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: history, isLoading } = useHistory({
    limit: 50,
    action: filter === 'all' ? undefined : filter,
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4 bg-transparent">
        <Loader2 className="h-10 w-10 animate-spin text-primary-500/50" />
        <p className="text-slate-500 font-light italic">Retrieving edit records...</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-10 py-10 px-4">
      <div className="text-center space-y-4">
        <h1 className="text-slate-100 flex items-center justify-center gap-3">
          <History className="h-8 w-8 text-primary-400/60" /> Edit History
        </h1>
        <p className="text-lg text-slate-400/70 font-light max-w-lg mx-auto leading-relaxed">
          A comprehensive ledger of all AI-suggested changes and manual overrides.
        </p>
      </div>

      <div className="glass-panel rounded-3xl overflow-hidden shadow-2xl border border-white/10">
        {!history?.length ? (
          <div className="py-24 text-center">
            <History className="h-12 w-12 text-slate-700 mx-auto mb-4 opacity-20" />
            <p className="text-slate-500 italic">No historical records found for this filter.</p>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {history.map((item) => {
              const actionKey = item.user_action.toUpperCase() as UserAction;
              const config = ACTION_CONFIG[actionKey];
              const Icon = config.icon;
              const isExpanded = selectedId === item.id;

              return (
                <div key={item.id} className={cn(
                  "transition-colors duration-300",
                  isExpanded ? "bg-white/[0.04]" : "hover:bg-white/[0.02]"
                )}>
                  <button
                    onClick={() => setSelectedId(isExpanded ? null : item.id)}
                    className="w-full px-6 py-6 text-left focus:outline-none group"
                  >
                    <div className="flex items-center gap-5">
                      <div className={cn(
                        'w-10 h-10 rounded-2xl flex items-center justify-center flex-shrink-0 border transition-transform group-hover:scale-110',
                        config.bg
                      )}>
                        <Icon className={cn('h-5 w-5', config.color)} />
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <span className={cn('text-sm font-bold uppercase tracking-widest', config.color)}>
                            {config.label}
                          </span>
                          <span className="h-1 w-1 rounded-full bg-slate-700" />
                          <span className="text-xs text-slate-500 font-light tracking-wide">
                            {formatDate(item.created_at)}
                          </span>
                        </div>
                        
                        <div className="flex items-center gap-2 mt-2 text-slate-300">
                          <FileText className="h-4 w-4 text-slate-600" />
                          <span className="text-sm font-medium truncate max-w-[200px] md:max-w-md">
                            {item.file_path || 'Unknown file'}
                          </span>
                          {item.section_title && (
                            <>
                              <span className="text-slate-700">/</span>
                              <span className="text-sm text-slate-400 truncate font-light">
                                {item.section_title}
                              </span>
                            </>
                          )}
                        </div>
                      </div>

                      {isExpanded ? (
                        <ChevronUp className="h-5 w-5 text-slate-600" />
                      ) : (
                        <ChevronDown className="h-5 w-5 text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                      )}
                    </div>
                  </button>
                  {isExpanded && (
                    <div className="px-6 pb-8 pt-2 animate-[slideUpFade_0.4s_ease_both]">
                      <div className="rounded-2xl border border-white/5 bg-black/20 p-6 overflow-hidden shadow-inner">
                         <div className="mb-4 text-[10px] uppercase tracking-[0.2em] text-slate-500 font-bold">
                           Change Details
                         </div>
                         <DiffViewer original={item.old_content} modified={item.new_content} />
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}