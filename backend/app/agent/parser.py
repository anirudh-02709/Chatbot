"""
Decision parser for Goal 10.7: Agent Orchestration Foundation.

Safely parses and validates structured JSON decisions from LLM generation without
relying on arbitrary code execution, unsafe eval, or guessing model intentions.
"""

import json
import re
from typing import Any, Optional

from app.agent.models import AgentDecision, AgentDecisionType


class DecisionParsingError(Exception):
    """Raised when an LLM decision output cannot be parsed into a valid AgentDecision."""
    pass


def extract_json_payload(raw_text: str) -> str:
    """
    Extracts the JSON payload from raw LLM output, handling markdown code fences
    or surrounding conversational noise safely.

    Raises:
        DecisionParsingError: If no JSON object boundary can be identified.
    """
    clean_text = raw_text.strip() if raw_text else ""
    if not clean_text:
        raise DecisionParsingError("Model returned empty or whitespace response.")

    # 1. Match fenced code block ```json ... ``` or ``` ... ```
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(fence_pattern, clean_text, re.IGNORECASE)
    if match:
        content = match.group(1).strip()
        if content.startswith("{") and content.endswith("}"):
            return content

    # 2. Match outermost { ... }
    first_brace = clean_text.find("{")
    last_brace = clean_text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return clean_text[first_brace : last_brace + 1].strip()

    raise DecisionParsingError(
        f"Could not locate valid JSON object in model response: {clean_text[:100]}..."
    )


def parse_agent_decision(
    raw_text: str,
    valid_tools: Optional[set[str]] = None,
) -> AgentDecision:
    """
    Parses and validates a model-generated decision string into an AgentDecision.

    Strict validation rules:
    - Must be a valid JSON object.
    - Must contain 'type' equal to 'final_answer' or 'tool_call'.
    - If 'final_answer', 'answer' must be a non-empty string.
    - If 'tool_call', 'tool_name' must be a non-empty string and match a valid tool.
    - 'arguments' must be a valid dictionary.
    - Never executes arbitrary text or code.

    Raises:
        DecisionParsingError: If parsing or schema validation fails.
    """
    json_str = extract_json_payload(raw_text)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise DecisionParsingError(f"Malformed JSON in agent decision: {e}") from e

    if not isinstance(data, dict):
        raise DecisionParsingError(
            f"Decision payload must be a JSON object, got {type(data).__name__}."
        )

    if "type" not in data or not isinstance(data["type"], str):
        raise DecisionParsingError("Decision missing required 'type' field.")

    dec_type = data["type"].strip().lower()

    if dec_type == AgentDecisionType.FINAL_ANSWER.value:
        answer = data.get("answer")
        if answer is None or not isinstance(answer, str) or not answer.strip():
            raise DecisionParsingError(
                "Final answer decision must provide a non-empty 'answer' string."
            )
        return AgentDecision(
            type=AgentDecisionType.FINAL_ANSWER,
            answer=answer.strip(),
            reasoning=data.get("reasoning"),
            confidence=float(data["confidence"]) if "confidence" in data and data["confidence"] is not None else None,
        )

    elif dec_type == AgentDecisionType.TOOL_CALL.value:
        tool_name = data.get("tool_name")
        if not tool_name or not isinstance(tool_name, str) or not tool_name.strip():
            raise DecisionParsingError(
                "Tool call decision must provide a non-empty 'tool_name' string."
            )

        clean_tool_name = tool_name.strip()
        if valid_tools is not None and clean_tool_name not in valid_tools:
            raise DecisionParsingError(
                f"Requested tool '{clean_tool_name}' is not registered. Available tools: {sorted(valid_tools)}."
            )

        args = data.get("arguments")
        if args is None:
            args = {}
        elif not isinstance(args, dict):
            raise DecisionParsingError(
                f"Tool arguments for '{clean_tool_name}' must be a dictionary/object, got {type(args).__name__}."
            )

        return AgentDecision(
            type=AgentDecisionType.TOOL_CALL,
            tool_name=clean_tool_name,
            tool_arguments=args,
            reasoning=data.get("reasoning"),
            confidence=float(data["confidence"]) if "confidence" in data and data["confidence"] is not None else None,
        )

    else:
        raise DecisionParsingError(
            f"Unknown decision type '{dec_type}'. Expected 'final_answer' or 'tool_call'."
        )
