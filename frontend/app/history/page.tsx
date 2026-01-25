'use client';

import { useState } from 'react';
import { History, Check, X, Pencil, RotateCcw, Loader2, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatDate, getStatusBg } from '@/lib/utils';
import { useHistory } from '@/hooks';
import { Card, CardContent, Button } from '@/components/ui';
import { DiffViewer } from '@/components/suggestions';
import type { EditHistory, UserAction } from '@/types';

const ACTION_CONFIG: Record<UserAction, { icon: typeof Check; label: string; color: string }> = {
  ACCEPTED: { icon: Check, label: 'Accepted', color: 'text-green-600' },
  REJECTED: { icon: X, label: 'Rejected', color: 'text-red-600' },
  EDITED: { icon: Pencil, label: 'Edited', color: 'text-blue-600' },
  REVERTED: { icon: RotateCcw, label: 'Reverted', color: 'text-orange-600' },
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
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <History className="h-6 w-6" /> Edit History
        </h1>
        <p className="text-muted-foreground mt-1">Track all changes made to your documentation</p>
      </div>

    

      <Card>
        <CardContent className="p-0">
          {!history?.length ? (
            <div className="py-12 text-center">
              <History className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No edit history yet</p>
            </div>
          ) : (
            <div className="divide-y">
              {history.map((item) => {
                const actionKey = item.user_action.toUpperCase() as UserAction;
                const config = ACTION_CONFIG[actionKey];
                const Icon = config.icon;
                const isExpanded = selectedId === item.id;

                return (
                  <div key={item.id} className="p-4">
                    <button
                      onClick={() => setSelectedId(isExpanded ? null : item.id)}
                      className="w-full text-left"
                    >
                      <div className="flex items-start gap-4">
                        <div className={cn('w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0', getStatusBg(item.user_action))}>
                          <Icon className={cn('h-4 w-4', config.color)} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className={cn('font-medium', config.color)}>{config.label}</span>
                            <span className="text-muted-foreground">·</span>
                            <span className="text-sm text-muted-foreground">{formatDate(item.created_at)}</span>
                          </div>
                          <div className="flex items-center gap-2 mt-1 text-sm">
                            <FileText className="h-4 w-4 text-muted-foreground" />
                            <span className="truncate">{item.file_path || 'Unknown file'}</span>
                            {item.section_title && (
                              <>
                                <span className="text-muted-foreground">·</span>
                                <span className="truncate text-muted-foreground">{item.section_title}</span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="mt-4 pt-4 border-t ml-12">
                        <DiffViewer original={item.old_content} modified={item.new_content} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
