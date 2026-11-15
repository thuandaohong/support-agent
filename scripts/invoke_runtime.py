"""Gọi agent đang chạy trên AgentCore Runtime (Day 59) — 1 câu, hoặc cả bộ eval/graph_cases.jsonl.

Giống agents/try_graph.py nhưng đi qua endpoint CLOUD thay vì gọi ask() tại chỗ → kiểm cả đường
InvokeAgentRuntime → container → serve.py → ask(). Tự kiểm phần TẤT ĐỊNH (route, order_lookup).

Chạy:  python scripts/invoke_runtime.py "Đơn #1003 còn đổi trả được không?" --customer C003
       python scripts/invoke_runtime.py --cases            (cả 18 ca)
       python scripts/invoke_runtime.py --cases g01 g07    (vài ca)

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

REGION = os.environ.get("AWS_REGION", "us-east-1")
RUNTIME_NAME = os.environ.get("RUNTIME_NAME", "support_agent")
CASES = Path(__file__).resolve().parent.parent / "eval" / "graph_cases.jsonl"


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


def run_cases(client, arn: str, session_id: str, wanted: set[str]) -> None:
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line]
    checked = passed = 0
    for c in cases:
        if wanted and c["id"] not in wanted:
            continue
        t0 = time.perf_counter()
        out = invoke(client, arn, session_id, c["question"], c["customer_id"])
        ms = (time.perf_counter() - t0) * 1000
        # null trong file = không kiểm trường đó (giống try_graph)
        problems = []
        if c["route"] is not None and out.get("route") != c["route"]:
            problems.append(f"route={out.get('route')} (mong đợi {c['route']})")
        if c["order_lookup"] is not None and out.get("order_lookup") != c["order_lookup"]:
            problems.append(f"order_lookup={out.get('order_lookup')} (mong đợi {c['order_lookup']})")
        checked += 1
        passed += not problems
        print(f"── {c['id']} [{c['customer_id']}] {c['question']}  ({ms:.0f} ms)")
        print(f"   route={out.get('route')} order_lookup={out.get('order_lookup', '-')} "
              f"steps={out.get('steps')} {'✅' if not problems else '❌ ' + '; '.join(problems)}")
        print(f"   TRẢ LỜI: {out.get('answer')}\n")
    print(f"Qua Runtime — phần tất định (route + order_lookup): {passed}/{checked} đúng")


def main():
    parser = argparse.ArgumentParser(description="Gọi support-agent trên AgentCore Runtime.")
    parser.add_argument("question", nargs="*", help="câu hỏi, hoặc id ca khi dùng --cases")
    parser.add_argument("--customer", default="C003")
    parser.add_argument("--cases", action="store_true", help="chạy eval/graph_cases.jsonl")
    args = parser.parse_args()

    client = boto3.client("bedrock-agentcore", region_name=REGION)
    arn = runtime_arn()
    session_id = f"eval-{uuid.uuid4().hex}"
    if args.cases:
        run_cases(client, arn, session_id, set(args.question))
    elif args.question:
        print(json.dumps(invoke(client, arn, session_id, " ".join(args.question), args.customer),
                         ensure_ascii=False, indent=2))
    else:
        parser.error("cần câu hỏi hoặc --cases")


if __name__ == "__main__":
    main()
