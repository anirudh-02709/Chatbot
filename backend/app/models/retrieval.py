from typing import Optional, Union
from pydantic import BaseModel, ConfigDict, Field

MetadataValue = Union[str, int, float, bool, list[str], None]


class StoredVector(BaseModel):
    chunk_id: str = Field(..., alias="chunkId", serialization_alias="chunkId")
    attachment_id: str = Field(..., alias="attachmentId", serialization_alias="attachmentId")
    document_section_index: int = Field(..., alias="documentSectionIndex", serialization_alias="documentSectionIndex")
    chunk_index: int = Field(..., alias="chunkIndex", serialization_alias="chunkIndex")
    content: str
    embedding: list[float]
    character_count: int = Field(..., alias="characterCount", serialization_alias="characterCount")
    page_number: Optional[int] = Field(default=None, alias="pageNumber", serialization_alias="pageNumber")
    section_title: Optional[str] = Field(default=None, alias="sectionTitle", serialization_alias="sectionTitle")
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class RetrievalResult(BaseModel):
    chunk_id: str = Field(..., alias="chunkId", serialization_alias="chunkId")
    attachment_id: str = Field(..., alias="attachmentId", serialization_alias="attachmentId")
    content: str
    similarity_score: float = Field(..., alias="similarityScore", serialization_alias="similarityScore")
    document_section_index: int = Field(..., alias="documentSectionIndex", serialization_alias="documentSectionIndex")
    chunk_index: int = Field(..., alias="chunkIndex", serialization_alias="chunkIndex")
    page_number: Optional[int] = Field(default=None, alias="pageNumber", serialization_alias="pageNumber")
    section_title: Optional[str] = Field(default=None, alias="sectionTitle", serialization_alias="sectionTitle")
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class RetrievalRequest(BaseModel):
    query: str
    top_k: Optional[int] = Field(default=None, alias="topK", serialization_alias="topK")
    min_score: Optional[float] = Field(default=None, alias="minScore", serialization_alias="minScore")
    attachment_id: Optional[str] = Field(default=None, alias="attachmentId", serialization_alias="attachmentId")
    attachment_ids: Optional[list[str]] = Field(default=None, alias="attachmentIds", serialization_alias="attachmentIds")

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class RetrievalResponse(BaseModel):
    query: str
    model: str
    dimensions: int
    result_count: int = Field(..., alias="resultCount", serialization_alias="resultCount")
    results: list[RetrievalResult] = Field(default_factory=list)

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class IndexSummaryResponse(BaseModel):
    attachment_id: str = Field(..., alias="attachmentId", serialization_alias="attachmentId")
    filename: str
    model: str
    dimensions: int
    chunk_count: int = Field(..., alias="chunkCount", serialization_alias="chunkCount")
    indexed_count: int = Field(..., alias="indexedCount", serialization_alias="indexedCount")
    indexed_at: str = Field(..., alias="indexedAt", serialization_alias="indexedAt")

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class DeleteIndexResponse(BaseModel):
    attachment_id: str = Field(..., alias="attachmentId", serialization_alias="attachmentId")
    deleted_count: int = Field(..., alias="deletedCount", serialization_alias="deletedCount")
    message: str

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )
