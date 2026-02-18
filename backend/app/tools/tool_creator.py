from __future__ import annotations

import json
import logging
import re
from typing import Any

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from app.llm.router import llm_router
from app.tools.registry import tool_registry
from app.tracing.tracer import TracingContext, new_run_id
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)


class ToolCreatorState(TypedDict, total=False):
    run_id: str
    task_description: str
    tool_name: str
    tool_description: str
    source_code: str
    parameters_schema: dict
    validation_result: str
    is_valid: bool
    error: str


TOOL_GENERATION_PROMPT = """You are a Python tool creator. Given a task description, create a Python function that can be registered as a reusable tool.

Task: {task_description}

Requirements:
1. Define a single Python function with a clear, descriptive name (snake_case)
2. Add a docstring explaining what it does
3. Use only standard library imports (os, json, re, datetime, urllib, etc.)
4. The function should be self-contained
5. Handle errors gracefully with try/except
6. Return a meaningful result

Respond with EXACTLY this JSON format:
{{
  "name": "function_name",
  "description": "What this tool does",
  "source_code": "def function_name(param1: str, param2: int = 0) -> str:\\n    ...",
  "parameters_schema": {{
    "type": "object",
    "properties": {{
      "param1": {{"type": "string", "description": "..."}},
      "param2": {{"type": "integer", "description": "...", "default": 0}}
    }},
    "required": ["param1"]
  }}
}}
"""

VALIDATION_PROMPT = """Review this Python function for safety and correctness.

Function name: {name}
Source code:
```python
{source_code}
```

Check for:
1. No file system writes to dangerous locations
2. No network calls to unknown servers
3. No exec/eval on user input
4. No infinite loops
5. Proper error handling
6. Function signature matches the name

Respond with EXACTLY: "SAFE" if the tool is safe, or "UNSAFE: <reason>" if not.
"""


async def analyze_task(state: ToolCreatorState) -> ToolCreatorState:
    """Use LLM to generate tool code from task description."""
    run_id = state.get("run_id", new_run_id())
    async with TracingContext(run_id, "tool_creator", "analyze_task"):
        llm = llm_router.get_llm()
        prompt = TOOL_GENERATION_PROMPT.format(task_description=state["task_description"])

        try:
            result = await llm.ainvoke([{"role": "user", "content": prompt}])
            content = result.content.strip()

            json_match = re.search(r'\{[\s\S]*\}', content)
            if not json_match:
                state["error"] = "LLM did not return valid JSON"
                state["is_valid"] = False
                return state

            parsed = json.loads(json_match.group())
            state["tool_name"] = parsed["name"]
            state["tool_description"] = parsed["description"]
            state["source_code"] = parsed["source_code"]
            state["parameters_schema"] = parsed.get("parameters_schema", {})
        except Exception as e:
            state["error"] = f"Tool generation failed: {e}"
            state["is_valid"] = False

    return state


async def validate_tool(state: ToolCreatorState) -> ToolCreatorState:
    """Validate the generated tool for safety and correctness."""
    run_id = state.get("run_id", new_run_id())
    async with TracingContext(run_id, "tool_creator", "validate_tool") as ctx:
        if state.get("error"):
            state["is_valid"] = False
            return state

        source = state.get("source_code", "")
        name = state.get("tool_name", "")

        # Static checks
        dangerous_patterns = ["os.system", "subprocess", "shutil.rmtree", "__import__", "eval(", "exec("]
        for pattern in dangerous_patterns:
            if pattern in source:
                state["is_valid"] = False
                state["validation_result"] = f"Dangerous pattern found: {pattern}"
                await ctx.record_decision(
                    reasoning=f"Static analysis found dangerous pattern: {pattern}",
                    chosen="reject",
                    alternatives=["accept"],
                )
                return state

        # Syntax check
        try:
            compile(source, "<tool>", "exec")
        except SyntaxError as e:
            state["is_valid"] = False
            state["validation_result"] = f"Syntax error: {e}"
            return state

        # Verify function exists
        namespace: dict[str, Any] = {}
        try:
            exec(source, namespace)
            if name not in namespace or not callable(namespace[name]):
                state["is_valid"] = False
                state["validation_result"] = f"Source does not define callable '{name}'"
                return state
        except Exception as e:
            state["is_valid"] = False
            state["validation_result"] = f"Execution error: {e}"
            return state

        # LLM safety review
        try:
            llm = llm_router.get_llm()
            prompt = VALIDATION_PROMPT.format(name=name, source_code=source)
            result = await llm.ainvoke([{"role": "user", "content": prompt}])
            review = result.content.strip()

            if review.startswith("SAFE"):
                state["is_valid"] = True
                state["validation_result"] = "Passed all checks"
                await ctx.record_decision(
                    reasoning="Tool passed static analysis and LLM safety review",
                    chosen="accept",
                    alternatives=["reject"],
                )
            else:
                state["is_valid"] = False
                state["validation_result"] = review
                await ctx.record_decision(
                    reasoning=f"LLM flagged tool as unsafe: {review}",
                    chosen="reject",
                    alternatives=["accept"],
                )
        except Exception as e:
            logger.warning("LLM validation failed, using static analysis only: %s", e)
            state["is_valid"] = True
            state["validation_result"] = "Passed static checks (LLM review unavailable)"

    return state


async def register_tool_node(state: ToolCreatorState) -> ToolCreatorState:
    """Register the validated tool in the registry."""
    run_id = state.get("run_id", new_run_id())
    async with TracingContext(run_id, "tool_creator", "register_tool"):
        if not state.get("is_valid"):
            return state

        try:
            tool_id = await tool_registry.register(
                name=state["tool_name"],
                description=state["tool_description"],
                source_code=state["source_code"],
                parameters_schema=state.get("parameters_schema"),
            )
            logger.info("Tool registered: %s (id=%d)", state["tool_name"], tool_id)
        except Exception as e:
            state["error"] = f"Registration failed: {e}"
            state["is_valid"] = False

    return state


def should_register(state: ToolCreatorState) -> str:
    if state.get("is_valid"):
        return "register_tool"
    return END


def build_tool_creator():
    graph = StateGraph(ToolCreatorState)

    graph.add_node("analyze_task", analyze_task)
    graph.add_node("validate_tool", validate_tool)
    graph.add_node("register_tool", register_tool_node)

    graph.set_entry_point("analyze_task")
    graph.add_edge("analyze_task", "validate_tool")
    graph.add_conditional_edges("validate_tool", should_register, {
        "register_tool": "register_tool",
        END: END,
    })
    graph.add_edge("register_tool", END)

    return graph.compile()


tool_creator = build_tool_creator()


async def create_tool(task_description: str) -> dict:
    """High-level API to create a tool from a natural language description."""
    state: ToolCreatorState = {
        "run_id": new_run_id(),
        "task_description": task_description,
    }
    result = await tool_creator.ainvoke(state)
    return {
        "success": result.get("is_valid", False),
        "tool_name": result.get("tool_name", ""),
        "description": result.get("tool_description", ""),
        "validation_result": result.get("validation_result", ""),
        "error": result.get("error", ""),
    }
