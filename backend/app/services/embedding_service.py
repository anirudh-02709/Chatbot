import logging
import math
from typing import Optional
from fastapi import HTTPException, status

from app.config import Settings, get_settings
from app.models.document import DocumentChunk
from app.models.embedding import (
    DocumentEmbedding,
    EmbeddingPreview,
    EmbeddingSummaryResponse,
)
from app.services.embeddings.base import BaseEmbeddingProvider, EmbeddingError
from app.services.embeddings.ollama_provider import OllamaEmbeddingProvider

logger = logging.getLogger("chatbot.embedding_service")


class EmbeddingService:
    """Service to generate dense vector embeddings for DocumentChunks."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        provider: Optional[BaseEmbeddingProvider] = None,
    ):
        self.settings = settings or get_settings()
        self.provider = provider or OllamaEmbeddingProvider(settings=self.settings)

    async def embed_chunks(
        self,
        chunks: list[DocumentChunk],
        attachment_id: str,
        filename: str = "document",
        include_preview: bool = False,
    ) -> tuple[list[DocumentEmbedding], EmbeddingSummaryResponse]:
        """
        Generates dense vector embeddings for an ordered list of DocumentChunks.
        Returns a tuple of (full DocumentEmbedding objects, EmbeddingSummaryResponse).
        """
        if not chunks:
            summary = EmbeddingSummaryResponse(
                attachment_id=attachment_id,
                filename=filename,
                model=self.settings.embedding_model,
                dimensions=self.settings.embedding_dimensions,
                chunk_count=0,
                embedded_count=0,
                preview=[] if include_preview else None,
            )
            return [], summary

        texts = [c.content for c in chunks]

        try:
            logger.info(
                f"Generating embeddings for {len(chunks)} chunks of attachment {attachment_id} using {self.settings.embedding_model}"
            )
            vectors = await self.provider.embed_batch(texts)
        except EmbeddingError as ee:
            logger.warning(f"Embedding generation failed: {ee}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(ee),
            )
        except Exception as e:
            logger.error(f"Unexpected error during embedding generation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while generating embeddings.",
            )

        if len(vectors) != len(chunks):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Vector count mismatch: generated {len(vectors)} for {len(chunks)} chunks.",
            )

        dimensions = len(vectors[0]) if vectors else self.settings.embedding_dimensions
        embeddings: list[DocumentEmbedding] = []
        previews: list[EmbeddingPreview] = []

        for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
            embeddings.append(
                DocumentEmbedding(
                    chunk_id=chunk.id,
                    attachment_id=attachment_id,
                    model=self.settings.embedding_model,
                    dimensions=dimensions,
                    vector=vec,
                )
            )

            if include_preview and idx < 5:  # Preview first 5 items
                # Calculate vector norm sqrt(sum(x^2))
                norm = math.sqrt(sum(x * x for x in vec))
                previews.append(
                    EmbeddingPreview(
                        chunk_id=chunk.id,
                        character_count=chunk.character_count,
                        vector_preview=[round(x, 4) for x in vec[:5]],  # First 5 dimensions
                        vector_norm=round(norm, 4),
                    )
                )

        summary = EmbeddingSummaryResponse(
            attachment_id=attachment_id,
            filename=filename,
            model=self.settings.embedding_model,
            dimensions=dimensions,
            chunk_count=len(chunks),
            embedded_count=len(embeddings),
            preview=previews if include_preview else None,
        )

        logger.info(
            f"Successfully generated {len(embeddings)} embeddings ({dimensions} dim) for {attachment_id}"
        )
        return embeddings, summary


# Global singleton service
embedding_service = EmbeddingService()
