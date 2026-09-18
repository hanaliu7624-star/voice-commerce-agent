from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from domain.intents import (
    CONFIDENCE_CLARIFY,
    CONFIDENCE_EXECUTE,
    INTENT_ACTIONS,
)
from voice_commerce.config import LLM_BASE_URL, LLM_MODEL, require_api_key
from voice_commerce.models import AgentMemory, IntentResult, TurnResult
from voice_commerce.prompts import ANSWER_SYSTEM, ROUTER_SYSTEM
from voice_commerce.rag import retrieve
from voice_commerce.tools import (
    get_customer_orders,
    get_customer_refunds,
    get_delivery,
    get_order,
    get_refund,
    pick_latest_order_id,
)
from voice_commerce.trace import new_trace_id, write_trace

ORDER_ID_RE = re.compile(r"ORD\d{5}", re.IGNORECASE)


class GraphState(TypedDict):
    customer_id: str
    user_query: str
    history: list[dict[str, str]]
    memory: dict[str, str | None]
    intent: str
    confidence: float
    order_id: str | None
    wants_latest: bool
    action: str
    retrieved_documents: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    final_answer: str
    escalated: bool
    trace_id: str


def _llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=require_api_key(),
        base_url=LLM_BASE_URL,
        temperature=0,
        extra_body={"enable_thinking": False},
    )


def _parse_intent(text: str) -> IntentResult:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)
    return IntentResult.model_validate_json(raw)


def _history_text(history: list[dict[str, str]]) -> str:
    if not history:
        return "（无）"
    lines = []
    for item in history[-6:]:
        role = "用户" if item["role"] == "user" else "客服"
        lines.append(f"{role}: {item['content']}")
    return "\n".join(lines)


def route_node(state: GraphState) -> dict[str, Any]:
    message = _llm().invoke(
        [
            SystemMessage(content=ROUTER_SYSTEM + "\n只输出一个 JSON 对象，字段：intent, confidence, order_id, wants_latest, notes。"),
            HumanMessage(
                content=(
                    f"当前记忆订单号: {state['memory'].get('active_order_id')}\n"
                    f"历史对话:\n{_history_text(state['history'])}\n\n"
                    f"本轮用户: {state['user_query']}"
                )
            ),
        ]
    )
    content = message.content
    if isinstance(content, list):
        content = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block) for block in content
        )
    parsed = _parse_intent(str(content))
    intent = parsed.intent if parsed.intent in INTENT_ACTIONS else "help"
    confidence = parsed.confidence
    query = state["user_query"]
    # 订单号只认用户原文；禁止路由器臆造 ORD 号。
    match = ORDER_ID_RE.search(query)
    order_id = match.group(0).upper() if match else None
    # 「最新/最近」只认用户原文，禁止路由器误标 wants_latest 跳过澄清。
    wants_latest = ("最新" in query) or ("最近" in query)
    intent = _override_intent(query, intent)

    action = INTENT_ACTIONS[intent]
    if confidence < CONFIDENCE_CLARIFY:
        action = "FALLBACK"
    elif confidence < CONFIDENCE_EXECUTE:
        action = "CLARIFICATION"

    return {
        "intent": intent,
        "confidence": confidence,
        "order_id": order_id,
        "wants_latest": wants_latest,
        "action": action,
        "escalated": action == "ESCALATION",
    }


def _override_intent(query: str, intent: str) -> str:
    """对明确口语做确定性纠偏，减少相近意图抖动。"""
    if "退款" in query:
        if any(k in query for k in ("到账", "进度", "到哪儿了", "到哪了", "怎么还没")) and not any(
            k in query for k in ("一般", "几天", "规则", "多久能")
        ):
            return "refund_status"
        return intent
    if any(k in query for k in ("还没送到", "还没到货", "为什么还没送", "延迟了", "延误", "物流延误")):
        return "delivery_delay"
    if any(k in query for k in ("什么时候能到", "什么时候送到", "何时能到", "预计到")):
        return "delivery_eta"
    if any(k in query for k in ("在哪里", "到哪了", "到哪儿了", "物流到哪")):
        return "order_tracking"
    return intent


def resolve_order_id(state: GraphState) -> dict[str, Any]:
    action = state["action"]
    if action not in {"TOOL", "TOOL_AND_RAG"}:
        return {}

    order_id = state.get("order_id") or state["memory"].get("active_order_id")
    if state.get("wants_latest"):
        order_id = pick_latest_order_id(state["customer_id"])
    if not order_id and state["intent"] in {"refund_status", "return_status"}:
        refunds = get_customer_refunds(state["customer_id"])
        if len(refunds) == 1:
            order_id = refunds[0]["order_id"]
    if order_id:
        return {"order_id": order_id}

    orders = get_customer_orders(state["customer_id"])
    if len(orders) == 1:
        return {"order_id": orders[0]["order_id"]}
    return {"action": "CLARIFICATION", "order_id": None}


def retrieve_node(state: GraphState) -> dict[str, Any]:
    docs = retrieve(state["user_query"])
    return {"retrieved_documents": docs}


def tools_node(state: GraphState) -> dict[str, Any]:
    customer_id = state["customer_id"]
    order_id = state.get("order_id")
    intent = state["intent"]
    calls: list[dict[str, Any]] = []

    if intent == "order_history" and not order_id:
        result = get_customer_orders(customer_id)
        calls.append({"name": "get_customer_orders", "arguments": {"customer_id": customer_id}, "result": result})
        return {"tool_calls": calls}

    if not order_id:
        return {"tool_calls": calls, "action": "CLARIFICATION"}

    need_order = intent in {
        "order_tracking",
        "order_status",
        "order_cancellation",
        "payment_status",
        "payment_failed",
        "return_status",
    }
    need_delivery = intent in {
        "order_tracking",
        "delivery_status",
        "delivery_eta",
        "delivery_delay",
    }
    need_refund = intent in {"refund_status", "return_status"}

    if need_order or need_delivery or need_refund:
        result = get_order(customer_id, order_id)
        calls.append(
            {
                "name": "get_order",
                "arguments": {"customer_id": customer_id, "order_id": order_id},
                "result": result,
            }
        )
    if need_delivery:
        result = get_delivery(customer_id, order_id)
        calls.append(
            {
                "name": "get_delivery",
                "arguments": {"customer_id": customer_id, "order_id": order_id},
                "result": result,
            }
        )
    if need_refund:
        result = get_refund(customer_id, order_id)
        calls.append(
            {
                "name": "get_refund",
                "arguments": {"customer_id": customer_id, "order_id": order_id},
                "result": result,
            }
        )
    return {"tool_calls": calls}


def _format_tool_answer(state: GraphState) -> str | None:
    """事实类问题优先用工具结果拼答案，减少模型编造登录/订单信息。"""
    if state["action"] not in {"TOOL", "TOOL_AND_RAG"}:
        return None
    calls = state.get("tool_calls") or []
    if not calls:
        return None
    intent = state["intent"]
    by_name = {c["name"]: c.get("result") or {} for c in calls}

    order = by_name.get("get_order") or {}
    delivery = by_name.get("get_delivery") or {}
    refund = by_name.get("get_refund") or {}

    if order and order.get("found") is False:
        return f"在当前账号 {state['customer_id']} 下查不到订单 {order.get('order_id')}。请核对订单号，或说“最新一单”。"

    if intent in {"order_tracking", "order_status", "payment_failed", "payment_status"} and order.get("found"):
        parts = [
            f"订单 {order['order_id']} 当前状态是 {order.get('status')}。",
            f"商品：{order.get('product_name')}，金额 {order.get('amount')} {order.get('currency')}。",
        ]
        if order.get("payment_status"):
            parts.append(f"支付状态：{order['payment_status']}。")
        if order.get("status") == "CANCELLED":
            parts.append("该订单已取消，不会再配送。")
        shipment = delivery.get("shipment") if delivery.get("found") else None
        if shipment:
            parts.append(
                f"物流状态：{shipment.get('status')}，承运商 {shipment.get('carrier')}，"
                f"预计送达 {shipment.get('estimated_delivery_date') or '暂无'}。"
            )
        elif intent == "order_tracking":
            parts.append(delivery.get("reason") or "当前还没有物流单。")
        return "".join(parts)

    if intent in {"delivery_status", "delivery_eta", "delivery_delay"}:
        if order.get("found") and order.get("status") == "CANCELLED":
            return f"订单 {order['order_id']} 已取消，无法安排配送，也不能告知到货时间。"
        if delivery.get("found") and delivery.get("shipment"):
            shipment = delivery["shipment"]
            base = (
                f"订单 {delivery['order_id']} 物流状态是 {shipment.get('status')}，"
                f"承运商 {shipment.get('carrier')}，运单号 {shipment.get('tracking_number')}。"
            )
            if shipment.get("status") == "DELAYED":
                return base + f"已超过预计送达日 {shipment.get('estimated_delivery_date')}，属于延迟件。"
            if shipment.get("estimated_delivery_date"):
                return base + f"预计送达日是 {shipment['estimated_delivery_date']}。"
            return base
        if delivery.get("found"):
            return f"订单 {delivery.get('order_id')} {delivery.get('reason') or '暂无物流信息'}。"

    if intent == "refund_status" and refund.get("found"):
        if refund.get("refund"):
            r = refund["refund"]
            return (
                f"订单 {refund['order_id']} 的退款单 {r.get('refund_id')} 当前状态是 {r.get('status')}，"
                f"金额 {r.get('amount')} {r.get('currency')}，原因：{r.get('reason')}。"
            )
        return f"订单 {refund.get('order_id')} {refund.get('reason') or '没有退款单'}。"

    return None


def generate_node(state: GraphState) -> dict[str, Any]:
    action = state["action"]
    if action == "ESCALATION":
        answer = "这个问题需要人工客服继续处理。我已经为你登记升级，请稍等，人工坐席会接入。我不会继续自行给出处理结论。"
        return {"final_answer": answer, "escalated": True}
    if action == "CLARIFICATION":
        orders = get_customer_orders(state["customer_id"])
        ids = "、".join(o["order_id"] + f"（{o['status']} {o['product_name']}）" for o in orders[:5]) or "暂无订单"
        answer = (
            f"当前已登录账号 {state['customer_id']}。"
            f"我需要确认你要查哪一笔订单。你名下最近的订单有：{ids}。请告诉我订单号，或者说“最新一单”。"
        )
        return {"final_answer": answer}
    if action == "FALLBACK":
        answer = "我还没听清你的具体需求。你可以问订单物流、支付是否成功、退款进度，或退货退款规则。也可以说“转人工”。"
        return {"final_answer": answer}
    if action == "DIRECT":
        if state["intent"] == "greeting":
            answer = (
                f"你好，我是电商客服助手。当前账号 {state['customer_id']} 已登录。"
                "可以帮你查订单、物流、支付和退款，也可以说明退货退款规则。"
            )
        else:
            answer = "我可以查询你的订单、物流、支付失败原因和退款进度，也可以说明退货退款与配送规则。请直接说出问题。"
        return {"final_answer": answer}

    factual = _format_tool_answer(state)
    if factual and action == "TOOL":
        return {"final_answer": factual}

    payload = {
        "customer_id": state["customer_id"],
        "authenticated": True,
        "intent": state["intent"],
        "action": action,
        "order_id": state.get("order_id"),
        "tool_results": state.get("tool_calls") or [],
        "retrieved_documents": [
            {"document_id": d.get("document_id"), "score": d.get("score"), "content": d.get("content")}
            for d in (state.get("retrieved_documents") or [])
        ],
        "tool_summary": factual,
    }
    llm = _llm()
    message = llm.invoke(
        [
            SystemMessage(content=ANSWER_SYSTEM),
            HumanMessage(
                content=f"用户问题：{state['user_query']}\n\n证据：\n{json.dumps(payload, ensure_ascii=False)}"
            ),
        ]
    )
    content = message.content
    if isinstance(content, list):
        content = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block) for block in content
        )
    return {"final_answer": str(content)}


def route_after_classify(state: GraphState) -> str:
    return state["action"]


def after_resolve(state: GraphState) -> str:
    action = state["action"]
    if action == "TOOL":
        return "tools"
    if action == "RAG":
        return "retrieve"
    if action == "TOOL_AND_RAG":
        return "tools"
    return "generate"


def after_tools(state: GraphState) -> str:
    if state["action"] == "TOOL_AND_RAG":
        return "retrieve"
    return "generate"


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("route", route_node)
    graph.add_node("resolve", resolve_order_id)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("tools", tools_node)
    graph.add_node("generate", generate_node)
    graph.add_edge(START, "route")
    graph.add_conditional_edges(
        "route",
        route_after_classify,
        {
            "TOOL": "resolve",
            "RAG": "retrieve",
            "TOOL_AND_RAG": "resolve",
            "DIRECT": "generate",
            "CLARIFICATION": "generate",
            "ESCALATION": "generate",
            "FALLBACK": "generate",
        },
    )
    graph.add_conditional_edges(
        "resolve",
        after_resolve,
        {
            "tools": "tools",
            "retrieve": "retrieve",
            "generate": "generate",
        },
    )
    graph.add_conditional_edges(
        "tools",
        after_tools,
        {"retrieve": "retrieve", "generate": "generate"},
    )
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


class CommerceAgent:
    def __init__(self, customer_id: str):
        self.customer_id = customer_id
        self.graph = build_graph()
        self.memory = AgentMemory()
        self.history: list[dict[str, str]] = []
        self.last_trace: dict[str, Any] | None = None

    def ask(self, user_query: str) -> TurnResult:
        state: GraphState = {
            "customer_id": self.customer_id,
            "user_query": user_query,
            "history": list(self.history),
            "memory": self.memory.model_dump(),
            "intent": "",
            "confidence": 0.0,
            "order_id": None,
            "wants_latest": False,
            "action": "FALLBACK",
            "retrieved_documents": [],
            "tool_calls": [],
            "final_answer": "",
            "escalated": False,
            "trace_id": new_trace_id(),
        }
        out = self.graph.invoke(state)
        if out.get("order_id") and out.get("action") in {"TOOL", "TOOL_AND_RAG", "RAG"}:
            self.memory.active_order_id = out["order_id"]
            self.memory.active_intent = out["intent"]
        if out.get("escalated"):
            self.memory.active_intent = "human_support"
        result = TurnResult(
            trace_id=out["trace_id"],
            user_query=user_query,
            intent=out["intent"],
            confidence=out["confidence"],
            entities={"order_id": out.get("order_id")},
            action=out["action"],
            retrieved_documents=out.get("retrieved_documents") or [],
            tool_calls=out.get("tool_calls") or [],
            final_answer=out["final_answer"],
            memory=self.memory,
            escalated=bool(out.get("escalated")),
        )
        path = write_trace(result.model_dump())
        self.last_trace = {**result.model_dump(), "trace_path": str(path)}
        self.history.append({"role": "user", "content": user_query})
        self.history.append({"role": "assistant", "content": result.final_answer})
        return result
