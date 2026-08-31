from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from app.models.chat import ChatRequest, ModelInfoResponse, HealthResponse
from app.services.ollama import OllamaService
from app.config import Settings, get_settings

router = APIRouter(prefix="/api", tags=["chat"])


def get_ollama_service(settings: Settings = Depends(get_settings)) -> OllamaService:
    return OllamaService(settings=settings)


@router.post(
    "/chat",
    summary="Stream chat response from Gemma / Ollama",
    response_description="Server-Sent Events stream with assistant response tokens",
)
async def chat_endpoint(
    request: ChatRequest,
    ollama_service: OllamaService = Depends(get_ollama_service),
):
    """
    Generate an assistant response for the conversation history.
    Normalizes Ollama NDJSON into application-level Server-Sent Events.
    """
    return StreamingResponse(
        ollama_service.stream_chat(request.messages),
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
