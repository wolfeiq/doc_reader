import { clsx, type ClassValue } from 'clsx';

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(date));
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

export function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.9) return 'text-green-600 dark:text-green-400';
  if (confidence >= 0.7) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-red-600 dark:text-red-400';
}

export function getConfidenceBg(confidence: number): string {
  if (confidence >= 0.9) return 'bg-green-100 dark:bg-green-900/30';
  if (confidence >= 0.7) return 'bg-yellow-100 dark:bg-yellow-900/30';
  return 'bg-red-100 dark:bg-red-900/30';
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'COMPLETED':
    case 'ACCEPTED':
      return 'text-green-600 dark:text-green-400';
    case 'PROCESSING':
    case 'PENDING':
      return 'text-yellow-600 dark:text-yellow-400';
    case 'FAILED':
    case 'REJECTED':
      return 'text-red-600 dark:text-red-400';
    default:
      return 'text-gray-600 dark:text-gray-400';
  }
}

export function getStatusBg(status: string): string {
  switch (status) {
    case 'COMPLETED':
    case 'ACCEPTED':
      return 'bg-green-100 dark:bg-green-900/30';
    case 'PROCESSING':
    case 'PENDING':
      return 'bg-yellow-100 dark:bg-yellow-900/30';
    case 'FAILED':
    case 'REJECTED':
      return 'bg-red-100 dark:bg-red-900/30';
    default:
      return 'bg-gray-100 dark:bg-gray-900/30';
  }
}
