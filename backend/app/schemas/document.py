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
    sections: list[DocumentSectionResponse] = []


class DocumentListResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_path: str
    title: Optional[str] = None
    checksum: str
    created_at: datetime
    updated_at: datetime
    section_count: int = 0


class DocumentPreview(BaseModel):

    document: DocumentResponse
    preview_content: str
    pending_changes: list[dict] = []


class SectionDependencyResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_section_id: UUID
    target_section_id: UUID
    dependency_type: str
    # Include section info for display
    source_section_title: Optional[str] = None
    target_section_title: Optional[str] = None
    source_file_path: Optional[str] = None
    target_file_path: Optional[str] = None