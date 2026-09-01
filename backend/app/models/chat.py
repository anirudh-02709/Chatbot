from typing import Literal, Optional, Any
from pydantic import BaseModel, Field

from app.models.file import Attachment


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1)
    attachments: Optional[list[Attachment]] = None



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
