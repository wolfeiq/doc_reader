from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator
from uuid import UUID



class SemanticSearchArgs(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000, description="Search query")
    n_results: int = Field(default=10, ge=1, le=20, description="Number of results")
    file_path_filter: str | None = Field(None, description="Optional file path filter")


class GetSectionContentArgs(BaseModel):
    section_id: str = Field(..., description="UUID of the section")
    
    @field_validator('section_id')
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        try:
            UUID(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid UUID format: {v}")


class FindDependenciesArgs(BaseModel):
    section_id: str = Field(..., description="UUID of the section")
    direction: Literal["incoming", "outgoing", "both"] = Field(
        default="both",
        description="Direction of dependencies"
    )
    
    @field_validator('section_id')
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        try:
            UUID(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid UUID format: {v}")


class ProposeEditArgs(BaseModel):
    section_id: str = Field(..., description="UUID of the section")
    suggested_text: str = Field(..., min_length=1, description="Proposed new content")
    reasoning: str = Field(..., min_length=1, description="Explanation of the edit")
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score"
    )
    
    @field_validator('section_id')
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        try:
            UUID(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid UUID format: {v}")


class GetDocumentStructureArgs(BaseModel):
    document_id: str = Field(..., description="UUID of the document")
    
    @field_validator('document_id')
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        try:
            UUID(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid UUID format: {v}")


class SearchByFilePathArgs(BaseModel):
    path_pattern: str = Field(..., min_length=1, description="File path pattern")



class SearchResult(BaseModel):
    section_id: str
    content: str | None
    metadata: dict[str, Any]
    score: float = Field(ge=0.0, le=1.0)


class SemanticSearchResponse(BaseModel):
    results: list[SearchResult]
    count: int = Field(ge=0)
    query: str


class SectionContentResponse(BaseModel):
    section_id: str
    section_title: str | None
    content: str
    file_path: str | None
    order: int = Field(ge=0)


class DependencyInfo(BaseModel):
    dependency_id: str
    section_id: str
    section_title: str | None
    dependency_type: str


class FindDependenciesResponse(BaseModel):
    section_id: str
    dependencies: dict[str, list[DependencyInfo]]


class ProposeEditResponse(BaseModel):
    success: bool
    suggestion_id: str
    section_id: str
    section_title: str | None
    file_path: str | None
    confidence: float = Field(ge=0.0, le=1.0)


class SectionInfo(BaseModel):
    section_id: str
    title: str | None
    order: int = Field(ge=0)


class GetDocumentStructureResponse(BaseModel):
    document_id: str
    file_path: str
    title: str | None
    sections: list[SectionInfo]


class SearchByFilePathResponse(BaseModel):
    results: list[SearchResult]
    count: int = Field(ge=0)
    pattern: str


class ToolErrorResponse(BaseModel):
    error: str
    details: str | None = None

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