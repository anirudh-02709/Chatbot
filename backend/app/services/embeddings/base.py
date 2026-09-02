from abc import ABC, abstractmethod


class EmbeddingError(Exception):
    """Raised when text embedding generation fails."""
    pass


class BaseEmbeddingProvider(ABC):
    """Abstract base interface for text embedding providers."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate a dense vector embedding for a single string."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate dense vector embeddings for a list of strings in batch."""
        pass

    @abstractmethod
    async def get_dimensions(self) -> int:
        """Return the vector dimensionality produced by this provider."""
        pass

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if the embedding provider service is reachable and operational."""
        pass
