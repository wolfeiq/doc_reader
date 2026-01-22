from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class DocumentSectionBase(BaseModel):
    section_title: Optional[str] = None
    content: str
    order: int = 0
    start_line: Optional[int] = None
    end_line: Optional[int] = None


class DocumentSectionCreate(DocumentSectionBase):
    pass


class DocumentSectionResponse(DocumentSectionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    embedding_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DocumentSectionInfo(BaseModel):
    id: UUID
    section_title: Optional[str]
    content: str
    order: int
    start_line: Optional[int]
    end_line: Optional[int]


class DocumentBase(BaseModel):
    file_path: str
    title: Optional[str] = None
    content: str


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_path: str
    title: Optional[str] = None
    content: str
    checksum: str
    created_at: datetime
    updated_at: datetime
    sections: list[DocumentSectionResponse] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_path: str
    title: Optional[str] = None
    checksum: str
    created_at: datetime
    updated_at: datetime
    section_count: int = 0


class SectionPreview(BaseModel):
    section_id: UUID
    section_title: Optional[str]
    original_content: str
    preview_content: str
    suggestion_id: Optional[UUID]
    confidence: Optional[float]


class DocumentPreviewResponse(BaseModel):
    id: UUID
    file_path: str
    title: Optional[str]
    sections: list[SectionPreview]
    has_pending_changes: bool
    pending_suggestion_count: int


class DocumentPreview(BaseModel):
    document: DocumentResponse
    preview_content: str
    pending_changes: list[dict] = Field(default_factory=list)


class DependencyNode(BaseModel):
    section_id: UUID
    section_title: Optional[str]
    file_path: str
    document_id: UUID


class DependencyEdge(BaseModel):
    source_section_id: UUID
    target_section_id: UUID
    dependency_type: str


class SectionDependencyInfo(BaseModel):
    dependency_id: UUID
    section_id: UUID
    section_title: Optional[str]
    dependency_type: str


class SectionDependenciesResponse(BaseModel):
    incoming: list[SectionDependencyInfo]
    outgoing: list[SectionDependencyInfo]


class DependencyGraphResponse(BaseModel):
    nodes: list[DependencyNode]
    edges: list[DependencyEdge]


class ReindexResponse(BaseModel):
    success: bool
    document_id: UUID
    sections_indexed: int


class SectionDependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_section_id: UUID
    target_section_id: UUID
    dependency_type: str
    source_section_title: Optional[str] = None
    target_section_title: Optional[str] = None
    source_file_path: Optional[str] = None
    target_file_path: Optional[str] = None