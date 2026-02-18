from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    run_id: str
    agent_name: str
    node_name: str
    input_summary: dict = Field(default_factory=dict)
    output_summary: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0


class DecisionEvent(BaseModel):
    run_id: str
    node_name: str
    reasoning: str = ""
    chosen_action: str = ""
    alternatives: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
