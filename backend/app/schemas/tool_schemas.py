from __future__ import annotations
from uuid import UUID
from typing import Any, Literal, Optional, Union, TypedDict
from pydantic import BaseModel, Field, ConfigDict

model_config = ConfigDict(from_attributes=True)


class SearchResultItem(BaseModel):
    section_id: str
    document_id: str | None = None 
    section_title: str | None = None
    file_path: Optional[str] = None
    content_preview: Optional[str] = None 
    score: float = Field(ge=0.0, le=1.0)

class DependencyInfo(BaseModel):
    dependency_id: str
    section_id: str
    section_title: str | None = None
    dependency_type: str

class DocumentStructureSection(BaseModel):
    section_id: str
    title: str | None = None
    order: int = Field(ge=0)

class SemanticSearchArgs(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)
    n_results: int = Field(default=10, ge=1, le=20)
    file_path_filter: str | None = None

class GetSectionContentArgs(BaseModel):
    section_id: UUID  

class FindDependenciesArgs(BaseModel):
    section_id: UUID
    direction: Literal["incoming", "outgoing", "both"] = "both"

class ProposeEditArgs(BaseModel):
    section_id: UUID
    suggested_text: str = Field(..., min_length=1)
    reasoning: str = Field(..., min_length=1)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

class GetDocumentStructureArgs(BaseModel):
    document_id: UUID

class SearchByFilePathArgs(BaseModel):
    path_pattern: str = Field(..., min_length=1)


class SearchResult(BaseModel):
    results: list[SearchResultItem]
    count: int
    query: str

class SectionResult(BaseModel):
    section_id: str
    section_title: str | None = None
    content: str
    file_path: str | None = None
    order: int
    error: str | None = None

class DependencyResult(BaseModel):
    section_id: str
    dependencies: list[dict[str, Any]]

class ProposeEditResult(BaseModel):
    success: bool = True
    suggestion_id: str | None = None
    document_id: str | None = None
    section_id: str
    section_title: str | None = None
    file_path: str | None = None
    confidence: float
    error: str | None = None

class DocumentStructureResult(BaseModel):
    document_id: str
    file_path: str
    title: str | None = None
    sections: list[DocumentStructureSection]
    error: str | None = None

class FilePathSearchResult(BaseModel):
    results: list[dict[str, Any]]
    count: int
    pattern: str

class ToolError(BaseModel):
    error: str

class AgentStats(TypedDict):
    searches_performed: int
    sections_analyzed: int
    suggestions_created: int

class ProcessResult(TypedDict):
    query_id: str
    status: str
    searches_performed: int
    sections_analyzed: int
    suggestions_created: int
    error: str | None

ToolResult = Union[
    SearchResult,
    SectionResult,
    DependencyResult,
    ProposeEditResult,
    DocumentStructureResult,
    FilePathSearchResult,
    ToolError
]

TOOL_ARG_SCHEMAS: dict[str, type[BaseModel]] = {
    "semantic_search": SemanticSearchArgs,
    "get_section_content": GetSectionContentArgs,
    "find_dependencies": FindDependenciesArgs,
    "propose_edit": ProposeEditArgs,
    "get_document_structure": GetDocumentStructureArgs,
    "search_by_file_path": SearchByFilePathArgs,
}

def validate_tool_args(tool_name: str, args: dict[str, Any]) -> BaseModel:
    schema = TOOL_ARG_SCHEMAS.get(tool_name)
    if not schema:
        raise ValueError(f"Unknown tool: {tool_name}")
    return schema(**args)