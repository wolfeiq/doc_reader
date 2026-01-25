
export type QueryStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

export interface Query {
  id: string;
  query_text: string;
  status: QueryStatus;
  status_message: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  suggestion_count: number;
}

export interface QueryDetail extends Query {
  suggestions: Suggestion[];
}

export interface QueryCreate {
  query_text: string;
}

export type SuggestionStatus = 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'EDITED';

export interface Suggestion {
  id: string;
  query_id: string;
  section_id: string;
  original_text: string;
  suggested_text: string;
  reasoning: string;
  confidence: number;
  status: SuggestionStatus;
  edited_text: string | null;
  created_at: string;
  updated_at: string;
  section_title: string | null;
  file_path: string | null;
}

export interface SuggestionUpdate {
  status?: SuggestionStatus;
  edited_text?: string;
}

export interface SuggestionActionResponse {
  success: boolean;
  suggestion_id: string;
  section_id: string;
  message: string;
}

export interface Document {
  id: string;
  file_path: string;
  title: string | null;
  content: string;
  checksum: string;
  created_at: string;
  updated_at: string;
  sections: DocumentSection[];
}

export interface DocumentListItem {
  id: string;
  file_path: string;
  title: string | null;
  checksum: string;
  section_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentSection {
  section_id: string;
  section_title: string;
  original_content: string;
  preview_content: string; 
  suggestion_id: string | null;
  confidence: number | null;
}

export interface DocumentPreview {
  id: string;
  file_path: string;
  title: string;
  sections: DocumentSection[];
  has_pending_changes: boolean;
  pending_suggestion_count: number;
}

export interface SectionPreview {
  section_id: string;
  section_title: string | null;
  original_content: string;
  preview_content: string;
  suggestion_id: string | null;
  confidence: number | null;
}

export type UserAction = 'ACCEPTED' | 'REJECTED' | 'EDITED' | 'REVERTED';

export interface EditHistory {
  id: string;
  document_id: string | null;
  section_id: string | null;
  suggestion_id: string | null;
  old_content: string;
  new_content: string;
  user_action: UserAction;
  query_text: string | null;
  file_path: string | null;
  section_title: string | null;
  created_at: string;
}

export interface SSESuggestionEvent {
  suggestion_id: string;
  section_title: string | null;
  file_path: string;
  confidence: number;
  preview: string;
}

export interface SSECompletedEvent {
  total_suggestions: number;
  query_id: string;
}


