"""Eval harness (Day 66): chạy cả bộ eval/golden.jsonl qua agent → chấm → bảng theo nhóm → lưu file.

Chạy:  python scripts/run_eval.py                      # local: agents.graph.ask() (gọi Bedrock thật)
       python scripts/run_eval.py --target runtime     # qua AgentCore Runtime đang chạy
       python scripts/run_eval.py --only m01,s02       # vài ca
       python scripts/run_eval.py --min-routing 0.9    # exit 1 nếu routing tổng < 90%

Mỗi ca ĐỘC LẬP: local không truyền session_id (ask() không nhớ gì); Runtime mỗi ca một session mới
(agent có Memory theo session — dùng chung thì ca sau thấy lịch sử ca trước).

Màn hình chỉ in id + đúng/sai + chỗ sai, KHÔNG in câu trả lời. Câu trả lời + reference nằm trong
eval/results/<YYYYmmdd-HHMMSS>-<target>.jsonl (gitignore): dòng 1 là meta (git sha, model, image,
as_of_date, bảng điểm), mỗi dòng sau một ca — Day 20 (LLM-as-judge) chấm từ file này, không chạy lại agent.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agents.eval_cases import (
    EVAL_DIR,
    GOLDEN,
    format_table,
    load,
    rate,
    score,
    summarize,
)

RESULTS_DIR = EVAL_DIR / "results"
# "Hôm nay" cố định cho luật đổi trả — reference viết theo ngày này (Runtime: AS_OF_DATE trong Terraform)
AS_OF_DATE = "2026-11-08"
OUT_FIELDS = ("answer", "sources", "route", "order_lookup", "steps", "error")


def git_sha() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                               capture_output=True, text=True, check=False).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def local_target():
    """→ (call, meta). call(case) gọi graph trong process, không session."""
    from agents.graph import ask
    from agents.supervisor import ROUTER_MODEL_ID

    def call(case: dict) -> dict:
        return ask(case["question"], case["customer_id"], as_of_date=AS_OF_DATE)

    return call, {"model": ROUTER_MODEL_ID, "as_of_date": AS_OF_DATE}


def runtime_target():
    """→ (call, meta). call(case) gọi InvokeAgentRuntime, mỗi ca một session."""
    import boto3

    from scripts.invoke_runtime import REGION, invoke, new_session, runtime_arn

    arn = runtime_arn()
    client = boto3.client("bedrock-agentcore", region_name=REGION)
    rt = boto3.client("bedrock-agentcore-control", region_name=REGION).get_agent_runtime(
        agentRuntimeId=arn.rsplit("/", 1)[-1])
    env = rt.get("environmentVariables") or {}
    uri = rt.get("agentRuntimeArtifact", {}).get("containerConfiguration", {}).get("containerUri", "")

    def call(case: dict) -> dict:
        return invoke(client, arn, new_session(f"eval-{case['id']}"), case["question"], case["customer_id"])

    # chỉ lấy TAG image (URI có account id), không ghi ARN
    return call, {"model": env.get("ROUTER_MODEL_ID"), "as_of_date": env.get("AS_OF_DATE"),
                  "image_tag": uri.rsplit(":", 1)[-1] if ":" in uri else None}


def run(cases: list[dict], call) -> list[dict]:
    """Chạy từng ca, chấm, in một dòng. Lỗi gọi agent (throttle, mạng) → ghi thành error, chạy tiếp."""
    rows = []
    for c in cases:
        t0 = time.perf_counter()
        try:
            out = call(c)
        except Exception as e:  # noqa: BLE001 — một ca hỏng không được dừng cả lượt
            out = {"error": f"exception:{type(e).__name__}"}
        ms = round((time.perf_counter() - t0) * 1000)
        sc = score(out, c)
        mark = "✅" if sc["ok"] else "❌ " + "; ".join(sc["problems"])
        print(f"{c['id']:<5} {c['group']:<9} {ms:>6} ms  {mark}", flush=True)
        rows.append({
            "id": c["id"], "group": c["group"], "question": c["question"], "customer_id": c["customer_id"],
            "expected": {k: c.get(k) for k in ("route", "order_lookup", "sources", "forbid_source")},
            "reference": c["reference"],
            "out": {k: out[k] for k in OUT_FIELDS if k in out},
            "ms": ms, "score": sc,
        })
    return rows


def write_results(path: Path, meta: dict, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"meta": meta}, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None, targets: dict | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chạy eval/golden.jsonl qua agent và chấm điểm.")
    parser.add_argument("--target", choices=["local", "runtime"], default="local")
    parser.add_argument("--only", help="danh sách id, cách nhau bởi dấu phẩy")
    parser.add_argument("--min-routing", type=float, default=0.85, help="exit 1 nếu routing tổng thấp hơn")
    args = parser.parse_args(argv)

    cases = load(GOLDEN)
    if args.only:
        wanted = set(args.only.split(","))
        unknown = wanted - {c["id"] for c in cases}
        if unknown:
            parser.error(f"không có ca: {', '.join(sorted(unknown))}")
        cases = [c for c in cases if c["id"] in wanted]

    targets = targets or {"local": local_target, "runtime": runtime_target}
    call, target_meta = targets[args.target]()
    started = datetime.now()
    rows = run(cases, call)
    table = summarize([(r, r["score"]) for r in rows])

    meta = {"target": args.target, "git": git_sha(), "started": started.isoformat(timespec="seconds"),
            "cases": len(rows), "only": args.only, **target_meta, "summary": table}
    path = RESULTS_DIR / f"{started:%Y%m%d-%H%M%S}-{args.target}.jsonl"
    write_results(path, meta, rows)

    routing = rate(table["TỔNG"]["routing"])
    print("\n" + format_table(table))
    print(f"\nRouting accuracy: {table['TỔNG']['routing'][0]}/{table['TỔNG']['routing'][1]} = {routing:.0%}"
          f"  ({args.target}, {meta.get('model')})")
    print(f"Đã lưu: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    if routing < args.min_routing:
        print(f"⛔ routing {routing:.0%} < ngưỡng {args.min_routing:.0%}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
