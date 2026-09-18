"""
Web Search Tool for Goal 10.5.

Exposes a standardized WebSearchTool implementing BaseTool.
Connects to external search engines via BaseWebSearchProvider without
performing LLM synthesis or coupling to future Agent loops.
"""

import logging
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.models.tool import ToolResult
from app.tools.base import BaseTool
from app.tools.web_search_providers import (
    BaseWebSearchProvider,
    WebSearchResultItem,
    WebSearchNotConfiguredError,
    WebSearchTimeoutError,
    WebSearchHttpError,
    WebSearchNetworkError,
    WebSearchMalformedResponseError,
    create_search_provider,
)

logger = logging.getLogger("chatbot.tools.web_search")


# ─────────────────────────────────────────────────────────────────────────────
# Input Schema
# ─────────────────────────────────────────────────────────────────────────────

class WebSearchInput(BaseModel):
    """Input parameters for the WebSearchTool."""

    query: str = Field(
        ...,
        min_length=1,
        description="The search query or keywords to search the public web for.",
    )
    max_results: Optional[int] = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of search results to return (1 to 20, default: 5).",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Web Search Tool Implementation
# ─────────────────────────────────────────────────────────────────────────────

class WebSearchTool(BaseTool):
    """
    Tool allowing the AI Assistant to search the public web for external information.

    Connects to external search APIs (e.g. Tavily, Brave) through a pluggable
    BaseWebSearchProvider. Returns raw ranked search results and snippets
    without synthesizing answers or modifying chat state.
    """

    name = "web_search"
    description = (
        "Searches the public web for current information, facts, and documents relevant to a search query. "
        "Returns ranked search results with URLs, titles, and content snippets."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query or keywords to search the public web for.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of search results to return (1 to 20, default: 5).",
            },
        },
        "required": ["query"],
    }
    args_model = WebSearchInput

    def __init__(self, provider: Optional[BaseWebSearchProvider] = None):
        """
        Initializes the WebSearchTool.

        Args:
            provider: Optional search provider instance. If None, the provider
                      is lazily instantiated from application settings.
        """
        self._provider = provider

    @property
    def provider(self) -> BaseWebSearchProvider:
        """Resolves the active search provider."""
        if self._provider is None:
            self._provider = create_search_provider()
        return self._provider

    async def execute(
        self,
        query: str,
        max_results: Optional[int] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """
        Executes a web search query through the active search provider.

        Args:
            query: The search keywords or phrase.
            max_results: Max items to return (1 to 20, default: 5).

        Returns:
            Structured ToolResult with ranked search results or structured failure.
        """
        clean_query = query.strip() if query else ""
        if not clean_query:
            return ToolResult.fail(
                tool_name=self.name,
                error="Search query cannot be empty or whitespace.",
                error_type="ToolInputValidationError",
            )

        effective_max_results = max_results if max_results is not None else 5
        if effective_max_results < 1 or effective_max_results > 20:
            return ToolResult.fail(
                tool_name=self.name,
                error=f"max_results must be between 1 and 20 (got {effective_max_results}).",
                error_type="ToolInputValidationError",
            )

        active_provider = self.provider

        # Check provider configuration before attempting network calls
        if not active_provider.is_configured():
            logger.info(f"WebSearchTool called but provider '{active_provider.name}' is not configured.")
            return ToolResult.fail(
                tool_name=self.name,
                error=(
                    f"Web search provider '{active_provider.name}' is not configured. "
                    "Please set WEB_SEARCH_API_KEY in the environment or .env file."
                ),
                error_type="WebSearchNotConfiguredError",
                metadata={"provider": active_provider.name, "query": clean_query},
            )

        # Execute search
        try:
            items: list[WebSearchResultItem] = await active_provider.search(
                query=clean_query,
                max_results=effective_max_results,
            )
        except WebSearchNotConfiguredError as exc:
            return ToolResult.fail(
                tool_name=self.name,
                error=str(exc),
                error_type="WebSearchNotConfiguredError",
                metadata={"provider": active_provider.name, "query": clean_query},
            )
        except WebSearchTimeoutError as exc:
            logger.warning(f"WebSearchTool timeout: {exc}")
            return ToolResult.fail(
                tool_name=self.name,
                error=str(exc),
                error_type="WebSearchTimeoutError",
                metadata={"provider": active_provider.name, "query": clean_query},
            )
        except WebSearchHttpError as exc:
            logger.warning(f"WebSearchTool HTTP error: {exc}")
            return ToolResult.fail(
                tool_name=self.name,
                error=str(exc),
                error_type="WebSearchHttpError",
                metadata={
                    "provider": active_provider.name,
                    "query": clean_query,
                    "status_code": exc.status_code,
                },
            )
        except WebSearchNetworkError as exc:
            logger.warning(f"WebSearchTool network error: {exc}")
            return ToolResult.fail(
                tool_name=self.name,
                error=str(exc),
                error_type="WebSearchNetworkError",
                metadata={"provider": active_provider.name, "query": clean_query},
            )
        except WebSearchMalformedResponseError as exc:
            logger.warning(f"WebSearchTool malformed response error: {exc}")
            return ToolResult.fail(
                tool_name=self.name,
                error=str(exc),
                error_type="WebSearchMalformedResponseError",
                metadata={"provider": active_provider.name, "query": clean_query},
            )
        except Exception as exc:
            logger.error(f"Unexpected error in WebSearchTool: {exc}")
            return ToolResult.fail(
                tool_name=self.name,
                error=f"Web search failed unexpectedly: {exc}",
                error_type=type(exc).__name__,
                metadata={"provider": active_provider.name, "query": clean_query},
            )

        # Structure results strictly as passive data
        results_data = [
            {
                "title": item.title,
                "url": item.url,
                "snippet": item.snippet,
                "source": item.source,
                "rank": item.rank,
            }
            for item in items
        ]

        logger.info(
            f"WebSearchTool retrieved {len(results_data)} results for '{clean_query[:50]}' "
            f"via provider '{active_provider.name}'"
        )

        return ToolResult.ok(
            tool_name=self.name,
            data={
                "query": clean_query,
                "result_count": len(results_data),
                "results": results_data,
            },
            metadata={
                "query": clean_query,
                "provider": active_provider.name,
                "max_results": effective_max_results,
                "result_count": len(results_data),
                "urls": [r["url"] for r in results_data if r["url"]],
            },
        )


# Global singleton instance
web_search_tool = WebSearchTool()
