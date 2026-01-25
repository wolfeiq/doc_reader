'use client';

import React, { useState, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Loader2, AlertCircle, ChevronRight, Check, X } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useQuery } from '@tanstack/react-query';
import { documentApi } from '@/lib/api';

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

// Word-level diff types
interface DiffSegment {
  type: 'unchanged' | 'added' | 'removed';
  text: string;
}

// Compute word-level diff using LCS algorithm
function computeWordDiff(original: string, modified: string): DiffSegment[] {
  if (original === modified) {
    return [{ type: 'unchanged', text: original }];
  }

  const originalWords = original.split(/(\s+)/);
  const modifiedWords = modified.split(/(\s+)/);

  const m = originalWords.length;
  const n = modifiedWords.length;

  // Build LCS table
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

  // Backtrack to find diff
  let i = m, j = n;
  const result: DiffSegment[] = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && originalWords[i - 1] === modifiedWords[j - 1]) {
      result.unshift({ type: 'unchanged', text: originalWords[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: 'added', text: modifiedWords[j - 1] });
      j--;
    } else {
      result.unshift({ type: 'removed', text: originalWords[i - 1] });
      i--;
    }
  }

  // Merge consecutive segments of the same type
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

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.id as string;

  // Fetch full document content
  const { data: fullDoc, isLoading: loadingDoc, error: errorDoc } = useQuery({
    queryKey: ['documents', documentId],
    queryFn: () => documentApi.get(documentId),
    enabled: !!documentId,
  });

  // Fetch preview with sections (include 24h of history)
  const { data: preview, isLoading: loadingPreview } = useQuery<DocumentPreview>({
    queryKey: ['documents', documentId, 'preview'],
    queryFn: () => documentApi.preview(documentId),
    enabled: !!documentId,
  });

  const [selectedSection, setSelectedSection] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<'all' | 'pending' | 'accepted' | 'rejected'>('all');

  // Sections with any changes (pending or from history)
  const changedSections = useMemo(
    () => preview?.sections.filter((s: Section) => s.change_type !== 'none') || [],
    [preview?.sections]
  );

  // Filter sections based on selected filter
  const filteredSections = useMemo(() => {
    if (filterType === 'all') return changedSections;
    return changedSections.filter((s: Section) => s.change_type === filterType);
  }, [changedSections, filterType]);

  const selectedSectionData = useMemo(() => {
    if (!selectedSection || !preview) return null;
    return preview.sections.find((s: Section) => s.section_id === selectedSection);
  }, [selectedSection, preview]);

  // Count by type
  const countByType = useMemo(() => {
    const counts = { pending: 0, accepted: 0, rejected: 0 };
    changedSections.forEach((s: Section) => {
      if (s.change_type in counts) {
        counts[s.change_type as keyof typeof counts]++;
      }
    });
    return counts;
  }, [changedSections]);

  // Auto-select first changed section
  React.useEffect(() => {
    if (filteredSections.length > 0 && !selectedSection) {
      setSelectedSection(filteredSections[0].section_id);
    }
  }, [filteredSections, selectedSection]);

  if (loadingDoc || loadingPreview) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (errorDoc || !fullDoc || !preview) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-medium text-red-600 mb-4">Error loading document</h2>
          <button
            onClick={() => router.push('/documents')}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Documents
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <button
            onClick={() => router.push('/documents')}
            className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Documents
          </button>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-3xl font-bold">{preview.title}</h1>
              <p className="text-gray-600 mt-1">{preview.file_path}</p>
            </div>
            <div className="flex items-center gap-2">
              {preview.has_pending_changes && (
                <div className="bg-amber-500 text-white px-3 py-1.5 rounded-md flex items-center gap-2">
                  <AlertCircle className="h-4 w-4" />
                  {preview.pending_suggestion_count} Pending
                </div>
              )}
              {preview.has_recent_changes && (
                <div className="bg-green-500 text-white px-3 py-1.5 rounded-md flex items-center gap-2">
                  <Check className="h-4 w-4" />
                  {preview.recent_change_count} Recent
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Main Document Content - Original */}
          <div>
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm sticky top-6">
              <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
                <h2 className="font-semibold">Current Document</h2>
                <p className="text-xs text-gray-600 mt-1">
                  Current version in your documentation
                </p>
              </div>
              <div className="p-6 overflow-y-auto max-h-[calc(100vh-200px)]">
                <MarkdownRenderer content={fullDoc.content} />
              </div>
            </div>
          </div>

          {/* Changes Panel */}
          <div>
            <div className="space-y-4">
              {/* Changes Summary */}
              <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                <h3 className="font-semibold mb-3">Changes Summary</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Total Sections</span>
                    <span className="font-medium">{preview.sections.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">With Changes</span>
                    <span className="font-medium">{changedSections.length}</span>
                  </div>
                </div>
                
                {/* Filter buttons */}
                {changedSections.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t">
                    <button
                      onClick={() => setFilterType('all')}
                      className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                        filterType === 'all'
                          ? 'bg-gray-900 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      All ({changedSections.length})
                    </button>
                    {countByType.pending > 0 && (
                      <button
                        onClick={() => setFilterType('pending')}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                          filterType === 'pending'
                            ? 'bg-amber-500 text-white'
                            : 'bg-amber-100 text-amber-700 hover:bg-amber-200'
                        }`}
                      >
                        Pending ({countByType.pending})
                      </button>
                    )}
                    {countByType.accepted > 0 && (
                      <button
                        onClick={() => setFilterType('accepted')}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                          filterType === 'accepted'
                            ? 'bg-green-500 text-white'
                            : 'bg-green-100 text-green-700 hover:bg-green-200'
                        }`}
                      >
                        Accepted ({countByType.accepted})
                      </button>
                    )}
                    {countByType.rejected > 0 && (
                      <button
                        onClick={() => setFilterType('rejected')}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                          filterType === 'rejected'
                            ? 'bg-red-500 text-white'
                            : 'bg-red-100 text-red-700 hover:bg-red-200'
                        }`}
                      >
                        Rejected ({countByType.rejected})
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Changed Sections List */}
              {filteredSections.length > 0 ? (
                <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
                  <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
                    <h3 className="font-semibold">
                      {filterType === 'all' ? 'All Changes' : 
                       filterType === 'pending' ? 'Pending Changes' :
                       filterType === 'accepted' ? 'Accepted Changes' : 'Rejected Changes'}
                    </h3>
                    <p className="text-xs text-gray-600 mt-1">
                      Click to view diff
                    </p>
                  </div>
                  <div className="divide-y max-h-[400px] overflow-y-auto">
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
                <div className="bg-white border border-gray-200 rounded-lg p-8 text-center shadow-sm">
                  <AlertCircle className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                  <p className="text-sm text-gray-600">
                    {filterType === 'all' ? 'No changes found' : `No ${filterType} changes`}
                  </p>
                </div>
              )}

              {/* Selected Section Diff */}
              {selectedSectionData && selectedSectionData.change_type !== 'none' && (
                <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
                  <DiffHeader section={selectedSectionData} />
                  <div className="p-4">
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
    </div>
  );
}

function SectionListItem({ 
  section, 
  isSelected, 
  onClick 
}: { 
  section: Section; 
  isSelected: boolean; 
  onClick: () => void;
}) {
  const getBadgeStyles = (type: ChangeType) => {
    switch (type) {
      case 'pending':
        return 'bg-amber-100 text-amber-700 border-amber-200';
      case 'accepted':
        return 'bg-green-100 text-green-700 border-green-200';
      case 'rejected':
        return 'bg-red-100 text-red-700 border-red-200';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  const getSelectedStyles = (type: ChangeType) => {
    switch (type) {
      case 'pending':
        return 'bg-amber-50 border-l-4 border-amber-500';
      case 'accepted':
        return 'bg-green-50 border-l-4 border-green-500';
      case 'rejected':
        return 'bg-red-50 border-l-4 border-red-500';
      default:
        return 'bg-gray-50 border-l-4 border-gray-500';
    }
  };

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
        isSelected ? getSelectedStyles(section.change_type) : ''
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm truncate">
            {section.section_title || 'Untitled Section'}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-xs px-1.5 py-0.5 rounded border ${getBadgeStyles(section.change_type)}`}>
              {section.change_type}
            </span>
            {section.changed_at && (
              <span className="text-xs text-gray-500">
                {formatRelativeTime(section.changed_at)}
              </span>
            )}
            {section.confidence && (
              <span className="text-xs text-gray-500">
                {Math.round(section.confidence * 100)}%
              </span>
            )}
          </div>
        </div>
        <ChevronRight className={`h-4 w-4 flex-shrink-0 ${
          isSelected ? 'text-gray-900' : 'text-gray-400'
        }`} />
      </div>
    </button>
  );
}

function DiffHeader({ section }: { section: Section }) {
  const getHeaderStyles = (type: ChangeType) => {
    switch (type) {
      case 'pending':
        return 'bg-amber-50 border-amber-200 text-amber-900';
      case 'accepted':
        return 'bg-green-50 border-green-200 text-green-900';
      case 'rejected':
        return 'bg-red-50 border-red-200 text-red-900';
      default:
        return 'bg-gray-50 border-gray-200 text-gray-900';
    }
  };

  const getIcon = (type: ChangeType) => {
    switch (type) {
      case 'pending':
        return <AlertCircle className="h-4 w-4" />;
      case 'accepted':
        return <Check className="h-4 w-4" />;
      case 'rejected':
        return <X className="h-4 w-4" />;
      default:
        return null;
    }
  };

  return (
    <div className={`px-4 py-3 border-b ${getHeaderStyles(section.change_type)}`}>
      <div className="flex items-center gap-2">
        {getIcon(section.change_type)}
        <h3 className="font-semibold text-sm">
          {section.section_title || 'Untitled Section'}
        </h3>
        <span className="text-xs opacity-75">
          ({section.change_type})
        </span>
      </div>
      {section.changed_at && (
        <p className="text-xs opacity-75 mt-0.5">
          Changed {formatRelativeTime(section.changed_at)}
        </p>
      )}
    </div>
  );
}

function DiffViewer({ 
  original, 
  modified, 
  changeType 
}: { 
  original: string; 
  modified: string;
  changeType: ChangeType;
}) {
  const diff = useMemo(() => computeWordDiff(original, modified), [original, modified]);
  const hasChanges = original !== modified;

  if (!hasChanges) {
    return (
      <div className="font-mono text-xs border border-gray-200 rounded-lg p-3 bg-gray-50 whitespace-pre-wrap">
        {original}
      </div>
    );
  }

  // For rejected changes, swap the labels (show what was proposed vs what was kept)
  const isRejected = changeType === 'rejected';

  return (
    <div className="space-y-3">
      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-gray-600">
        <div className="flex items-center gap-1.5">
          <span className="px-1.5 py-0.5 bg-red-100 text-red-800 rounded line-through">
            {isRejected ? 'proposed (rejected)' : 'removed'}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="px-1.5 py-0.5 bg-green-100 text-green-800 rounded underline">
            {isRejected ? 'kept' : 'added'}
          </span>
        </div>
      </div>

      {/* Inline Diff */}
      <div className="font-mono text-xs border border-gray-200 rounded-lg p-3 bg-white max-h-[500px] overflow-y-auto leading-relaxed whitespace-pre-wrap">
        {diff.map((segment, idx) => {
          if (segment.type === 'unchanged') {
            return <span key={idx}>{segment.text}</span>;
          }
          if (segment.type === 'added') {
            return (
              <span
                key={idx}
                className="bg-green-100 text-green-900 px-0.5 rounded underline decoration-green-500 underline-offset-2"
              >
                {segment.text}
              </span>
            );
          }
          if (segment.type === 'removed') {
            return (
              <span
                key={idx}
                className="bg-red-100 text-red-900 px-0.5 rounded line-through decoration-red-500"
              >
                {segment.text}
              </span>
            );
          }
          return null;
        })}
      </div>

      {/* Side by side view */}
      <details className="group">
        <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700 select-none">
          Show side-by-side comparison
        </summary>
        <div className="grid grid-cols-2 gap-3 mt-3">
          <div>
            <div className="text-xs font-medium text-red-700 mb-1.5 flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-red-400"></div>
              {isRejected ? 'Proposed (Rejected)' : 'Original'}
            </div>
            <div className="font-mono text-xs border border-red-200 rounded-lg p-3 bg-red-50/50 whitespace-pre-wrap max-h-[300px] overflow-y-auto">
              {original}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-green-700 mb-1.5 flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-green-400"></div>
              {isRejected ? 'Kept (Current)' : changeType === 'accepted' ? 'Accepted' : 'Proposed'}
            </div>
            <div className="font-mono text-xs border border-green-200 rounded-lg p-3 bg-green-50/50 whitespace-pre-wrap max-h-[300px] overflow-y-auto">
              {modified}
            </div>
          </div>
        </div>
      </details>
    </div>
  );
}