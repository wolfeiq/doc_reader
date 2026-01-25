'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Check, X, Pencil, ChevronDown, ChevronUp, FileText, MessageSquare, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getConfidenceColor, getConfidenceBg, getStatusColor, getStatusBg } from '@/lib/utils';
import { useSuggestionStore } from '@/stores';
import { Button, Badge } from '../ui';
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
  const isPending = suggestion.status?.toUpperCase() === 'PENDING' || suggestion.status === 'pending';
  const displayText = suggestion.edited_text || suggestion.suggested_text;

  const handleSave = () => {
    onSave(suggestion.id, editedText);
    cancelEditing();
  };

  return (
    <div
      onClick={() => setSelected(suggestion.id)}
      className={cn(
        'glass-panel rounded-3xl overflow-hidden transition-all duration-300 border mb-6',
        isSelected ? 'border-primary-500/50 shadow-[0_0_30px_rgba(14,165,233,0.15)]' : 'border-white/10 shadow-2xl',
        !isPending && 'opacity-60'
      )}
    >
      <div className="flex items-start justify-between gap-4 p-5 border-b border-white/5 bg-white/[0.02]">
        <div className="flex items-center gap-4 min-w-0">
          <div className="p-2.5 rounded-2xl bg-white/5 border border-white/10">
            <FileText className="h-4 w-4 text-slate-400" />
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-medium text-slate-100 truncate">
              {suggestion.section_title || 'Untitled Section'}
            </span>
            
            <div className="flex items-center gap-3 mt-0.5">
              <Link 
                href={`/documents/${suggestion.document_id}`}
                onClick={(e) => e.stopPropagation()} // Prevent card selection when clicking link
                className="text-[10px] uppercase tracking-widest text-slate-500 truncate font-bold hover:text-primary-400 transition-colors flex items-center gap-1"
              >
                {suggestion.file_path}
                <ExternalLink className="h-2.5 w-2.5" />
              </Link>

              <Link
                href={`/documents/${suggestion.document_id}`}
                onClick={(e) => e.stopPropagation()}
                className={cn(
                  "text-[9px] font-black uppercase tracking-tighter px-2 py-0.5 rounded-md",
                  "bg-orange-500 text-white shadow-[0_0_15px_rgba(249,115,22,0.4)]",
                  "hover:bg-orange-400 hover:scale-105 transition-all animate-pulse"
                )}
              >
                click here to see the changes in the whole doc!!!
              </Link>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-2 flex-shrink-0">
          <Badge className={cn(
            'text-[10px] uppercase tracking-wider px-2.5 py-0.5 rounded-full border-none font-bold',
            getConfidenceBg(suggestion.confidence), 
            getConfidenceColor(suggestion.confidence)
          )}>
            {Math.round(suggestion.confidence * 100)}% Match
          </Badge>
          {!isPending && (
            <Badge className={cn(
              'text-[10px] uppercase tracking-wider px-2.5 py-0.5 rounded-full border-none font-bold',
              getStatusBg(suggestion.status), 
              getStatusColor(suggestion.status)
            )}>
              {suggestion.status}
            </Badge>
          )}
        </div>
      </div>

      <div className="p-6">
        {isEditing ? (
          <div className="space-y-4 animate-[slideUpFade_0.3s_ease_both]">
            <textarea
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              className={cn(
                "w-full h-64 rounded-2xl bg-black/40 px-5 py-4 font-mono text-sm resize-none",
                "text-slate-200 border border-white/10 focus:outline-none focus:ring-1 focus:ring-primary-500/50 transition-all shadow-inner"
              )}
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={cancelEditing} className="rounded-full px-5 text-slate-400">
                <X className="h-4 w-4 mr-1.5" /> Cancel
              </Button>
              <Button size="sm" onClick={handleSave} className="rounded-full px-6 bg-primary-600 hover:bg-primary-500">
                <Check className="h-4 w-4 mr-1.5" /> Save Changes
              </Button>
            </div>
          </div>
        ) : (
          <div className="rounded-2xl overflow-hidden border border-white/5 shadow-inner">
            <DiffViewer original={suggestion.original_text} modified={displayText} />
          </div>
        )}
      </div>

      <div className="border-t border-white/5">
        <button
          onClick={(e) => { e.stopPropagation(); setIsExpanded(!isExpanded); }}
          className="flex items-center justify-between w-full px-6 py-4 text-xs font-bold uppercase tracking-[0.2em] text-slate-500 hover:bg-white/[0.02] transition-colors"
        >
          <div className="flex items-center gap-2">
            <MessageSquare className="h-3.5 w-3.5" />
            <span>AI Reasoning</span>
          </div>
          {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
        {isExpanded && (
          <div className="px-6 pb-6 text-sm text-slate-400 font-light leading-relaxed animate-[slideUpFade_0.3s_ease_both]">
            {suggestion.reasoning}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 p-5 border-t border-white/5 bg-black/10">
        <div className="flex items-center gap-4">
           <span className="text-[9px] uppercase tracking-[0.2em] text-slate-600 font-bold">
            Status: {suggestion.status}
          </span>
        </div>
        
        <div className="flex gap-2">
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={(e) => { e.stopPropagation(); startEditing(suggestion.id, displayText); }} 
            disabled={isLoading || !isPending}
            className="rounded-full px-4 text-slate-400 hover:text-white hover:bg-white/5"
          >
            <Pencil className="h-3.5 w-3.5 mr-1.5" /> Edit
          </Button>
          
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={(e) => { e.stopPropagation(); onReject(suggestion.id); }} 
            disabled={isLoading || !isPending} 
            className="rounded-full px-4 text-red-400/70 hover:text-red-400 hover:bg-red-500/10 border-none"
          >
            <X className="h-3.5 w-3.5 mr-1.5" /> Reject
          </Button>

          <Button 
            size="sm" 
            onClick={(e) => { e.stopPropagation(); onAccept(suggestion.id); }} 
            disabled={isLoading || !isPending}
            className="rounded-full px-6 bg-primary-600 hover:bg-primary-500 shadow-lg shadow-primary-900/20"
          >
            <Check className="h-3.5 w-3.5 mr-1.5" /> Accept
          </Button>
        </div>
      </div>
    </div>
  );
}