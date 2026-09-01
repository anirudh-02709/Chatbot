from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    ollama_base_url: str = "http://127.0.0.1:11434"
    model_name: str = "gemma4:e4b"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    request_timeout_seconds: float = 120.0
    enable_thinking: bool = True
    system_prompt: str = (
        "You are Gemma, a helpful, accurate, and concise AI assistant running locally. "
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
