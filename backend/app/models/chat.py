from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)


class ModelInfoResponse(BaseModel):
    name: str
    architecture: str
    installed: bool
    loaded: bool
    runtime: str = "local"
    status: str
    details: Optional[dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    ollama: str
    model_installed: bool
    model_loaded: bool
