import logging
from typing import Optional
import httpx

from app.config import Settings, get_settings
from app.services.embeddings.base import BaseEmbeddingProvider, EmbeddingError

logger = logging.getLogger("chatbot.embeddings.ollama")


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Local embedding provider utilizing Ollama's /api/embed endpoint."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.ollama_base_url.rstrip("/")
        self.model = self.settings.embedding_model
        self.expected_dim = self.settings.embedding_dimensions
        self.batch_size = self.settings.embedding_batch_size
        self.timeout = self.settings.embedding_timeout_seconds

    async def get_dimensions(self) -> int:
        return self.expected_dim

    async def is_healthy(self) -> bool:
        """Check if Ollama is reachable and the embedding model exists."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code != 200:
                    return False
                data = res.json()
                models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
                model_base = self.model.split(":")[0]
                return model_base in models or self.model in [m.get("name", "") for m in data.get("models", [])]
        except Exception:
            return False

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for a single text."""
        if not text.strip():
            # Return zero vector if empty string
            return [0.0] * self.expected_dim

        results = await self.embed_batch([text])
        if not results:
            raise EmbeddingError("No embedding vector returned.")
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a list of texts in configurable batch slices."""
        if not texts:
            return []

        all_vectors: list[list[float]] = []

        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]
            
            # Replace empty strings with a single space so Ollama doesn't reject them
            sanitized_texts = [t if t.strip() else " " for t in batch_texts]

            payload = {
                "model": self.model,
                "input": sanitized_texts,
            }

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/api/embed",
                        json=payload,
                    )
            except httpx.ConnectError as e:
                logger.error(f"Cannot connect to Ollama at {self.base_url}: {e}")
                raise EmbeddingError(
                    f"Unable to connect to local Ollama service at {self.base_url}."
                )
            except httpx.TimeoutException:
                logger.error(f"Embedding request timed out after {self.timeout}s")
                raise EmbeddingError(
                    f"Embedding request to Ollama timed out after {self.timeout}s."
                )
            except Exception as e:
                logger.error(f"Unexpected error communicating with Ollama: {e}")
                raise EmbeddingError(f"Failed to communicate with Ollama: {e}")

            if response.status_code == 404 or "not found" in response.text.lower():
                raise EmbeddingError(
                    f"Embedding model '{self.model}' not found in Ollama. Please run: ollama pull {self.model}"
                )

            if response.status_code != 200:
                raise EmbeddingError(
                    f"Ollama returned error status {response.status_code}: {response.text}"
                )

            try:
                data = response.json()
                embeddings = data.get("embeddings", [])
            except Exception as e:
                raise EmbeddingError(f"Malformed JSON response from Ollama: {e}")

            if len(embeddings) != len(batch_texts):
                raise EmbeddingError(
                    f"Expected {len(batch_texts)} embedding vectors, but received {len(embeddings)}."
                )

            # Validate dimensions and numeric contents
            for vec_idx, vec in enumerate(embeddings):
                if not isinstance(vec, list) or len(vec) != self.expected_dim:
                    actual_len = len(vec) if isinstance(vec, list) else type(vec).__name__
                    raise EmbeddingError(
                        f"Dimension mismatch for item {i + vec_idx}: expected {self.expected_dim}, got {actual_len}."
                    )
                all_vectors.append([float(x) for x in vec])

        return all_vectors
