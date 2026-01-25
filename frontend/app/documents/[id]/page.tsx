'use client';

import React, { useState, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Loader2, AlertCircle, ChevronRight, Check, X } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useQuery } from '@tanstack/react-query';
import { documentApi } from '@/lib/api';
import { cn } from '@/lib/utils';

const MarkdownRenderer = dynamic(() => import('@/components/ClientMarkdown'), { ssr: false });


type ChangeType = 'none' | 'pending' | 'accepted' | 'rejected';

interface Section {
  section_id: string;
  section_title: string;
  original_content: string;
  preview_content: string;
  suggestion_id: string | null;
  history_id: string | null;
  confidence: number | null;
  change_type: ChangeType;
  changed_at: string | null;
  order: number;
  start_line: number;
  end_line: number;
}

interface DocumentPreview {
  id: string;
  file_path: string;
  title: string;
  sections: Section[];
  has_pending_changes: boolean;
  pending_suggestion_count: number;
  has_recent_changes: boolean;
  recent_change_count: number;
}

interface DiffSegment {
  type: 'unchanged' | 'added' | 'removed';
  text: string;
}


function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

function computeWordDiff(original: string, modified: string): DiffSegment[] {
  if (original === modified) {
    return [{ type: 'unchanged', text: original }];
  }
  const originalWords = original.split(/(\s+)/);
  const modifiedWords = modified.split(/(\s+)/);
  const m = originalWords.length;
  const n = modifiedWords.length;
  const dp: number[][] = Array(m + 1).fill(null).map(() => Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (originalWords[i - 1] === modifiedWords[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  let i = m, j = n;
  const result: DiffSegment[] = [];
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && originalWords[i - 1] === modifiedWords[j - 1]) {
      result.unshift({ type: 'unchanged', text: originalWords[i - 1] });
      i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: 'added', text: modifiedWords[j - 1] });
      j--;
    } else {
      result.unshift({ type: 'removed', text: originalWords[i - 1] });
      i--;
    }
  }

  const merged: DiffSegment[] = [];
  for (const seg of result) {
    if (merged.length > 0 && merged[merged.length - 1].type === seg.type) {
      merged[merged.length - 1].text += seg.text;
    } else {
      merged.push({ ...seg });
    }
  }
  return merged;
}


export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.id as string;

  const { data: fullDoc, isLoading: loadingDoc, error: errorDoc } = useQuery({
    queryKey: ['documents', documentId],
    queryFn: () => documentApi.get(documentId),
    enabled: !!documentId,
  });

  const { data: preview, isLoading: loadingPreview } = useQuery<DocumentPreview>({
    queryKey: ['documents', documentId, 'preview'],
    queryFn: () => documentApi.preview(documentId),
    enabled: !!documentId,
  });

  const [selectedSection, setSelectedSection] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<'all' | 'pending' | 'accepted' | 'rejected'>('all');

  const changedSections = useMemo(
    () => preview?.sections.filter((s: Section) => s.change_type !== 'none') || [],
    [preview?.sections]
  );

  const filteredSections = useMemo(() => {
    if (filterType === 'all') return changedSections;
    return changedSections.filter((s: Section) => s.change_type === filterType);
  }, [changedSections, filterType]);

  const selectedSectionData = useMemo(() => {
    if (!selectedSection || !preview) return null;
    return preview.sections.find((s: Section) => s.section_id === selectedSection);
  }, [selectedSection, preview]);

  const countByType = useMemo(() => {
    const counts = { pending: 0, accepted: 0, rejected: 0 };
    changedSections.forEach((s: Section) => {
      if (s.change_type in counts) {
        counts[s.change_type as keyof typeof counts]++;
      }
    });
    return counts;
  }, [changedSections]);

  React.useEffect(() => {
    if (filteredSections.length > 0 && !selectedSection) {
      setSelectedSection(filteredSections[0].section_id);
    }
  }, [filteredSections, selectedSection]);

  if (loadingDoc || loadingPreview) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-transparent">
        <Loader2 className="h-8 w-8 animate-spin text-primary-400" />
      </div>
    );
  }

  if (errorDoc || !fullDoc || !preview) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-transparent">
        <div className="text-center bg-white/5 backdrop-blur-xl p-8 rounded-2xl border border-white/10">
          <h2 className="text-xl font-medium text-red-400 mb-4 font-heading">Error loading document</h2>
          <button
            onClick={() => router.push('/documents')}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 text-white rounded-md hover:bg-white/20 transition-all"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Documents
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-transparent p-6 text-slate-200">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="animate-[slideUpFade_0.6s_ease_both]">
          <button
            onClick={() => router.push('/documents')}
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-white mb-4 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Documents
          </button>
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <h1 className="text-3xl font-heading text-slate-100">{preview.title}</h1>
              <p className="text-slate-400 font-light tracking-wide">{preview.file_path}</p>
            </div>
            <div className="flex items-center gap-2">
              {preview.has_pending_changes && (
                <div className="bg-amber-500/20 text-amber-300 border border-amber-500/30 px-3 py-1.5 rounded-full backdrop-blur-md flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider">
                  <AlertCircle className="h-3.5 w-3.5" />
                  {preview.pending_suggestion_count} Pending
                </div>
              )}
              {preview.has_recent_changes && (
                <div className="bg-green-500/20 text-green-300 border border-green-500/30 px-3 py-1.5 rounded-full backdrop-blur-md flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider">
                  <Check className="h-3.5 w-3.5" />
                  {preview.recent_change_count} Recent
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="space-y-4">
            <div className="bg-white/[0.03] backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden shadow-2xl sticky top-6">
              <div className="bg-white/[0.05] px-5 py-4 border-b border-white/10 flex justify-between items-center">
                <h2 className="font-medium text-slate-100">Current Document</h2>
                <span className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Read Only</span>
              </div>
              <div className="p-8 overflow-y-auto max-h-[calc(100vh-250px)] no-scrollbar prose-invert prose-slate">
                <MarkdownRenderer content={fullDoc.content} />
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-white/[0.03] backdrop-blur-xl border border-white/10 rounded-2xl p-6 shadow-2xl space-y-6">
              <h3 className="font-medium text-slate-100">Changes Summary</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white/[0.02] p-4 rounded-xl border border-white/5">
                  <span className="text-[10px] uppercase tracking-widest text-slate-500 block mb-1 font-bold">Total Sections</span>
                  <span className="text-xl font-heading text-slate-200">{preview.sections.length}</span>
                </div>
                <div className="bg-white/[0.02] p-4 rounded-xl border border-white/5">
                  <span className="text-[10px] uppercase tracking-widest text-slate-500 block mb-1 font-bold">With Changes</span>
                  <span className="text-xl font-heading text-primary-400">{changedSections.length}</span>
                </div>
              </div>
              
              {changedSections.length > 0 && (
                <div className="flex flex-wrap gap-2 pt-6 border-t border-white/10">
                  <FilterBtn active={filterType === 'all'} onClick={() => setFilterType('all')} label={`All (${changedSections.length})`} variant="all" />
                  {countByType.pending > 0 && <FilterBtn active={filterType === 'pending'} onClick={() => setFilterType('pending')} label={`Pending (${countByType.pending})`} variant="pending" />}
                  {countByType.accepted > 0 && <FilterBtn active={filterType === 'accepted'} onClick={() => setFilterType('accepted')} label={`Accepted (${countByType.accepted})`} variant="accepted" />}
                  {countByType.rejected > 0 && <FilterBtn active={filterType === 'rejected'} onClick={() => setFilterType('rejected')} label={`Rejected (${countByType.rejected})`} variant="rejected" />}
                </div>
              )}
            </div>

            {filteredSections.length > 0 ? (
              <div className="bg-white/[0.03] backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden shadow-2xl">
                <div className="bg-white/[0.05] px-5 py-4 border-b border-white/10">
                  <h3 className="font-medium text-slate-100">Section Diff</h3>
                </div>
                <div className="divide-y divide-white/5 max-h-[350px] overflow-y-auto no-scrollbar">
                  {filteredSections.map((section: Section) => (
                    <SectionListItem
                      key={section.section_id}
                      section={section}
                      isSelected={selectedSection === section.section_id}
                      onClick={() => setSelectedSection(section.section_id)}
                    />
                  ))}
                </div>
              </div>
            ) : (
              <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-12 text-center shadow-2xl">
                <AlertCircle className="h-8 w-8 text-slate-600 mx-auto mb-2" />
                <p className="text-sm text-slate-500 italic">No changes matching the current filter.</p>
              </div>
            )}

            {selectedSectionData && selectedSectionData.change_type !== 'none' && (
              <div className="bg-white/[0.03] backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden shadow-2xl animate-[slideUpFade_0.4s_ease_both]">
                <DiffHeader section={selectedSectionData} />
                <div className="p-6">
                  <DiffViewer
                    original={selectedSectionData.original_content || ''}
                    modified={selectedSectionData.preview_content || ''}
                    changeType={selectedSectionData.change_type}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function FilterBtn({ active, onClick, label, variant }: { active: boolean, onClick: () => void, label: string, variant: string }) {
  const base = "px-4 py-2 text-[10px] font-bold uppercase tracking-wider rounded-full border border-white/5 transition-all";
  const styles = {
    all: active ? 'bg-white/20 text-white' : 'bg-white/5 text-slate-400 hover:bg-white/10',
    pending: active ? 'bg-amber-500/40 text-amber-200' : 'bg-amber-500/10 text-amber-400 hover:bg-amber-500/20',
    accepted: active ? 'bg-green-500/40 text-green-200' : 'bg-green-500/10 text-green-400 hover:bg-green-500/20',
    rejected: active ? 'bg-red-500/40 text-red-200' : 'bg-red-500/10 text-red-400 hover:bg-red-500/20'
  };
  return <button onClick={onClick} className={cn(base, styles[variant as keyof typeof styles])}>{label}</button>;
}

function SectionListItem({ section, isSelected, onClick }: { section: Section, isSelected: boolean, onClick: () => void }) {
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
            {section.changed_at && <span className="text-xs text-slate-500 font-light">{formatRelativeTime(section.changed_at)}</span>}
          </div>
        </div>
        <ChevronRight className={cn("h-4 w-4 mt-1 transition-colors", isSelected ? 'text-white' : 'text-slate-600')} />
      </div>
    </button>
  );
}

function DiffHeader({ section }: { section: Section }) {
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

function DiffViewer({ original, modified, changeType }: { original: string, modified: string, changeType: ChangeType }) {
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