import logging
from typing import Optional
from fastapi import HTTPException, status

from app.config import Settings, get_settings
from app.models.retrieval import RetrievalResponse
from app.services.embedding_service import EmbeddingService, embedding_service
from app.services.vector_store import LocalVectorStore, local_vector_store

logger = logging.getLogger("chatbot.retrieval_service")


class RetrievalService:
    """Service to perform semantic retrieval over indexed document vectors."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        embedding_svc: Optional[EmbeddingService] = None,
        vector_store: Optional[LocalVectorStore] = None,
    ):
        self.settings = settings or get_settings()
        self.embedding_svc = embedding_svc or embedding_service
        self.vector_store = vector_store or local_vector_store

    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
        attachment_id: Optional[str] = None,
        attachment_ids: Optional[list[str]] = None,
    ) -> RetrievalResponse:
        """
        Embeds a search query and performs cosine-similarity search against local vectors.
        Supports single or multiple attachment filters.
        """
        clean_query = query.strip() if query else ""
        if not clean_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query cannot be empty or whitespace.",
            )

        effective_top_k = top_k if top_k is not None else self.settings.similarity_top_k
        effective_min_score = min_score if min_score is not None else self.settings.similarity_min_score

        # Bound top_k
        effective_top_k = max(1, min(50, effective_top_k))

        try:
            # 1. Generate embedding for search query (embedded once)
            query_vector = await self.embedding_svc.provider.embed_text(clean_query)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Query embedding generation failed: {e}",
            )

        # 2. Search local vector store
        try:
            results = self.vector_store.search(
                query_vector=query_vector,
                top_k=effective_top_k,
                min_score=effective_min_score,
                attachment_id=attachment_id,
                attachment_ids=attachment_ids,
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Vector search execution failed.",
            )

        logger.info(
            f"Semantic search for '{clean_query[:50]}' returned {len(results)} results (top_k={effective_top_k})"
        )

        return RetrievalResponse(
            query=clean_query,
            model=self.settings.embedding_model,
            dimensions=self.settings.embedding_dimensions,
            result_count=len(results),
            results=results,
        )


# Global singleton instance
retrieval_service = RetrievalService()
