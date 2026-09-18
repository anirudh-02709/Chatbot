"""
Prompt templates and formatting for Goal 10.7: Agent Orchestration Foundation.

Constructs structured model-to-tool decision prompts for Local Gemma and OmniRoute.
"""

import json
from typing import Any


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
