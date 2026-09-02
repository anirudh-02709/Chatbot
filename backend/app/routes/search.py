from fastapi import APIRouter, Depends, status

from app.config import Settings, get_settings
from app.models.retrieval import RetrievalRequest, RetrievalResponse
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/api/search", tags=["search"])


def get_retrieval_service(
    settings: Settings = Depends(get_settings),
) -> RetrievalService:
    return RetrievalService(settings=settings)


@router.post(
    "",
    response_model=RetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic similarity search across indexed document vectors",
    response_description="Ranked list of document chunks with provenance sorted by descending cosine similarity",
)
async def search_endpoint(
    request: RetrievalRequest,
    retrieval_svc: RetrievalService = Depends(get_retrieval_service),
):
    """
    Embeds the user search query using local nomic-embed-text, performs cosine similarity
    search over stored float32 vector chunks in the local SQLite store, filters by optional
    min_score and attachment_id, and returns top_k ranked chunks with full section/page provenance.
    """
    return await retrieval_svc.search(
        query=request.query,
        top_k=request.top_k,
        min_score=request.min_score,
        attachment_id=request.attachment_id,
        attachment_ids=request.attachment_ids,
    )
