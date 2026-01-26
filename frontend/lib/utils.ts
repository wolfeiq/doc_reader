import { DiffSegment, DocumentListItem } from '@/types';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(date));
}

export function formatRelativeTimeUnique(dateString: string): string {
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

export function formatRelativeTime(date: string | Date): string {
  const now = new Date();
  const then = new Date(date);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return formatDate(date);
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + '...';
}

type ConfidenceLevel = 'high' | 'medium' | 'low';

function getConfidenceLevel(confidence: number): ConfidenceLevel {
  if (confidence >= 0.9) return 'high';
  if (confidence >= 0.7) return 'medium';
  return 'low';
}

const CONFIDENCE_STYLES = {
  high: {
    text: 'text-green-600 dark:text-green-400',
    bg: 'bg-green-100 dark:bg-green-900/30',
  },
  medium: {
    text: 'text-yellow-600 dark:text-yellow-400',
    bg: 'bg-yellow-100 dark:bg-yellow-900/30',
  },
  low: {
    text: 'text-red-600 dark:text-red-400',
    bg: 'bg-red-100 dark:bg-red-900/30',
  },
} as const;

export function getConfidenceColor(confidence: number): string {
  return CONFIDENCE_STYLES[getConfidenceLevel(confidence)].text;
}

export function getConfidenceBg(confidence: number): string {
  return CONFIDENCE_STYLES[getConfidenceLevel(confidence)].bg;
}

type StatusType = 'success' | 'warning' | 'error' | 'default';

function getStatusType(status: string): StatusType {
  const normalized = status.toUpperCase();
  
  if (normalized === 'COMPLETED' || normalized === 'ACCEPTED') return 'success';
  if (normalized === 'PROCESSING' || normalized === 'PENDING') return 'warning';
  if (normalized === 'FAILED' || normalized === 'REJECTED') return 'error';
  return 'default';
}

const STATUS_STYLES = {
  success: {
    text: 'text-green-600 dark:text-green-400',
    bg: 'bg-green-100 dark:bg-green-900/30',
  },
  warning: {
    text: 'text-yellow-600 dark:text-yellow-400',
    bg: 'bg-yellow-100 dark:bg-yellow-900/30',
  },
  error: {
    text: 'text-red-600 dark:text-red-400',
    bg: 'bg-red-100 dark:bg-red-900/30',
  },
  default: {
    text: 'text-gray-600 dark:text-gray-400',
    bg: 'bg-gray-100 dark:bg-gray-900/30',
  },
} as const;

export function getStatusColor(status: string): string {
  return STATUS_STYLES[getStatusType(status)].text;
}

export function getStatusBg(status: string): string {
  return STATUS_STYLES[getStatusType(status)].bg;
}


export function parseSSEChunk(buffer: string, chunk: string) {
  const currentBuffer = buffer + chunk;
  const lines = currentBuffer.split('\n');
  const remainingBuffer = lines.pop() || '';
  
  const messages: Array<{ event: string; data: any }> = [];
  let currentEvent = '';

  for (const line of lines) {
    if (!line.trim() || line.startsWith(':')) continue;

    if (line.startsWith('event:')) {
      currentEvent = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      const dataStr = line.slice(5).trim();
      try {
        const data = JSON.parse(dataStr);
        messages.push({ event: currentEvent, data });
        currentEvent = ''; 
      } catch (e) {
        console.error('Error parsing SSE JSON:', e);
      }
    }
  }

  return { remainingBuffer, messages };
}


export function computeWordDiff(original: string, modified: string): DiffSegment[] {
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

export function groupByFolder(docs: DocumentListItem[]): Record<string, DocumentListItem[]> {
  const groups: Record<string, DocumentListItem[]> = {};
  docs.forEach((doc) => {
    const parts = doc.file_path.split('/');
    const folder = parts.length > 1 ? parts.slice(0, -1).join('/') : '/';
    if (!groups[folder]) groups[folder] = [];
    groups[folder].push(doc);
  });
  return groups;
}