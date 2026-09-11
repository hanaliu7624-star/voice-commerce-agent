from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class IntentResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    intent: str
    confidence: float = Field(ge=0.0, le=1.0)
    order_id: str | None = None
    wants_latest: bool = False
    notes: str = ""


class AgentMemory(BaseModel):
    active_intent: str | None = None
    active_order_id: str | None = None


class TurnResult(BaseModel):
    trace_id: str
    user_query: str
    intent: str
    confidence: float
    entities: dict[str, Any]
    action: Literal[
        "TOOL",
        "RAG",
        "TOOL_AND_RAG",
        "DIRECT",
        "CLARIFICATION",
        "ESCALATION",
        "FALLBACK",
    ]
    retrieved_documents: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    final_answer: str
    memory: AgentMemory
    escalated: bool = False
