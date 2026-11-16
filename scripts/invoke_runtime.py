"""Gọi agent đang chạy trên AgentCore Runtime (Day 59) — 1 câu, hoặc cả bộ eval/graph_cases.jsonl.

Giống agents/try_graph.py nhưng đi qua endpoint CLOUD thay vì gọi ask() tại chỗ → kiểm cả đường
InvokeAgentRuntime → container → serve.py → ask(). Tự kiểm phần TẤT ĐỊNH (route, order_lookup).

Chạy:  python scripts/invoke_runtime.py "Đơn #1003 còn đổi trả được không?" --customer C003
       python scripts/invoke_runtime.py --cases            (cả 18 ca, MỖI CA MỘT SESSION)
       python scripts/invoke_runtime.py --cases g01 g07    (vài ca)
       python scripts/invoke_runtime.py --chat             (hội thoại nhiều lượt, Day 62)
       python scripts/invoke_runtime.py "Thế bảo hành?" --session <id cũ>   (hỏi tiếp một session)

Day 62: agent nhớ hội thoại theo session → các ca độc lập PHẢI khác session, không thì lịch sử
của ca trước lọt vào ca sau (vd g08 hỏi #9999 rồi g09 "Đơn của tôi bao giờ tới?" bị lấy #9999).
Đổi lại mỗi ca là một microVM mới (cold start) → cả bộ chậm hơn.

customer_id: ở đây MÌNH đóng vai backend đã xác thực (production: backend lấy từ JWT).
AS_OF_DATE do cấu hình Runtime quyết định (infra/runtime/runtime.env), không gửi trong payload.
"""
import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.eval_cases import CONVERSATIONS, GRAPH_CASES, load, problems

REGION = os.environ.get("AWS_REGION", "us-east-1")
RUNTIME_NAME = os.environ.get("RUNTIME_NAME", "support_agent")


def runtime_arn() -> str:
    """Tra ARN theo tên — không cần lưu ARN (có account ID) vào code hay file."""
    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    for rt in control.list_agent_runtimes()["agentRuntimes"]:
        if rt["agentRuntimeName"] == RUNTIME_NAME:
            return rt["agentRuntimeArn"]
    sys.exit(f"Không thấy Runtime {RUNTIME_NAME} ở {REGION}")


def invoke(client, arn: str, session_id: str, question: str, customer_id: str) -> dict:
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        qualifier="DEFAULT",
        runtimeSessionId=session_id,   # >= 33 ký tự; cùng session = cùng microVM (đỡ cold start)
        contentType="application/json",
        accept="application/json",
        payload=json.dumps({"question": question, "customer_id": customer_id}, ensure_ascii=False),
    )
    return json.loads(resp["response"].read())


def new_session(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex}"     # Runtime yêu cầu ≥ 33 ký tự


def timed(client, arn: str, session_id: str, question: str, customer_id: str) -> tuple[dict, float]:
    t0 = time.perf_counter()
    out = invoke(client, arn, session_id, question, customer_id)
    return out, (time.perf_counter() - t0) * 1000


def show(label: str, question: str, out: dict, ms: float, bad: list[str]) -> None:
    print(f"── {label} {question}  ({ms:.0f} ms)")
    print(f"   route={out.get('route')} order_lookup={out.get('order_lookup', '-')} "
          f"steps={out.get('steps')} {'✅' if not bad else '❌ ' + '; '.join(bad)}")
    print(f"   TRẢ LỜI: {out.get('answer')}\n")


def run_cases(client, arn: str, wanted: set[str]) -> None:
    checked = passed = 0
    for c in load(GRAPH_CASES):
        if wanted and c["id"] not in wanted:
            continue
        # mỗi ca một session: ca độc lập không được thấy lịch sử của ca trước
        out, ms = timed(client, arn, new_session(f"eval-{c['id']}"), c["question"], c["customer_id"])
        bad = problems(out, c)
        checked += 1
        passed += not bad
        show(f"{c['id']} [{c['customer_id']}]", c["question"], out, ms, bad)
    print(f"Qua Runtime — phần tất định (route + order_lookup): {passed}/{checked} đúng")


def run_conversations(client, arn: str, wanted: set[str]) -> None:
    checked = passed = 0
    for conv in load(CONVERSATIONS):
        if wanted and conv["id"] not in wanted:
            continue
        print(f"═══ {conv['id']}: {conv['note']}")
        session = new_session(f"chat-{conv['id']}")       # cả hội thoại chung một session
        for i, turn in enumerate(conv["turns"], 1):
            customer = turn.get("customer_id", conv["customer_id"])
            out, ms = timed(client, arn, session, turn["q"], customer)
            bad = problems(out, turn)
            checked += 1
            passed += not bad
            show(f"lượt {i} [{customer}]", turn["q"], out, ms, bad)
    print(f"Qua Runtime — hội thoại (route + order_lookup + nguồn): {passed}/{checked} lượt đúng")


def main():
    parser = argparse.ArgumentParser(description="Gọi support-agent trên AgentCore Runtime.")
    parser.add_argument("question", nargs="*", help="câu hỏi, hoặc id ca khi dùng --cases")
    parser.add_argument("--customer", default="C003")
    parser.add_argument("--cases", action="store_true", help="chạy eval/graph_cases.jsonl")
    parser.add_argument("--chat", action="store_true", help="chạy eval/conversation_cases.jsonl")
    parser.add_argument("--session", help="session id để hỏi tiếp một hội thoại (mặc định: mới)")
    args = parser.parse_args()

    client = boto3.client("bedrock-agentcore", region_name=REGION)
    arn = runtime_arn()
    if args.cases:
        run_cases(client, arn, set(args.question))
    elif args.chat:
        run_conversations(client, arn, set(args.question))
    elif args.question:
        session = args.session or new_session("cli")
        print(json.dumps(invoke(client, arn, session, " ".join(args.question), args.customer),
                         ensure_ascii=False, indent=2))
        print(f"session: {session}", file=sys.stderr)
    else:
        parser.error("cần câu hỏi, --cases hoặc --chat")


if __name__ == "__main__":
    main()
