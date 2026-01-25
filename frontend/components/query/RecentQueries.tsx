'use client';

import Link from 'next/link';
import { Clock, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatRelativeTime, getStatusColor, getStatusBg, truncate } from '@/lib/utils';
import { useQueries } from '@/hooks';
import { Card, CardHeader, CardTitle, CardContent, Badge } from '../ui';

export function RecentQueries() {
  const { data: queries, isLoading } = useQueries({ limit: 5 });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Recent Queries
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!queries?.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Recent Queries
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No queries yet. Start by describing a documentation update above.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-5 w-5" />
          Recent Queries
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {queries.map((query) => (
          <Link
            key={query.id}
            href={query.status === 'COMPLETED' ? `/review?query=${query.id}` : '/'}
            className={cn(
              'flex items-center justify-between rounded-lg border p-3',
              'hover:bg-accent transition-colors'
            )}
          >
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">{truncate(query.query_text, 50)}</p>
              <div className="flex items-center gap-2 mt-1">
                <Badge className={cn('text-xs', getStatusBg(query.status), getStatusColor(query.status))}>
                  {query.status}
                </Badge>
                {query.suggestion_count > 0 && (
                  <span className="text-xs text-muted-foreground">
                    {query.suggestion_count} suggestions
                  </span>
                )}
                <span className="text-xs text-muted-foreground">
                  {formatRelativeTime(query.created_at)}
                </span>
              </div>
            </div>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </Link>
        ))}
      </CardContent>
    </Card>
  );
}
