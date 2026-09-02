from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.models.chat import ChatRequest, ModelInfoResponse, HealthResponse
from app.services.ollama import OllamaService
from app.services.rag_service import RAGService
from app.config import Settings, get_settings

router = APIRouter(prefix="/api", tags=["chat"])


def get_ollama_service(settings: Settings = Depends(get_settings)) -> OllamaService:
    return OllamaService(settings=settings)


def get_rag_service(settings: Settings = Depends(get_settings)) -> RAGService:
    return RAGService(settings=settings)


@router.post(
    "/chat",
    summary="Stream chat response from Gemma / Ollama",
    response_description="Server-Sent Events stream with assistant response tokens",
)
async def chat_endpoint(
    request: ChatRequest,
    ollama_service: OllamaService = Depends(get_ollama_service),
    rag_svc: RAGService = Depends(get_rag_service),
):
    """
    Generate an assistant response for the conversation history.
    Retrieves grounded document context for user queries when attached or indexed documents exist,
    and normalizes Ollama NDJSON into application-level Server-Sent Events.
    """
    # 1. Extract latest user query and attachment IDs
    user_messages = [m for m in request.messages if m.role == "user"]
    latest_query = user_messages[-1].content if user_messages else ""

    attachment_ids: list[str] = []
    for msg in request.messages:
        if msg.attachments:
            for att in msg.attachments:
                if att.id and att.id not in attachment_ids:
                    attachment_ids.append(att.id)

    # 2. Retrieve relevant context via RAGService
    rag_results = await rag_svc.retrieve_context(
        query=latest_query,
        attachment_ids=attachment_ids if attachment_ids else None,
    )
    rag_context, rag_meta = rag_svc.build_rag_context_block(rag_results)

    # 3. Stream grounded assistant response
    return StreamingResponse(
        ollama_service.stream_chat(
            messages=request.messages,
            rag_context=rag_context,
            rag_meta=rag_meta,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/model",
    response_model=ModelInfoResponse,
    summary="Get sanitized model information and status",
)
async def model_info_endpoint(
    ollama_service: OllamaService = Depends(get_ollama_service),
):
    return await ollama_service.get_model_info()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System and Ollama health check",
)
async def health_endpoint(
    ollama_service: OllamaService = Depends(get_ollama_service),
):
    return await ollama_service.check_health()
