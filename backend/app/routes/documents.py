from typing import Optional
from fastapi import APIRouter, Depends, Path, Query, status

from app.config import Settings, get_settings
from app.models.document import ParsedDocument, DocumentChunksResponse
from app.models.embedding import EmbeddingSummaryResponse
from app.models.retrieval import IndexSummaryResponse, DeleteIndexResponse
from app.services.document_processor import DocumentProcessingService
from app.services.document_chunker import DocumentChunker
from app.services.embedding_service import EmbeddingService
from app.services.vector_index_service import VectorIndexService

router = APIRouter(prefix="/api/files", tags=["documents"])


def get_document_processor(
    settings: Settings = Depends(get_settings),
) -> DocumentProcessingService:
    return DocumentProcessingService(settings=settings)


def get_document_chunker(
    settings: Settings = Depends(get_settings),
) -> DocumentChunker:
    return DocumentChunker(settings=settings)


def get_embedding_service(
    settings: Settings = Depends(get_settings),
) -> EmbeddingService:
    return EmbeddingService(settings=settings)


def get_vector_index_service(
    settings: Settings = Depends(get_settings),
) -> VectorIndexService:
    return VectorIndexService(settings=settings)


@router.post(
    "/{attachment_id}/process",
    response_model=ParsedDocument,
    status_code=status.HTTP_200_OK,
    summary="Process and extract structured text from an uploaded attachment",
    response_description="Parsed document representation with extracted sections and provenance metadata",
)
async def process_document_endpoint(
    attachment_id: str = Path(..., description="Unique attachment ID to process (e.g. att_12345)"),
    processor: DocumentProcessingService = Depends(get_document_processor),
):
    """
    Locates an existing uploaded attachment file within the storage boundary,
    selects the appropriate format parser (PDF, DOCX, TXT, MD, CSV, JSON),
    extracts structured sections with page/heading provenance, and returns the normalized document.
    """
    return processor.process_attachment(attachment_id)


@router.post(
    "/{attachment_id}/chunks",
    response_model=DocumentChunksResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate retrieval-ready chunks from an uploaded document",
    response_description="Structured document chunks with location provenance and overlap",
)
async def get_document_chunks_endpoint(
    attachment_id: str = Path(..., description="Unique attachment ID to chunk (e.g. att_12345)"),
    chunk_size: Optional[int] = Query(None, description="Max characters per chunk (default from config)"),
    chunk_overlap: Optional[int] = Query(None, description="Overlap characters between contiguous chunks"),
    processor: DocumentProcessingService = Depends(get_document_processor),
    chunker: DocumentChunker = Depends(get_document_chunker),
):
    """
    Parses the document into sections and splits content into retrieval-ready chunks
    using natural boundary hierarchies (paragraphs, sentences, words) while preserving
    page numbers, section titles, and source provenance.
    """
    parsed_doc = processor.process_attachment(attachment_id)
    return chunker.chunk_document(
        parsed_doc=parsed_doc,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


@router.post(
    "/{attachment_id}/embeddings",
    response_model=EmbeddingSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate local vector embeddings for an uploaded document's chunks",
    response_description="Summary of generated dense embeddings including dimensions and chunk counts",
)
async def get_document_embeddings_endpoint(
    attachment_id: str = Path(..., description="Unique attachment ID to embed (e.g. att_12345)"),
    include_preview: bool = Query(False, description="Include small preview of first 5 embedding vectors and norms"),
    chunk_size: Optional[int] = Query(None, description="Max characters per chunk (default from config)"),
    chunk_overlap: Optional[int] = Query(None, description="Overlap characters between contiguous chunks"),
    processor: DocumentProcessingService = Depends(get_document_processor),
    chunker: DocumentChunker = Depends(get_document_chunker),
    embedding_svc: EmbeddingService = Depends(get_embedding_service),
):
    """
    End-to-end pipeline endpoint:
    1. Parses document into structured sections
    2. Splits sections into natural-boundary chunks
    3. Generates 768-dimensional local vector embeddings via Ollama (nomic-embed-text)
    4. Returns structured embedding metadata without exposing giant vectors by default
    """
    parsed_doc = processor.process_attachment(attachment_id)
    chunks_response = chunker.chunk_document(
        parsed_doc=parsed_doc,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    _, summary = await embedding_svc.embed_chunks(
        chunks=chunks_response.chunks,
        attachment_id=attachment_id,
        filename=parsed_doc.filename,
        include_preview=include_preview,
    )
    return summary


@router.post(
    "/{attachment_id}/index",
    response_model=IndexSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Index or atomically replace an attachment in the local vector store",
    response_description="Summary of indexed vector chunks persisted locally",
)
async def index_document_endpoint(
    attachment_id: str = Path(..., description="Unique attachment ID to index (e.g. att_12345)"),
    chunk_size: Optional[int] = Query(None, description="Max characters per chunk (default from config)"),
    chunk_overlap: Optional[int] = Query(None, description="Overlap characters between contiguous chunks"),
    index_svc: VectorIndexService = Depends(get_vector_index_service),
):
    """
    Parses, chunks, embeds, and persistently stores the attachment's vector representations
    in the local SQLite vector store under backend/storage/vector_store/vectors.db.
    Atomically replaces any existing vectors for the attachment.
    """
    return await index_svc.index_attachment(
        attachment_id=attachment_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


@router.delete(
    "/{attachment_id}/index",
    response_model=DeleteIndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete all indexed vectors for an attachment from the local vector store",
    response_description="Number of deleted vector records",
)
async def delete_document_index_endpoint(
    attachment_id: str = Path(..., description="Unique attachment ID to remove from index"),
    index_svc: VectorIndexService = Depends(get_vector_index_service),
):
    """
    Deletes all vector chunks belonging to the specified attachment from the local SQLite index.
    """
    return index_svc.delete_attachment_index(attachment_id=attachment_id)
