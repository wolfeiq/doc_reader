/**
 * Frontend TypeScript Type Definitions
 * =====================================
 *
 * This file contains all TypeScript interfaces and types for the application.
 * Types are organized by domain: Query, Suggestion, Document, History, SSE, UI.
 *
 * Type Safety Strategy:
 * ---------------------
 * - All API responses have corresponding TypeScript interfaces
 * - Interfaces mirror backend Pydantic schemas for consistency
 * - Union types used for enums (QueryStatus, SuggestionStatus)
 * - Nullable fields explicitly typed as `T | null`
 *
 * Naming Conventions:
 * -------------------
 * - Interfaces: PascalCase (Query, Suggestion)
 * - Type aliases: PascalCase (QueryStatus)
 * - Props interfaces: ComponentNameProps (QueryInputProps)
 * - API request types: EntityCreate, EntityUpdate
 * - API response types: Entity, EntityDetail, EntityListItem
 *
 * Production Considerations:
 * --------------------------
 * - Consider using Zod for runtime validation of API responses
 * - Add JSDoc comments for complex interfaces
 * - Consider generating types from OpenAPI spec (openapi-typescript)
 * - Add strict null checks in tsconfig.json
 */

// =============================================================================
// Query Types - Documentation update requests
// =============================================================================

/** Status of a query in the processing pipeline */
export type QueryStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

/**
 * A documentation update query (list view).
 * Contains summary info without full suggestions.
 */
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

/**
 * A query with its full suggestions (detail view).
 * Used on the review page.
 */
export interface QueryDetail extends Query {
  suggestions: Suggestion[];
}

/** Request body for creating a new query */
export interface QueryCreate {
  query_text: string;
}

// =============================================================================
// Suggestion Types - AI-generated edit proposals
// =============================================================================

/** Status of a suggestion in the review workflow */
export type SuggestionStatus = 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'EDITED';

/**
 * An AI-generated edit suggestion.
 * Shown in SuggestionCard with diff viewer.
 */
export interface Suggestion {
  id: string;
  query_id: string;
  section_id: string;
  document_id: string;
  original_text: string;      // Current content
  suggested_text: string;     // AI's proposed content
  reasoning: string;          // AI's explanation
  confidence: number;         // 0.0-1.0 confidence score
  status: SuggestionStatus;
  edited_text: string | null; // User's modified version (if edited)
  created_at: string;
  updated_at: string;
  section_title: string | null;
  file_path: string | null;
}

/** Request body for updating a suggestion */
export interface SuggestionUpdate {
  status?: SuggestionStatus;
  edited_text?: string;
}

/** Response from accept/reject suggestion actions */
export interface SuggestionActionResponse {
  success: boolean;
  suggestion_id: string;
  section_id: string;
  message: string;
}

// =============================================================================
// Document Types - Documentation files and sections
// =============================================================================

/** A full document with all its content and sections */
export interface Document {
  id: string;
  file_path: string;
  title: string | null;
  content: string;       // Full raw content
  checksum: string;      // SHA-256 for change detection
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


export interface SidebarProps {
  className?: string;
}

export interface QueryInputProps {
  onSubmit: (query: string) => void;
  isLoading?: boolean;
}

export interface DiffViewerProps {
  original: string;
  modified: string;
}

export interface SuggestionCardProps {
  suggestion: Suggestion;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  onSave: (id: string, text: string) => void;
  isLoading?: boolean;
}

export interface SuggestionListProps {
  suggestions: Suggestion[];
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  onSave: (id: string, text: string) => void;
  isLoading?: boolean;
}

export type ChangeType = 'none' | 'pending' | 'accepted' | 'rejected';

export type FilterVariant = 'all' | 'pending' | 'accepted' | 'rejected';

export interface Section {
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

export interface DiffSegment {
  type: 'unchanged' | 'added' | 'removed';
  text: string;
}

export interface DocumentPreviewUnique {
  id: string;
  file_path: string;
  title: string;
  sections: Section[];
  has_pending_changes: boolean;
  pending_suggestion_count: number;
  has_recent_changes: boolean;
  recent_change_count: number;
}