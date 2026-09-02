from typing import Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

DocumentStatus = Literal["pending", "processing", "processed", "error"]

MetadataValue = Union[str, int, float, bool, list[str], None]


class DocumentSection(BaseModel):
    index: int
    title: Optional[str] = None
    content: str
    page_number: Optional[int] = Field(default=None, alias="pageNumber", serialization_alias="pageNumber")
    character_count: int = Field(..., alias="characterCount", serialization_alias="characterCount")
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class ParsedDocument(BaseModel):
    attachment_id: str = Field(..., alias="attachmentId", serialization_alias="attachmentId")
    filename: str
    mime_type: str = Field(..., alias="mimeType", serialization_alias="mimeType")
    size: int
    status: DocumentStatus
    total_characters: int = Field(..., alias="totalCharacters", serialization_alias="totalCharacters")
    page_count: Optional[int] = Field(default=None, alias="pageCount", serialization_alias="pageCount")
    section_count: int = Field(..., alias="sectionCount", serialization_alias="sectionCount")
    processed_at: str = Field(..., alias="processedAt", serialization_alias="processedAt")
    sections: list[DocumentSection] = Field(default_factory=list)
    error_detail: Optional[str] = Field(default=None, alias="errorDetail", serialization_alias="errorDetail")
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class DocumentChunk(BaseModel):
    id: str
    attachment_id: str = Field(..., alias="attachmentId", serialization_alias="attachmentId")
    document_section_index: int = Field(..., alias="documentSectionIndex", serialization_alias="documentSectionIndex")
    chunk_index: int = Field(..., alias="chunkIndex", serialization_alias="chunkIndex")
    content: str
    character_count: int = Field(..., alias="characterCount", serialization_alias="characterCount")
    page_number: Optional[int] = Field(default=None, alias="pageNumber", serialization_alias="pageNumber")
    section_title: Optional[str] = Field(default=None, alias="sectionTitle", serialization_alias="sectionTitle")
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class DocumentChunksResponse(BaseModel):
    attachment_id: str = Field(..., alias="attachmentId", serialization_alias="attachmentId")
    filename: str
    total_chunks: int = Field(..., alias="totalChunks", serialization_alias="totalChunks")
    total_characters: int = Field(..., alias="totalCharacters", serialization_alias="totalCharacters")
    chunk_size: int = Field(..., alias="chunkSize", serialization_alias="chunkSize")
    chunk_overlap: int = Field(..., alias="chunkOverlap", serialization_alias="chunkOverlap")
    chunks: list[DocumentChunk] = Field(default_factory=list)

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )
