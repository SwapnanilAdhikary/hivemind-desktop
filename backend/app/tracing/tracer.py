from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from sqlalchemy import select

from app.db.database import async_session
from app.db.models import Trace, Decision
from app.tracing.models import TraceEvent, DecisionEvent
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)


def new_run_id() -> str:
    return uuid.uuid4().hex[:16]


def _truncate(obj: Any, max_len: int = 1000) -> Any:
    """Truncate strings in dicts/lists for storage."""
    if isinstance(obj, str):
        return obj[:max_len] + ("..." if len(obj) > max_len else "")
    if isinstance(obj, dict):
        return {k: _truncate(v, max_len) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_truncate(v, max_len) for v in obj[:20]]
    return obj


async def record_trace(event: TraceEvent) -> int:
    """Persist a trace event to the database and broadcast to connected clients."""
    async with async_session() as session:
        row = Trace(
            run_id=event.run_id,
            agent_name=event.agent_name,
            node_name=event.node_name,
            input_state=_truncate(event.input_summary),
            output_state=_truncate(event.output_summary),
            timestamp=event.timestamp,
            duration_ms=event.duration_ms,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)

    await ws_manager.broadcast("trace_update", {
        "id": row.id,
        "run_id": event.run_id,
        "agent_name": event.agent_name,
        "node_name": event.node_name,
        "input_state": _truncate(event.input_summary),
        "output_state": _truncate(event.output_summary),
        "timestamp": event.timestamp.isoformat(),
        "duration_ms": event.duration_ms,
    })
    return row.id


async def record_decision(event: DecisionEvent, trace_id: int) -> int:
    async with async_session() as session:
        row = Decision(
            trace_id=trace_id,
            node_name=event.node_name,
            reasoning=event.reasoning,
            chosen_action=event.chosen_action,
            alternatives=event.alternatives,
            timestamp=event.timestamp,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)

    await ws_manager.broadcast("agent_decision", {
        "id": row.id,
        "trace_id": trace_id,
        "node_name": event.node_name,
        "reasoning": event.reasoning,
        "chosen_action": event.chosen_action,
        "alternatives": event.alternatives,
        "timestamp": event.timestamp.isoformat(),
    })
    return row.id


class TracingContext:
    """Context manager that records full LLM input/output for a LangGraph node."""

    def __init__(self, run_id: str, agent_name: str, node_name: str) -> None:
        self.run_id = run_id
        self.agent_name = agent_name
        self.node_name = node_name
        self._start: float = 0
        self.trace_id: int | None = None
        self._input: dict[str, Any] = {}
        self._output: dict[str, Any] = {}

    async def __aenter__(self) -> "TracingContext":
        self._start = time.perf_counter()
        return self

    def set_input(self, **kwargs: Any) -> None:
        """Record what was sent to the LLM."""
        self._input.update(kwargs)

    def set_output(self, **kwargs: Any) -> None:
        """Record what the LLM returned."""
        self._output.update(kwargs)

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        duration = (time.perf_counter() - self._start) * 1000
        if exc_type:
            self._output["error"] = str(exc_val)
        event = TraceEvent(
            run_id=self.run_id,
            agent_name=self.agent_name,
            node_name=self.node_name,
            input_summary=self._input,
            output_summary=self._output,
            duration_ms=duration,
        )
        self.trace_id = await record_trace(event)

    async def record_decision(
        self, reasoning: str, chosen: str, alternatives: list[str] | None = None
    ) -> None:
        if self.trace_id is None:
            return
        event = DecisionEvent(
            run_id=self.run_id,
            node_name=self.node_name,
            reasoning=reasoning,
            chosen_action=chosen,
            alternatives=alternatives or [],
        )
        await record_decision(event, self.trace_id)
