from datetime import datetime, timezone
import logging
from typing import Optional

from app.config import Settings, get_settings
from app.models.retrieval import (
    StoredVector,
    IndexSummaryResponse,
    DeleteIndexResponse,
)
from app.services.document_processor import DocumentProcessingService
from app.services.document_chunker import DocumentChunker, document_chunker
from app.services.embedding_service import EmbeddingService, embedding_service
from app.services.vector_store import LocalVectorStore, local_vector_store

logger = logging.getLogger("chatbot.vector_index_service")


class VectorIndexService:
    """Service to coordinate document parsing, chunking, embedding, and vector persistence."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        processor: Optional[DocumentProcessingService] = None,
        chunker: Optional[DocumentChunker] = None,
        embedding_svc: Optional[EmbeddingService] = None,
        vector_store: Optional[LocalVectorStore] = None,
    ):
        self.settings = settings or get_settings()
        self.processor = processor or DocumentProcessingService(settings=self.settings)
        self.chunker = chunker or document_chunker
        self.embedding_svc = embedding_svc or embedding_service
        self.vector_store = vector_store or local_vector_store

    async def index_attachment(
        self,
        attachment_id: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> IndexSummaryResponse:
        """
        Processes, chunks, embeds, and indexes an attachment in the local vector store.
        Atomically replaces any previous vectors for the attachment.
        """
        # 1. Parse document
        parsed_doc = self.processor.process_attachment(attachment_id)

        # 2. Chunk document
        chunks_res = self.chunker.chunk_document(
            parsed_doc=parsed_doc,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        # 3. Generate embeddings
        embeddings, _ = await self.embedding_svc.embed_chunks(
            chunks=chunks_res.chunks,
            attachment_id=attachment_id,
            filename=parsed_doc.filename,
            include_preview=False,
        )

        # 4. Convert to StoredVector objects
        stored_vectors: list[StoredVector] = []
        for chunk, emb in zip(chunks_res.chunks, embeddings):
            stored_vectors.append(
                StoredVector(
                    chunk_id=chunk.id,
                    attachment_id=attachment_id,
                    document_section_index=chunk.document_section_index,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    embedding=emb.vector,
                    character_count=chunk.character_count,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    metadata=chunk.metadata,
                )
            )

        # 5. Persist atomically in local vector store
        indexed_count = self.vector_store.replace_attachment(attachment_id, stored_vectors)
        now_ts = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"Indexed {indexed_count} vectors for attachment {attachment_id} ({parsed_doc.filename})"
        )

        return IndexSummaryResponse(
            attachment_id=attachment_id,
            filename=parsed_doc.filename,
            model=self.settings.embedding_model,
            dimensions=self.settings.embedding_dimensions,
            chunk_count=len(chunks_res.chunks),
            indexed_count=indexed_count,
            indexed_at=now_ts,
        )

    def delete_attachment_index(self, attachment_id: str) -> DeleteIndexResponse:
        """Removes all indexed vectors for an attachment from the local vector store."""
        deleted = self.vector_store.delete_attachment(attachment_id)
        return DeleteIndexResponse(
            attachment_id=attachment_id,
            deleted_count=deleted,
            message=f"Deleted {deleted} indexed vector chunk(s) for attachment {attachment_id}.",
        )


# Global singleton instance
vector_index_service = VectorIndexService()
