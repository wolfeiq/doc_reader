'use client';

import Link from 'next/link';
import { FileText, FolderOpen, Loader2, ChevronRight } from 'lucide-react';
import { formatRelativeTime, groupByFolder } from '@/lib/utils';
import { useDocuments } from '@/hooks';

export default function DocumentsPage() {
  const { data: documents, isLoading, isFetching } = useDocuments();

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4 bg-transparent">
        <Loader2 className="h-10 w-10 animate-spin text-primary-500/50" />
        <p className="text-slate-500 font-light italic">Scanning knowledge base...</p>
      </div>
    );
  }

  const grouped = groupByFolder(documents || []);
  const isRefetching = isFetching && !isLoading;

  return (
    <div className="max-w-5xl mx-auto space-y-10 py-10 px-4">
      <div className="text-center space-y-4">
        <h1 className="text-slate-100 flex items-center justify-center gap-3">
          <FolderOpen className="h-8 w-8 text-primary-400/60" /> Documents
        </h1>
        <p className="text-lg text-slate-400/70 font-light max-w-lg mx-auto leading-relaxed">
          Browse your managed documentation and tracked file sections.
        </p>
        {isRefetching && (
          <div className="flex items-center justify-center gap-2 text-sm text-primary-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Refreshing...</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        <div className="lg:col-span-3 space-y-8">
          {!documents?.length ? (
            <div className="glass-panel rounded-3xl py-24 text-center border border-white/10">
              <FileText className="h-12 w-12 text-slate-700 mx-auto mb-4 opacity-20" />
              <p className="text-slate-500 italic">No documents found in the repository.</p>
            </div>
          ) : (
            <div className="space-y-10">
              {Object.entries(grouped).map(([folder, docs]) => (
                <div key={folder} className="animate-[slideUpFade_0.5s_ease_both]">
                  <div className="flex items-center gap-3 mb-4 px-2">
                    <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-primary-400/60">
                      {folder === '/' ? 'Root Directory' : folder}
                    </span>
                    <div className="h-[1px] flex-1 bg-white/5" />
                    <span className="text-[10px] text-slate-600 font-bold uppercase tracking-widest">
                      {docs.length} files
                    </span>
                  </div>

                  <div className="glass-panel rounded-3xl overflow-hidden border border-white/10 shadow-2xl divide-y divide-white/5">
                    {docs.map((doc) => (
                      <Link
                        key={doc.id}
                        href={`/documents/${doc.id}`}
                        className="group flex items-center gap-5 p-5 transition-all hover:bg-white/[0.04] focus:outline-none"
                      >
                        <div className="w-10 h-10 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0 transition-transform group-hover:scale-110">
                          <FileText className="h-5 w-5 text-slate-400 group-hover:text-primary-400 transition-colors" />
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-slate-200 group-hover:text-white transition-colors truncate">
                              {doc.file_path.split('/').pop()}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 mt-1.5">
                            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                              {doc.section_count} sections
                            </span>
                            <span className="h-1 w-1 rounded-full bg-slate-700" />
                            <span className="text-xs text-slate-500 font-light tracking-wide">
                              Updated {formatRelativeTime(doc.updated_at)}
                            </span>
                          </div>
                        </div>

                        <ChevronRight className="h-4 w-4 text-slate-700 opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all" />
                      </Link>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <aside className="lg:sticky lg:top-24 h-fit space-y-6">
          <div className="glass-panel rounded-3xl p-6 shadow-2xl border border-white/10 space-y-6">
            <h4 className="text-[10px] uppercase tracking-[0.2em] text-slate-200 font-bold border-b border-white/5 pb-4">
              Library Stats
            </h4>
            <div className="space-y-4">
              <div className="bg-white/[0.02] p-4 rounded-2xl border border-white/5">
                <span className="text-[10px] uppercase tracking-widest text-slate-500 block mb-1 font-bold">Files</span>
                <span className="text-2xl font-heading text-slate-200">{documents?.length || 0}</span>
              </div>
              <div className="bg-white/[0.02] p-4 rounded-2xl border border-white/5">
                <span className="text-[10px] uppercase tracking-widest text-slate-500 block mb-1 font-bold">Total Sections</span>
                <span className="text-2xl font-heading text-primary-400">
                  {documents?.reduce((sum, d) => sum + d.section_count, 0) || 0}
                </span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

