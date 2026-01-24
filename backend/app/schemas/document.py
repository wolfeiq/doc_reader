
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field





class DocumentSectionBase(BaseModel):

    section_title: str | None = None
    content: str
    order: int = Field(default=0, ge=0)
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)


class DocumentSectionCreate(DocumentSectionBase):

    pass


class DocumentSectionResponse(DocumentSectionBase):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    embedding_id: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentSectionInfo(BaseModel):

    id: UUID
    section_title: str | None = None
    content: str
    order: int = Field(ge=0)
    start_line: int | None = None
    end_line: int | None = None



class DocumentBase(BaseModel):

    file_path: str = Field(..., min_length=1, max_length=500)
    title: str | None = None
    content: str


class DocumentCreate(DocumentBase):

    pass


class DocumentUpdate(BaseModel):

    title: str | None = None
    content: str | None = None


class DocumentResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_path: str
    title: str | None = None
    content: str
    checksum: str
    created_at: datetime
    updated_at: datetime
    sections: list[DocumentSectionResponse] = Field(default_factory=list)


class DocumentListResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_path: str
    title: str | None = None
    checksum: str
    created_at: datetime
    updated_at: datetime
    section_count: int = Field(default=0, ge=0)



class SectionPreview(BaseModel):

    section_id: UUID
    section_title: str | None = None
    original_content: str
    preview_content: str
    suggestion_id: UUID | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class DocumentPreviewResponse(BaseModel):

    id: UUID
    file_path: str
    title: str | None = None
    sections: list[SectionPreview]
    has_pending_changes: bool
    pending_suggestion_count: int = Field(ge=0)


class DocumentPreview(BaseModel):

    document: DocumentResponse
    preview_content: str
    pending_changes: list[dict[str, object]] = Field(default_factory=list)




class DependencyNode(BaseModel):

    section_id: UUID
    section_title: str | None = None
    file_path: str
    document_id: UUID


class DependencyEdge(BaseModel):
    source_section_id: UUID
    target_section_id: UUID
    dependency_type: str


class SectionDependencyInfo(BaseModel):
    dependency_id: UUID
    section_id: UUID
    section_title: str | None = None
    dependency_type: str


class SectionDependenciesResponse(BaseModel):

    incoming: list[SectionDependencyInfo] = Field(default_factory=list)
    outgoing: list[SectionDependencyInfo] = Field(default_factory=list)


class DependencyGraphResponse(BaseModel):

    nodes: list[DependencyNode] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)



class ReindexResponse(BaseModel):

    success: bool
    document_id: UUID
    sections_indexed: int = Field(ge=0)


class SectionDependencyResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_section_id: UUID
    target_section_id: UUID
    dependency_type: str
    source_section_title: str | None = None
    target_section_title: str | None = None
    source_file_path: str | None = None
    target_file_path: str | None = None