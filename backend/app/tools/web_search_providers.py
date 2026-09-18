"""
Web Search Providers for Goal 10.5.

Provides a pluggable abstraction layer for external web search engines:
- BaseWebSearchProvider: Abstract base interface
- TavilySearchProvider: LLM-optimized search engine provider
- BraveSearchProvider: Brave Search API provider
- create_search_provider: Factory returning the configured provider
"""

import logging
import urllib.parse
from abc import ABC, abstractmethod
from typing import Any, Optional
import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings, get_settings

logger = logging.getLogger("chatbot.tools.web_search")


# ─────────────────────────────────────────────────────────────────────────────
# Search Result Data Model
# ─────────────────────────────────────────────────────────────────────────────

class WebSearchResultItem(BaseModel):
    """Normalized individual search result item from an external web search provider."""

    title: str = Field(..., description="Title of the web page or document.")
    url: str = Field(..., description="Canonical URL of the search result.")
    snippet: str = Field(..., description="Extracted text excerpt or snippet from the page.")
    source: str = Field(..., description="Hostname or domain name of the result source.")
    rank: int = Field(..., ge=1, description="1-indexed rank order in search results.")
    raw_score: Optional[float] = Field(default=None, description="Relevance score if provided by provider.")

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Provider Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class WebSearchProviderError(Exception):
    """Base exception for web search provider errors."""
    pass


class WebSearchNotConfiguredError(WebSearchProviderError):
    """Raised when the requested web search provider is missing required API credentials."""
    pass


class WebSearchTimeoutError(WebSearchProviderError):
    """Raised when the web search API call exceeds configured timeout."""
    pass


class WebSearchHttpError(WebSearchProviderError):
    """Raised when the web search API returns an HTTP error status code."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class WebSearchNetworkError(WebSearchProviderError):
    """Raised when network connection to the search provider fails."""
    pass


class WebSearchMalformedResponseError(WebSearchProviderError):
    """Raised when the search provider returns an invalid or unparseable response."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Provider Abstraction Interface
# ─────────────────────────────────────────────────────────────────────────────

class BaseWebSearchProvider(ABC):
    """
    Abstract base class for web search providers.

    Decouples WebSearchTool from specific search engines (Tavily, Brave, etc.),
    allowing providers to be swapped or mocked without touching tool code.
    """

    name: str

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the provider has all required credentials and config."""
        pass

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResultItem]:
        """
        Executes a search query and returns normalized search result items.

        Args:
            query: Sanitized search query string.
            max_results: Maximum number of results to retrieve.

        Returns:
            List of normalized WebSearchResultItem objects.

        Raises:
            WebSearchNotConfiguredError: If credentials are not configured.
            WebSearchTimeoutError: If the request times out.
            WebSearchHttpError: If provider returns 4xx/5xx HTTP status.
            WebSearchNetworkError: On connection/network failures.
            WebSearchMalformedResponseError: On unparseable response data.
        """
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Concrete Provider: Tavily
# ─────────────────────────────────────────────────────────────────────────────

class TavilySearchProvider(BaseWebSearchProvider):
    """
    Web search provider using the Tavily Search API.
    API docs: https://docs.tavily.com/
    """

    name = "tavily"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ):
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.base_url = (base_url or "https://api.tavily.com").rstrip("/")
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResultItem]:
        if not self.is_configured():
            raise WebSearchNotConfiguredError(
                f"Web search provider '{self.name}' is not configured. "
                "Please set WEB_SEARCH_API_KEY in the environment or .env file."
            )

        payload = {
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        endpoint = f"{self.base_url}/search"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(endpoint, json=payload, headers=headers)

            if response.status_code != 200:
                # Sanitize error detail to prevent any accidental credential leakage
                error_snippet = response.text[:200].replace(self.api_key or "", "[REDACTED]")
                raise WebSearchHttpError(
                    f"Tavily API returned HTTP {response.status_code}: {error_snippet}",
                    status_code=response.status_code,
                )

            data = response.json()
        except httpx.TimeoutException as exc:
            logger.warning(f"Tavily search timed out for query '{query[:50]}': {exc}")
            raise WebSearchTimeoutError(
                f"Web search request to Tavily timed out after {self.timeout_seconds} seconds."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise WebSearchHttpError(
                f"Tavily HTTP error: {exc.response.status_code}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            logger.warning(f"Network error communicating with Tavily: {exc}")
            raise WebSearchNetworkError(f"Network error connecting to Tavily: {exc}") from exc
        except (ValueError, KeyError) as exc:
            logger.warning(f"Malformed JSON response from Tavily: {exc}")
            raise WebSearchMalformedResponseError(
                f"Malformed response received from Tavily API: {exc}"
            ) from exc

        if not isinstance(data, dict) or "results" not in data or not isinstance(data["results"], list):
            raise WebSearchMalformedResponseError(
                "Tavily response missing valid 'results' list."
            )

        items: list[WebSearchResultItem] = []
        for idx, r in enumerate(data["results"][:max_results]):
            if not isinstance(r, dict):
                continue
            raw_url = str(r.get("url") or "").strip()
            title = str(r.get("title") or "").strip() or "Untitled Result"
            snippet = str(r.get("content") or r.get("snippet") or "").strip()
            score = float(r.get("score")) if r.get("score") is not None else None

            # Extract clean domain name for provenance
            parsed = urllib.parse.urlparse(raw_url)
            source = parsed.netloc or "web"

            items.append(
                WebSearchResultItem(
                    title=title,
                    url=raw_url,
                    snippet=snippet,
                    source=source,
                    rank=idx + 1,
                    raw_score=score,
                )
            )

        return items


# ─────────────────────────────────────────────────────────────────────────────
# Concrete Provider: Brave Search
# ─────────────────────────────────────────────────────────────────────────────

class BraveSearchProvider(BaseWebSearchProvider):
    """
    Web search provider using the Brave Search REST API.
    API docs: https://brave.com/search/api/
    """

    name = "brave"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ):
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.base_url = (base_url or "https://api.search.brave.com").rstrip("/")
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResultItem]:
        if not self.is_configured():
            raise WebSearchNotConfiguredError(
                f"Web search provider '{self.name}' is not configured. "
                "Please set WEB_SEARCH_API_KEY in the environment or .env file."
            )

        params = {
            "q": query,
            "count": min(max_results, 20),
        }
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }

        endpoint = f"{self.base_url}/res/v1/web/search"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(endpoint, params=params, headers=headers)

            if response.status_code != 200:
                error_snippet = response.text[:200].replace(self.api_key or "", "[REDACTED]")
                raise WebSearchHttpError(
                    f"Brave Search API returned HTTP {response.status_code}: {error_snippet}",
                    status_code=response.status_code,
                )

            data = response.json()
        except httpx.TimeoutException as exc:
            logger.warning(f"Brave Search timed out for query '{query[:50]}': {exc}")
            raise WebSearchTimeoutError(
                f"Web search request to Brave timed out after {self.timeout_seconds} seconds."
            ) from exc
        except httpx.RequestError as exc:
            logger.warning(f"Network error communicating with Brave Search: {exc}")
            raise WebSearchNetworkError(f"Network error connecting to Brave Search: {exc}") from exc
        except (ValueError, KeyError) as exc:
            logger.warning(f"Malformed JSON response from Brave Search: {exc}")
            raise WebSearchMalformedResponseError(
                f"Malformed response received from Brave Search API: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise WebSearchMalformedResponseError("Brave Search response must be a JSON object.")

        web_data = data.get("web", {})
        results_list = web_data.get("results", []) if isinstance(web_data, dict) else []

        items: list[WebSearchResultItem] = []
        for idx, r in enumerate(results_list[:max_results]):
            if not isinstance(r, dict):
                continue
            raw_url = str(r.get("url") or "").strip()
            title = str(r.get("title") or "").strip() or "Untitled Result"
            snippet = str(r.get("description") or "").strip()

            parsed = urllib.parse.urlparse(raw_url)
            source = parsed.netloc or "web"

            items.append(
                WebSearchResultItem(
                    title=title,
                    url=raw_url,
                    snippet=snippet,
                    source=source,
                    rank=idx + 1,
                )
            )

        return items


# ─────────────────────────────────────────────────────────────────────────────
# Factory Function
# ─────────────────────────────────────────────────────────────────────────────

def create_search_provider(settings: Optional[Settings] = None) -> BaseWebSearchProvider:
    """
    Factory creating the configured search provider based on application settings.
    """
    s = settings or get_settings()
    provider_name = (s.web_search_provider or "tavily").lower().strip()

    if provider_name == "brave":
        return BraveSearchProvider(
            api_key=s.web_search_api_key,
            base_url=s.web_search_base_url,
            timeout_seconds=s.web_search_timeout_seconds,
        )

    # Default provider: Tavily
    return TavilySearchProvider(
        api_key=s.web_search_api_key,
        base_url=s.web_search_base_url,
        timeout_seconds=s.web_search_timeout_seconds,
    )
