from __future__ import annotations

import argparse
import json
import sys

from voice_commerce.config import DEFAULT_CUSTOMER_ID
from voice_commerce.db import require_db
from voice_commerce.graph import CommerceAgent
from voice_commerce.rag import build_index
from voice_commerce.synth import generate


def _utf8_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")


def _print_turn(result) -> None:
    print()
    print(f"intent={result.intent}  confidence={result.confidence:.2f}  action={result.action}")
    if result.entities.get("order_id"):
        print(f"order_id={result.entities['order_id']}")
    if result.tool_calls:
        names = ", ".join(call["name"] for call in result.tool_calls)
        print(f"tools={names}")
    if result.retrieved_documents:
        docs = ", ".join(doc["document_id"] for doc in result.retrieved_documents)
        print(f"rag={docs}")
    print(f"trace={result.trace_id}")
    print()
    print(result.final_answer)
    print()


def main(argv: list[str] | None = None) -> int:
    _utf8_stdio()
    parser = argparse.ArgumentParser(description="电商客服 Agent（文字 MVP）")
    parser.add_argument("--customer", default=DEFAULT_CUSTOMER_ID, help="模拟登录用户 ID")
    parser.add_argument("--query", help="单轮提问；不传则进入交互")
    parser.add_argument("--init-data", action="store_true", help="生成 SQLite 模拟数据")
    parser.add_argument("--rebuild-index", action="store_true", help="重建政策向量索引")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    if args.init_data:
        path = generate(seed=args.seed)
        print(f"已生成数据库: {path} (seed={args.seed})")
        return 0
    if args.rebuild_index:
        path = build_index()
        print(f"已写入政策索引: {path}")
        return 0

    require_db()
    agent = CommerceAgent(customer_id=args.customer)
    print(f"当前用户: {args.customer}  （输入 /quit 退出，/trace 查看上一轮追溯）")

    if args.query:
        result = agent.ask(args.query)
        _print_turn(result)
        return 0

    while True:
        try:
            text = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not text:
            continue
        if text in {"/quit", "/exit", "退出"}:
            return 0
        if text == "/trace":
            if not agent.last_trace:
                print("还没有对话。")
                continue
            print(json.dumps(agent.last_trace, ensure_ascii=False, indent=2))
            continue
        result = agent.ask(text)
        _print_turn(result)


if __name__ == "__main__":
    raise SystemExit(main())
