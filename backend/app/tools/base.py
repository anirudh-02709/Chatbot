from abc import ABC, abstractmethod
from typing import Any, Optional, Type
from pydantic import BaseModel, ValidationError

from app.models.tool import ToolResult, ToolDefinition


# ─────────────────────────────────────────────────────────────────────────────
# Tool Exception Hierarchy
# ─────────────────────────────────────────────────────────────────────────────

class ToolError(Exception):
    """Base exception for all tool-related errors."""
    pass


class DuplicateToolError(ToolError):
    """Raised when attempting to register a tool with a name that is already registered."""
    pass


class ToolNotFoundError(ToolError):
    """Raised when attempting to retrieve or execute an unregistered tool."""
    pass


class ToolInputValidationError(ToolError):
    """Raised when arguments provided to a tool fail schema or model validation."""
    pass


class ToolExecutionError(ToolError):
    """Raised when an error occurs during tool execution."""
    pass


class ToolExecutionPolicyError(ToolError):
    """Raised when an execution policy rule (e.g. limit, recursion, authorization) is violated."""
    pass


class ExecutionLimitExceededError(ToolExecutionPolicyError):
    """Raised when the maximum number of tool executions for a session/request is exceeded."""
    pass


class RecursiveExecutionError(ToolExecutionPolicyError):
    """Raised when a tool attempts to recursively invoke tools through the execution layer."""
    pass


class ToolTimeoutError(ToolExecutionError):
    """Raised when a tool execution exceeds the configured timeout."""
    pass



# ─────────────────────────────────────────────────────────────────────────────
# Base Tool Abstraction
# ─────────────────────────────────────────────────────────────────────────────

class BaseTool(ABC):
    """
    Abstract base class for all tools in the AI Assistant architecture.

    Subclasses must provide:
    - `name`: Unique identifier for the tool.
    - `description`: Clear description of functionality and usage for the LLM.
    - `parameters_schema`: JSON Schema specifying the expected input parameters.
    - `execute`: Asynchronous execution logic returning a structured ToolResult.

    Subclasses can optionally define `args_model` (a Pydantic BaseModel) to
    enable automatic, rigorous input validation and type coercion.
    """

    name: str
    description: str
    parameters_schema: dict[str, Any] = {"type": "object", "properties": {}}
    args_model: Optional[Type[BaseModel]] = None

    def validate_input(self, arguments: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Validates input arguments against `args_model` if defined,
        or against basic JSON Schema rules (such as required fields).

        Raises:
            ToolInputValidationError: If validation fails.
        """
        args = arguments if arguments is not None else {}
        if not isinstance(args, dict):
            raise ToolInputValidationError(
                f"Tool '{self.name}' expected arguments as a dict, got {type(args).__name__}."
            )

        # 1. Pydantic validation if args_model is configured
        if self.args_model is not None:
            try:
                validated_obj = self.args_model.model_validate(args)
                return validated_obj.model_dump()
            except ValidationError as ve:
                errors = []
                for err in ve.errors():
                    field_path = ".".join(str(loc) for loc in err.get("loc", []))
                    msg = err.get("msg", "Invalid value")
                    errors.append(f"{field_path}: {msg}" if field_path else msg)
                raise ToolInputValidationError(
                    f"Input validation failed for tool '{self.name}': {'; '.join(errors)}"
                ) from ve

        # 2. Schema-level validation for required properties
        required_fields = self.parameters_schema.get("required", [])
        missing = [f for f in required_fields if f not in args]
        if missing:
            raise ToolInputValidationError(
                f"Missing required parameter(s) for tool '{self.name}': {', '.join(missing)}"
            )

        # Basic type checking for declared properties
        properties = self.parameters_schema.get("properties", {})
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        for prop_name, prop_val in args.items():
            if prop_name in properties:
                expected_type_str = properties[prop_name].get("type")
                if expected_type_str in type_map:
                    expected_type = type_map[expected_type_str]
                    # Note: bool is a subclass of int in Python, so check bool explicitly
                    if expected_type_str in ("integer", "number") and isinstance(prop_val, bool):
                        raise ToolInputValidationError(
                            f"Parameter '{prop_name}' for tool '{self.name}' expected {expected_type_str}, got boolean."
                        )
                    if not isinstance(prop_val, expected_type):
                        raise ToolInputValidationError(
                            f"Parameter '{prop_name}' for tool '{self.name}' expected {expected_type_str}, got {type(prop_val).__name__}."
                        )

        return args

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Asynchronously executes the tool logic with the provided arguments.
        Must return a structured ToolResult.
        """
        pass

    def to_dict(self) -> dict[str, Any]:
        """
        Exports the tool definition in standard OpenAI/Ollama function format.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }

    def to_definition(self) -> ToolDefinition:
        """Exports the tool as a Pydantic ToolDefinition."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters_schema,
        )
