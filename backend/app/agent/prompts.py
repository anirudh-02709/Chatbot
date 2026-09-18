"""
Prompt templates and formatting for Goal 10.7: Agent Orchestration Foundation.

Constructs structured model-to-tool decision prompts for Local Gemma and OmniRoute.
"""

import json
from typing import Any, Optional

from app.agent.models import AgentDecision, AgentDecisionType
from app.models.chat import ChatMessage
from app.models.tool import ToolExecutionRecord


AGENT_SYSTEM_PROMPT_TEMPLATE = """You are an intelligent autonomous AI Assistant equipped with specialized tools.
Your goal is to assist the user by either answering directly or using the most appropriate tool.

### AVAILABLE TOOLS:
{tools_section}

### DECISION PROTOCOL:
You must analyze the user request and decide whether to answer directly or invoke a tool.
You must respond with ONLY a single valid JSON object adhering strictly to one of the following two schemas:

Option 1 - If you can answer directly without any tools:
```json
{{
  "type": "final_answer",
  "answer": "<your comprehensive and direct answer>"
}}
```

Option 2 - If you need to invoke a tool to calculate, retrieve documents, search the web, or analyze data:
```json
{{
  "type": "tool_call",
  "tool_name": "<exact name of registered tool>",
  "arguments": {{ <parameters matching the tool schema> }}
}}
```

### CRITICAL RULES:
1. Output ONLY the JSON object. Do not provide conversational preamble or markdown explanation outside the JSON.
2. Only select tools from the AVAILABLE TOOLS list above. Do NOT invent new tools.
3. Arguments MUST strictly match the parameter schema of the selected tool.
4. Do NOT execute code or attempt to reveal your internal hidden chain-of-thought.
"""


def build_agent_system_prompt(tool_definitions: list[dict[str, Any]]) -> str:
    """
    Constructs the system prompt instructing the model on available tools
    and the structured JSON decision protocol.

    Args:
        tool_definitions: List of tool definition dictionaries from ToolRegistry.get_definitions().

    Returns:
        Formatted system prompt string.
    """
    tools_entries = []
    for defn in tool_definitions:
        # Each defn is formatted as {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
        fn = defn.get("function", defn)
        name = fn.get("name", "unknown")
        desc = fn.get("description", "")
        params = fn.get("parameters", {})
        params_str = json.dumps(params, indent=2)

        tools_entries.append(
            f"- Tool: `{name}`\n"
            f"  Description: {desc}\n"
            f"  Parameters Schema:\n```json\n{params_str}\n```"
        )

    tools_section = "\n\n".join(tools_entries) if tools_entries else "No tools currently registered."
    return AGENT_SYSTEM_PROMPT_TEMPLATE.format(tools_section=tools_section)


def format_tool_observation(tool_name: str, record: ToolExecutionRecord) -> str:
    """
    Formats a tool execution record into a structured JSON observation message
    for subsequent LLM decision-making steps. Quarantines external/untrusted data
    within a structured JSON block.
    """
    if record.success:
        obs_payload = {
            "status": "success",
            "tool": tool_name,
            "result": record.data,
        }
    else:
        obs_payload = {
            "status": "error",
            "tool": tool_name,
            "error": record.error or "Unknown tool execution error",
            "error_type": record.error_type or "ToolExecutionError",
        }

    raw_json = json.dumps(obs_payload, indent=2, ensure_ascii=False)
    return (
        f"[Tool Observation: {tool_name}]\n"
        f"```json\n{raw_json}\n```\n\n"
        "Based on the tool observation above, decide your next step according to the decision protocol "
        '(either call another tool using "tool_call" or produce your final answer using "final_answer").'
    )


def build_agent_messages(
    user_request: str,
    history: Optional[list[tuple[AgentDecision, ToolExecutionRecord]]] = None,
) -> list[ChatMessage]:
    """
    Constructs the multi-turn ChatMessage list sent to the LLM.

    Message structure:
    1. User: Original user query
    2. For each step in history:
       - Assistant: JSON representation of tool_call decision
       - User: Structured observation from the tool execution
    """
    messages: list[ChatMessage] = [
        ChatMessage(role="user", content=user_request)
    ]

    if not history:
        return messages

    for decision, record in history:
        if decision.type == AgentDecisionType.TOOL_CALL or decision.type == "tool_call":
            tool_payload: dict[str, Any] = {
                "type": "tool_call",
                "tool_name": decision.tool_name,
                "arguments": decision.tool_arguments or {},
            }
            if decision.reasoning:
                tool_payload["reasoning"] = decision.reasoning

            messages.append(
                ChatMessage(
                    role="assistant",
                    content=json.dumps(tool_payload),
                )
            )
            obs_text = format_tool_observation(decision.tool_name or "tool", record)
            messages.append(
                ChatMessage(
                    role="user",
                    content=obs_text,
                )
            )

    return messages

