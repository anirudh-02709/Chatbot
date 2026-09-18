from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model_name: str = "gemma4:e4b"
    omniroute_base_url: str = "http://127.0.0.1:20128/v1"
    omniroute_model_name: str = "free-provider-fallback"
    default_generation_mode: str = "omniroute"  # 'local_gemma' | 'omniroute'
    model_name: str = "free-provider-fallback"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    request_timeout_seconds: float = 120.0
    enable_thinking: bool = True
    system_prompt: str = (
        "You are a helpful, accurate, and concise AI assistant. "
        "Provide direct, clear answers. Use markdown formatting and code blocks where appropriate. "
        "Be honest if you do not know something or if an instruction is unclear."
    )

    # File upload and storage configuration
    upload_dir: str = "storage/uploads"
    max_upload_size_bytes: int = 10 * 1024 * 1024  # 10 MB limit
    allowed_extensions: list[str] = [
        ".pdf",
        ".txt",
        ".md",
        ".csv",
        ".json",
        ".docx",
    ]
    allowed_mime_types: list[str] = [
        "application/pdf",
        "text/plain",
        "text/markdown",
        "text/x-markdown",
        "text/csv",
        "application/csv",
        "application/json",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    ]

    # Document Chunking Configuration
    default_chunk_size: int = 1000  # Target characters per chunk (~200-250 tokens)
    default_chunk_overlap: int = 150  # Overlap characters between contiguous split chunks
    min_chunk_size: int = 100  # Minimum character length to avoid tiny trailing fragments

    # Local Embedding Configuration
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    embedding_batch_size: int = 32
    embedding_timeout_seconds: float = 60.0

    # Local Vector Store & Retrieval Configuration
    vector_store_dir: str = "storage/vector_store"
    similarity_top_k: int = 5
    similarity_min_score: float = 0.0

    # RAG (Retrieval-Augmented Generation) Configuration
    rag_enabled: bool = True
    rag_top_k: int = 5
    rag_candidate_pool_size: int = 10
    rag_min_score: float = 0.48
    rag_max_context_characters: int = 12000

    # Web Search Configuration (Goal 10.5)
    web_search_provider: str = "tavily"
    web_search_api_key: Optional[str] = None
    web_search_base_url: Optional[str] = None
    web_search_timeout_seconds: float = 10.0
    web_search_max_results: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
