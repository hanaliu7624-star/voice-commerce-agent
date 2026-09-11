from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice_commerce.config import DEFAULT_CUSTOMER_ID, ROOT as PROJECT_ROOT
from voice_commerce.graph import CommerceAgent


def _contains(text: str, needle: str) -> bool:
    return needle.lower() in text.lower()


def run_eval(path: Path, customer_id: str) -> int:
    cases = json.loads(path.read_text(encoding="utf-8"))
    failed = 0
    for case in cases:
        agent = CommerceAgent(customer_id=customer_id)
        if case.get("setup_query"):
            agent.ask(case["setup_query"])
        result = agent.ask(case["query"])
        errors: list[str] = []
        if result.intent != case["expected_intent"]:
            errors.append(f"intent {result.intent} != {case['expected_intent']}")
        if case.get("expected_action") and result.action != case["expected_action"]:
            errors.append(f"action {result.action} != {case['expected_action']}")
        if case.get("expected_order_id") and result.entities.get("order_id") != case["expected_order_id"]:
            errors.append(f"order_id {result.entities.get('order_id')} != {case['expected_order_id']}")
        tool_names = [call["name"] for call in result.tool_calls]
        for name in case.get("required_tools") or []:
            if name not in tool_names:
                errors.append(f"missing tool {name}")
        answer = result.final_answer
        for needle in case.get("must_contain") or []:
            if not _contains(answer, needle) and not _contains(json.dumps(result.tool_calls, ensure_ascii=False), needle):
                errors.append(f"missing '{needle}'")
        blob = answer + json.dumps(result.tool_calls, ensure_ascii=False)
        for needle in case.get("must_not_contain") or []:
            if needle and _contains(blob, needle) and needle != "ORD":
                errors.append(f"unexpected '{needle}'")
            if needle == "ORD" and "ORD" in answer:
                errors.append("answer leaked order id")
        status = "PASS" if not errors else "FAIL"
        if errors:
            failed += 1
        print(f"{status}  {case['id']}: {result.intent}/{result.action}  {'; '.join(errors)}")
    print(f"\n{len(cases) - failed}/{len(cases)} passed")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=str(PROJECT_ROOT / "eval" / "golden_cases.json"))
    parser.add_argument("--customer", default=DEFAULT_CUSTOMER_ID)
    args = parser.parse_args()
    return run_eval(Path(args.file), args.customer)


if __name__ == "__main__":
    raise SystemExit(main())
