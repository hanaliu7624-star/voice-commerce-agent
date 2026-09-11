from __future__ import annotations

from pathlib import Path

from voice_commerce.graph import resolve_order_id
from voice_commerce.synth import generate


def test_resolve_latest_and_refund(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "ecommerce.db"
    generate(seed=42, db_path=db_path)
    monkeypatch.setattr("voice_commerce.db.DB_PATH", db_path)

    latest = resolve_order_id(
        {
            "customer_id": "CUS10001",
            "user_query": "最新订单",
            "history": [],
            "memory": {"active_intent": None, "active_order_id": None},
            "intent": "order_tracking",
            "confidence": 0.95,
            "order_id": None,
            "wants_latest": True,
            "action": "TOOL",
            "retrieved_documents": [],
            "tool_calls": [],
            "final_answer": "",
            "escalated": False,
            "trace_id": "t",
        }
    )
    assert latest["order_id"] == "ORD10002"

    refund = resolve_order_id(
        {
            "customer_id": "CUS10001",
            "user_query": "退款到哪了",
            "history": [],
            "memory": {"active_intent": None, "active_order_id": None},
            "intent": "refund_status",
            "confidence": 0.95,
            "order_id": None,
            "wants_latest": False,
            "action": "TOOL",
            "retrieved_documents": [],
            "tool_calls": [],
            "final_answer": "",
            "escalated": False,
            "trace_id": "t",
        }
    )
    assert refund["order_id"] == "ORD10003"

    clarify = resolve_order_id(
        {
            "customer_id": "CUS10001",
            "user_query": "订单到哪了",
            "history": [],
            "memory": {"active_intent": None, "active_order_id": None},
            "intent": "order_tracking",
            "confidence": 0.95,
            "order_id": None,
            "wants_latest": False,
            "action": "TOOL",
            "retrieved_documents": [],
            "tool_calls": [],
            "final_answer": "",
            "escalated": False,
            "trace_id": "t",
        }
    )
    assert clarify["action"] == "CLARIFICATION"
    assert clarify["order_id"] is None
