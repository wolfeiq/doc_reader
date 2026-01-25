'use client';

import Link from 'next/link';
import { FileText, FolderOpen, Loader2 } from 'lucide-react';
import { formatRelativeTime } from '@/lib/utils';
import { useDocuments } from '@/hooks';
import { Card, CardHeader, CardTitle, CardContent, Badge } from '@/components/ui';
import type { DocumentListItem } from '@/types';

export default function DocumentsPage() {
  const { data: documents, isLoading } = useDocuments();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const grouped = groupByFolder(documents || []);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Documents</h1>
        <p className="text-muted-foreground mt-1">Browse your documentation files</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FolderOpen className="h-5 w-5" /> Documentation Files
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!documents?.length ? (
                <p className="text-sm text-muted-foreground py-4 text-center">No documents found.</p>
              ) : (
                <div className="space-y-4">
                  {Object.entries(grouped).map(([folder, docs]) => (
                    <div key={folder}>
                      <h3 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                        <FolderOpen className="h-4 w-4" /> {folder === '/' ? 'Root' : folder}
                        <Badge variant="default">{docs.length}</Badge>
                      </h3>
                      <div className="space-y-1 ml-6 border-l pl-3">
                        {docs.map((doc) => (
  <Link
    key={doc.id}
    href={`/documents/${doc.id}`}
    className="flex items-center gap-2 py-1.5 text-sm hover:bg-muted/50 px-2 rounded cursor-pointer"
  >
    <FileText className="h-4 w-4 text-muted-foreground" />
    <span className="font-medium">{doc.file_path.split('/').pop()}</span>
    <span className="text-xs text-muted-foreground">
      {doc.section_count} sections · {formatRelativeTime(doc.updated_at)}
    </span>
  </Link>
))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div>
          <Card>
            <CardHeader><CardTitle>Statistics</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total Documents</span>
                <span className="font-medium">{documents?.length || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total Sections</span>
                <span className="font-medium">{documents?.reduce((sum, d) => sum + d.section_count, 0) || 0}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function groupByFolder(docs: DocumentListItem[]): Record<string, DocumentListItem[]> {
  const groups: Record<string, DocumentListItem[]> = {};
  docs.forEach((doc) => {
    const parts = doc.file_path.split('/');
    const folder = parts.length > 1 ? parts.slice(0, -1).join('/') : '/';
    if (!groups[folder]) groups[folder] = [];
    groups[folder].push(doc);
  });
  return groups;
}
