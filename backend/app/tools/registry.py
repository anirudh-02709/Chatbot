import logging
import time
from typing import Any, Optional

from app.models.tool import ToolResult
from app.tools.base import (
    BaseTool,
    DuplicateToolError,
    ToolNotFoundError,
    ToolInputValidationError,
    ToolExecutionError,
)

logger = logging.getLogger("chatbot.tools.registry")


class ToolRegistry:
    """
    Central registry and dispatcher for extensible tool capabilities.

    Responsibilities:
    - Registering tools and preventing duplicate registrations.
    - Looking up and listing registered tools and schemas.
    - Safely dispatching asynchronous execution with input validation,
      latency timing, and structured error handling.
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool, overwrite: bool = False) -> None:
        """
        Registers a tool in the registry.

        Args:
            tool: A BaseTool instance.
            overwrite: If True, allows replacing an existing registration.

        Raises:
            TypeError: If tool is not an instance of BaseTool.
            ValueError: If tool name or description is missing.
            DuplicateToolError: If tool name already exists and overwrite is False.
        """
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Expected BaseTool instance, got {type(tool).__name__}.")

        name = tool.name.strip() if getattr(tool, "name", None) else ""
        if not name:
            raise ValueError("Tool must have a non-empty 'name'.")

        if not getattr(tool, "description", None) or not tool.description.strip():
            raise ValueError(f"Tool '{name}' must have a non-empty 'description'.")

        if name in self._tools and not overwrite:
            raise DuplicateToolError(
                f"Tool with name '{name}' is already registered in ToolRegistry."
            )

        self._tools[name] = tool
        logger.info(f"Registered tool: '{name}'")

    def unregister(self, name: str) -> bool:
        """
        Unregisters a tool by name.

        Returns:
            True if the tool was found and removed, False otherwise.
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: '{name}'")
            return True
        return False

    def get(self, name: str) -> Optional[BaseTool]:
        """Returns the tool with the given name, or None if not found."""
        return self._tools.get(name)

    def get_or_raise(self, name: str) -> BaseTool:
        """
        Returns the tool with the given name, or raises ToolNotFoundError.
        """
        tool = self.get(name)
        if tool is None:
            raise ToolNotFoundError(f"Tool '{name}' is not registered in ToolRegistry.")
        return tool

    def has(self, name: str) -> bool:
        """Checks if a tool name is currently registered."""
        return name in self._tools

    def list_tools(self) -> list[BaseTool]:
        """Returns an ordered list of all registered tools."""
        return list(self._tools.values())

    def list_tool_names(self) -> list[str]:
        """Returns a list of all registered tool names."""
        return list(self._tools.keys())

    def get_definitions(self) -> list[dict[str, Any]]:
        """
        Returns OpenAI/Ollama function-calling schemas for all registered tools.
        """
        return [t.to_dict() for t in self._tools.values()]

    def clear(self) -> None:
        """Clears all registered tools (primarily used for test isolation)."""
        self._tools.clear()

    async def execute(
        self,
        name: str,
        arguments: Optional[dict[str, Any]] = None,
        raise_on_error: bool = False,
    ) -> ToolResult:
        """
        Validates arguments and asynchronously executes the requested tool.

        Args:
            name: The registered tool name.
            arguments: Dict of input arguments passed to the tool.
            raise_on_error: If True, raises exceptions rather than returning
                            a failed ToolResult.

        Returns:
            ToolResult containing structured output, latency, and status.
        """
        t0 = time.perf_counter()

        # 1. Lookup tool
        tool = self.get(name)
        if tool is None:
            err_msg = f"Tool '{name}' is not registered in ToolRegistry."
            if raise_on_error:
                raise ToolNotFoundError(err_msg)
            return ToolResult.fail(
                tool_name=name,
                error=err_msg,
                error_type="ToolNotFoundError",
                execution_time_ms=round((time.perf_counter() - t0) * 1000, 2),
            )

        # 2. Input validation
        try:
            validated_args = tool.validate_input(arguments)
        except ToolInputValidationError as e:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.warning(f"Input validation error executing tool '{name}': {e}")
            if raise_on_error:
                raise
            return ToolResult.fail(
                tool_name=name,
                error=str(e),
                error_type="ToolInputValidationError",
                execution_time_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.error(f"Unexpected validation error for tool '{name}': {e}")
            if raise_on_error:
                raise ToolInputValidationError(str(e)) from e
            return ToolResult.fail(
                tool_name=name,
                error=f"Input validation failed: {e}",
                error_type="ToolInputValidationError",
                execution_time_ms=elapsed_ms,
            )

        # 3. Asynchronous execution
        try:
            result = await tool.execute(**validated_args)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

            if not isinstance(result, ToolResult):
                logger.warning(
                    f"Tool '{name}' returned non-ToolResult type ({type(result).__name__}). Normalizing."
                )
                result = ToolResult.ok(
                    tool_name=name,
                    data=result,
                    execution_time_ms=elapsed_ms,
                )
            elif result.execution_time_ms is None:
                result.execution_time_ms = elapsed_ms

            return result

        except Exception as e:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.exception(f"Execution error in tool '{name}': {e}")
            if raise_on_error:
                raise ToolExecutionError(f"Execution of tool '{name}' failed: {e}") from e
            return ToolResult.fail(
                tool_name=name,
                error=str(e),
                error_type="ToolExecutionError",
                execution_time_ms=elapsed_ms,
            )


# Global singleton tool registry instance
tool_registry = ToolRegistry()
