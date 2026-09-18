import logging
from typing import Any, Optional
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.models.tool import ToolResult
from app.models.retrieval import RetrievalResponse
from app.tools.base import BaseTool
from app.services.retrieval_service import RetrievalService, retrieval_service
from app.services.rag_service import RAGService, rag_service

logger = logging.getLogger("chatbot.tools.document_search")


class DocumentSearchInput(BaseModel):
    """Input parameters for the DocumentSearchTool."""

    query: str = Field(
        ...,
        min_length=1,
        description="The search query or keywords to find relevant document excerpts for.",
    )
    top_k: Optional[int] = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of relevant chunks to retrieve (1 to 50, default: 5).",
    )
    attachment_ids: Optional[list[str]] = Field(
        default=None,
        description="Optional list of attachment IDs to filter the search to specific documents.",
    )
    attachment_id: Optional[str] = Field(
        default=None,
        description="Optional single attachment ID to filter the search.",
    )


class DocumentSearchTool(BaseTool):
    """
    Tool exposing the AI Assistant's semantic document retrieval capability.

    Directly reuses the existing RetrievalService and RAGService as the single source
    of truth for vector embedding and cosine-similarity retrieval, preserving complete
    chunk provenance without generating answers.
    """

    name = "document_search"
    description = (
        "Searches reference documents using semantic retrieval to find relevant excerpts and evidence. "
        "Returns ranked document chunks with similarity scores, section titles, and chunk identifiers."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query or keywords to find relevant document excerpts for.",
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of relevant chunks to retrieve (1 to 50, default: 5).",
            },
            "attachment_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of attachment IDs to filter the search to specific documents.",
            },
            "attachment_id": {
                "type": "string",
                "description": "Optional single attachment ID to filter the search.",
            },
        },
        "required": ["query"],
    }
    args_model = DocumentSearchInput

    def __init__(
        self,
        retrieval_svc: Optional[RetrievalService] = None,
        rag_svc: Optional[RAGService] = None,
    ):
        self.retrieval_svc = retrieval_svc or retrieval_service
        self.rag_svc = rag_svc or rag_service

    async def execute(
        self,
        query: str,
        top_k: Optional[int] = None,
        attachment_ids: Optional[list[str]] = None,
        attachment_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """
        Asynchronously executes semantic search over indexed document chunks.
        Preserves provenance and returns structured results without generating text.
        """
        clean_query = query.strip() if query else ""
        if not clean_query:
            return ToolResult.fail(
                tool_name=self.name,
                error="Search query cannot be empty or whitespace.",
                error_type="ToolInputValidationError",
            )

        effective_top_k = top_k if top_k is not None else 5
        if effective_top_k < 1 or effective_top_k > 50:
            return ToolResult.fail(
                tool_name=self.name,
                error=f"top_k must be between 1 and 50 (got {effective_top_k}).",
                error_type="ToolInputValidationError",
            )

        # Normalize attachment filters
        combined_ids: list[str] = []
        if attachment_ids:
            for aid in attachment_ids:
                if aid and isinstance(aid, str) and aid.strip():
                    combined_ids.append(aid.strip())
        if attachment_id and isinstance(attachment_id, str) and attachment_id.strip():
            clean_aid = attachment_id.strip()
            if clean_aid not in combined_ids:
                combined_ids.append(clean_aid)

        effective_ids = combined_ids if combined_ids else None

        # Just-In-Time (JIT) index specified attachments if needed
        if self.rag_svc and effective_ids:
            try:
                await self.rag_svc.ensure_attachments_indexed(effective_ids)
            except HTTPException as he:
                logger.warning(f"JIT indexing returned HTTP error for {effective_ids}: {he.detail}")
                return ToolResult.fail(
                    tool_name=self.name,
                    error=f"Attachment indexing error ({he.status_code}): {he.detail}",
                    error_type="AttachmentNotFoundError" if he.status_code == 404 else "IndexingError",
                    metadata={"attachment_ids": effective_ids},
                )
            except Exception as e:
                logger.error(f"Unexpected JIT indexing failure for {effective_ids}: {e}")
                return ToolResult.fail(
                    tool_name=self.name,
                    error=f"Attachment indexing failed: {e}",
                    error_type=type(e).__name__,
                    metadata={"attachment_ids": effective_ids},
                )

        # Execute semantic retrieval via existing RetrievalService
        try:
            res: RetrievalResponse = await self.retrieval_svc.search(
                query=clean_query,
                top_k=effective_top_k,
                attachment_ids=effective_ids,
            )
        except HTTPException as he:
            logger.warning(f"RetrievalService HTTP error for query '{clean_query}': {he.detail}")
            return ToolResult.fail(
                tool_name=self.name,
                error=f"Document retrieval failed ({he.status_code}): {he.detail}",
                error_type="RetrievalServiceError",
                metadata={"query": clean_query, "attachment_ids": effective_ids},
            )
        except Exception as e:
            logger.error(f"Unexpected error in RetrievalService: {e}")
            return ToolResult.fail(
                tool_name=self.name,
                error=f"Document retrieval failed: {e}",
                error_type=type(e).__name__,
                metadata={"query": clean_query, "attachment_ids": effective_ids},
            )

        # Structure retrieved chunks preserving complete provenance
        chunks_data = [
            {
                "chunk_id": r.chunk_id,
                "attachment_id": r.attachment_id,
                "section_title": r.section_title or f"Section {r.document_section_index + 1}",
                "document_section_index": r.document_section_index,
                "chunk_index": r.chunk_index,
                "page_number": r.page_number,
                "similarity_score": round(r.similarity_score, 4),
                "content": r.content,
                "metadata": r.metadata,
            }
            for r in res.results
        ]

        logger.info(
            f"DocumentSearchTool executed for '{clean_query[:50]}': retrieved {len(chunks_data)} chunks (top_k={effective_top_k})"
        )

        return ToolResult.ok(
            tool_name=self.name,
            data={
                "query": clean_query,
                "result_count": len(chunks_data),
                "chunks": chunks_data,
            },
            metadata={
                "query": clean_query,
                "top_k": effective_top_k,
                "result_count": len(chunks_data),
                "attachment_ids": effective_ids,
                "top_score": chunks_data[0]["similarity_score"] if chunks_data else 0.0,
                "chunk_ids": [c["chunk_id"] for c in chunks_data],
            },
        )


# Global singleton instance
document_search_tool = DocumentSearchTool()
