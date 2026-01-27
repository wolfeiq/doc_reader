'use client';

import React, { useState, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Loader2, AlertCircle, Check } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useQuery } from '@tanstack/react-query';
import { documentApi } from '@/lib/api';
import type { Section, DocumentPreviewUnique, FilterVariant } from '@/types';
import { FilterBtn } from '@/components/ui/FilterBtn';
import { SectionListItem } from '@/components/ui/SectionListItem';
import { DiffHeader } from '@/components/ui/DiffHeader';
import { SectionDiff } from '@/components/ui/DiffViewer';

const MarkdownRenderer = dynamic(() => import('@/components/ui/ClientMarkdown'), { ssr: false });

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.id as string;

  const { data: fullDoc, isLoading: loadingDoc, error: errorDoc } = useQuery({
    queryKey: ['documents', documentId],
    queryFn: () => documentApi.get(documentId),
    enabled: !!documentId,
  });

  const { data: preview, isLoading: loadingPreview } = useQuery<DocumentPreviewUnique>({
    queryKey: ['documents', documentId, 'preview'],
    queryFn: () => documentApi.preview(documentId),
    enabled: !!documentId,
  });

  const [selectedSection, setSelectedSection] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<FilterVariant>('all');

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
                  <SectionDiff
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
