"""V1 意图表。action 由意图决定，不由模型另猜。"""

from __future__ import annotations

from typing import Literal

Action = Literal[
    "TOOL",
    "RAG",
    "TOOL_AND_RAG",
    "DIRECT",
    "CLARIFICATION",
    "ESCALATION",
    "FALLBACK",
]

INTENT_ACTIONS: dict[str, Action] = {
    "order_tracking": "TOOL",
    "order_status": "TOOL",
    "order_history": "TOOL",
    "order_cancellation": "TOOL_AND_RAG",
    "delivery_status": "TOOL",
    "delivery_eta": "TOOL",
    "delivery_delay": "TOOL_AND_RAG",
    "payment_status": "TOOL",
    "payment_failed": "TOOL",
    "payment_policy": "RAG",
    "return_policy": "RAG",
    "refund_policy": "RAG",
    "refund_status": "TOOL",
    "return_status": "TOOL",
    "complaint": "ESCALATION",
    "human_support": "ESCALATION",
    "create_support_ticket": "ESCALATION",
    "greeting": "DIRECT",
    "help": "DIRECT",
}

MVP_INTENTS = [
    "order_tracking",
    "order_status",
    "order_history",
    "delivery_status",
    "delivery_eta",
    "delivery_delay",
    "payment_failed",
    "refund_status",
    "return_policy",
    "refund_policy",
    "complaint",
    "human_support",
    "greeting",
    "help",
]

TOOL_INTENTS = {name for name, action in INTENT_ACTIONS.items() if "TOOL" in action}
RAG_INTENTS = {name for name, action in INTENT_ACTIONS.items() if "RAG" in action}

CONFIDENCE_EXECUTE = 0.85
CONFIDENCE_CLARIFY = 0.60
