'use client';

import { useState } from 'react';
import { Check, X, Pencil, ChevronDown, ChevronUp, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getConfidenceColor, getConfidenceBg, getStatusColor, getStatusBg } from '@/lib/utils';
import { useSuggestionStore } from '@/stores';
import { Button, Card, Badge } from '../ui';
import { DiffViewer } from './DiffViewer';
import type { Suggestion } from '@/types';

interface SuggestionCardProps {
  suggestion: Suggestion;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  onSave: (id: string, text: string) => void;
  isLoading?: boolean;
}

export function SuggestionCard({ suggestion, onAccept, onReject, onSave, isLoading }: SuggestionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { selectedId, setSelected, editingId, editedText, startEditing, setEditedText, cancelEditing } = useSuggestionStore();

  const isSelected = selectedId === suggestion.id;
  const isEditing = editingId === suggestion.id;
  // Make this check more flexible
  const isPending = suggestion.status?.toUpperCase() === 'PENDING' || suggestion.status === 'pending';
  const displayText = suggestion.edited_text || suggestion.suggested_text;

  const handleSave = () => {
    onSave(suggestion.id, editedText);
    cancelEditing();
  };

  return (
    <Card
      className={cn('transition-all', isSelected && 'ring-2 ring-primary-500', !isPending && 'opacity-75')}
      onClick={() => setSelected(suggestion.id)}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4 p-4 border-b">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
          <span className="text-sm font-medium truncate">{suggestion.section_title || 'Untitled'}</span>
          <span className="text-xs text-muted-foreground truncate">{suggestion.file_path}</span>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Badge className={cn(getConfidenceBg(suggestion.confidence), getConfidenceColor(suggestion.confidence))}>
            {Math.round(suggestion.confidence * 100)}%
          </Badge>
          {!isPending && (
            <Badge className={cn(getStatusBg(suggestion.status), getStatusColor(suggestion.status))}>
              {suggestion.status}
            </Badge>
          )}
        </div>
      </div>

      {/* Diff */}
      <div className="p-4">
        {isEditing ? (
          <div className="space-y-3">
            <textarea
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              className="w-full h-64 rounded-lg border bg-background px-3 py-2 font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-500"
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={cancelEditing}>
                <X className="h-4 w-4 mr-1" /> Cancel
              </Button>
              <Button size="sm" onClick={handleSave}>
                <Check className="h-4 w-4 mr-1" /> Save
              </Button>
            </div>
          </div>
        ) : (
          <DiffViewer original={suggestion.original_text} modified={displayText} />
        )}
      </div>

      {/* Reasoning */}
      <div className="border-t">
        <button
          onClick={(e) => { e.stopPropagation(); setIsExpanded(!isExpanded); }}
          className="flex items-center justify-between w-full px-4 py-2 text-sm text-muted-foreground hover:bg-muted/50"
        >
          <span>Reasoning</span>
          {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
        {isExpanded && <div className="px-4 pb-4 text-sm text-muted-foreground">{suggestion.reasoning}</div>}
      </div>

      {/* Actions - ALWAYS SHOW FOR DEBUGGING */}
      <div className="flex justify-end gap-2 p-4 border-t bg-muted/30">
        {/* Debug info */}
        <span className="text-xs text-muted-foreground mr-auto">
          Status: {suggestion.status} | isPending: {isPending.toString()} | isEditing: {isEditing.toString()}
        </span>
        
        <Button variant="outline" size="sm" onClick={(e) => { e.stopPropagation(); startEditing(suggestion.id, displayText); }} disabled={isLoading || !isPending}>
          <Pencil className="h-4 w-4 mr-1" /> Edit
        </Button>
        <Button variant="outline" size="sm" onClick={(e) => { e.stopPropagation(); onReject(suggestion.id); }} disabled={isLoading || !isPending} className="text-red-600 hover:bg-red-50">
          <X className="h-4 w-4 mr-1" /> Reject
        </Button>
        <Button size="sm" onClick={(e) => { e.stopPropagation(); onAccept(suggestion.id); }} disabled={isLoading || !isPending}>
          <Check className="h-4 w-4 mr-1" /> Accept
        </Button>
      </div>
    </Card>
  );
}