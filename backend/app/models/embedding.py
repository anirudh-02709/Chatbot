from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentEmbedding(BaseModel):
    chunk_id: str = Field(..., alias="chunkId", serialization_alias="chunkId")
    attachment_id: str = Field(..., alias="attachmentId", serialization_alias="attachmentId")
    model: str
    dimensions: int
    vector: list[float]

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class EmbeddingPreview(BaseModel):
    chunk_id: str = Field(..., alias="chunkId", serialization_alias="chunkId")
    character_count: int = Field(..., alias="characterCount", serialization_alias="characterCount")
    vector_preview: list[float] = Field(..., alias="vectorPreview", serialization_alias="vectorPreview")
    vector_norm: float = Field(..., alias="vectorNorm", serialization_alias="vectorNorm")

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class EmbeddingSummaryResponse(BaseModel):
    attachment_id: str = Field(..., alias="attachmentId", serialization_alias="attachmentId")
    filename: str
    model: str
    dimensions: int
    chunk_count: int = Field(..., alias="chunkCount", serialization_alias="chunkCount")
    embedded_count: int = Field(..., alias="embeddedCount", serialization_alias="embeddedCount")
    preview: Optional[list[EmbeddingPreview]] = None

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )
