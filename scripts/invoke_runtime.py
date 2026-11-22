"""Gọi agent đang chạy trên AgentCore Runtime (Day 59) — 1 câu, hoặc cả bộ eval/golden.jsonl.

Giống agents/try_graph.py nhưng đi qua endpoint CLOUD thay vì gọi ask() tại chỗ → kiểm cả đường
InvokeAgentRuntime → container → serve.py → ask(). Tự kiểm phần TẤT ĐỊNH (route, order_lookup).

Chạy:  python scripts/invoke_runtime.py "Đơn #1003 còn đổi trả được không?" --customer C003
       python scripts/invoke_runtime.py --cases            (cả golden, MỖI CA MỘT SESSION)
       python scripts/invoke_runtime.py --cases g01 g07    (vài ca)
       python scripts/invoke_runtime.py --chat             (hội thoại nhiều lượt, Day 62)
       python scripts/invoke_runtime.py "Thế bảo hành?" --session <id cũ>   (hỏi tiếp một session)
       python scripts/invoke_runtime.py "Đơn #1003 tới đâu?" --customer C003 --auth   (Day 63)
       python scripts/invoke_runtime.py --cases --auth     (mỗi khách đăng nhập Cognito, 1 token)
       python scripts/invoke_runtime.py "Đơn #1003 tới đâu?" --auth --attack tampered

Day 62: agent nhớ hội thoại theo session → các ca độc lập PHẢI khác session, không thì lịch sử
của ca trước lọt vào ca sau (vd g08 hỏi #9999 rồi g09 "Đơn của tôi bao giờ tới?" bị lấy #9999).
Đổi lại mỗi ca là một microVM mới (cold start) → cả bộ chậm hơn.

customer_id — hai chế độ:
  mặc định: lấy thẳng từ --customer / ca eval (như Day 59–62: tin người gọi)
  --auth (Day 63): MÌNH ĐÓNG VAI BACKEND. --customer chỉ chọn user test nào "ngồi trước bàn
    phím" → đăng nhập Cognito → access token → auth/tokens.py kiểm 6 bước → customer_id LẤY TỪ
    TOKEN mới vào payload. Token hỏng → in 401 <lý do> và KHÔNG gọi Runtime (không tốn token).
    Day 64: API Gateway + Lambda làm đúng việc này.
  --attack: thử token hỏng có chủ đích (id_token / tampered / garbage), --token-file: token tuỳ ý.
AS_OF_DATE do cấu hình Runtime quyết định (infra/runtime/runtime.env), không gửi trong payload.
"""
import argparse
import base64
import json
import os
import sys
import time
import uuid
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.eval_cases import CONVERSATIONS, GOLDEN, load, problems, score
from auth.tokens import AuthError

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


class Backend:
    """--auth: đóng vai backend Day 64 — chỉ tin customer_id lấy từ access token đã kiểm."""

    def __init__(self):
        # import muộn: chỉ cần khi --auth (cognito-idp + test-users.env)
        from auth.cognito import Cognito
        self.cognito = Cognito()
        self.verifier = self.cognito.verifier()
        self.tokens: dict[str, dict] = {}     # user → kết quả login (token sống 60 phút: login 1 lần)

    def login(self, user: str) -> dict:
        if user not in self.tokens:
            self.tokens[user] = self.cognito.login(user)
        return self.tokens[user]

    def customer_id(self, user: str, attack: str | None = None, token: str | None = None) -> str:
        """Token của `user` (hoặc token đưa vào / token bị phá) → kiểm → customer_id. Sai → AuthError."""
        if token is None:
            token = forge(self.login(user), attack) if attack else self.login(user)["AccessToken"]
        return self.verifier.customer_id(token)


def forge(login: dict, attack: str) -> str:
    """Token hỏng có chủ đích, từ token THẬT của user."""
    if attack == "id_token":                   # đúng chữ ký, đúng pool — nhưng là ID token
        return login["IdToken"]
    if attack == "tampered":                   # đổi username sang khách khác, giữ chữ ký cũ
        header, payload, signature = login["AccessToken"].split(".")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        claims["username"] = "c020" if claims["username"] != "c020" else "c003"
        forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        return f"{header}.{forged}.{signature}"
    return "not-a-jwt"                         # garbage


def who(backend: Backend | None, customer: str) -> str:
    """customer_id gửi vào payload: mặc định tin tham số; --auth → lấy từ token đã kiểm."""
    return customer if backend is None else backend.customer_id(customer)


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


def run_cases(client, arn: str, wanted: set[str], backend: Backend | None) -> None:
    checked = passed = 0
    for c in load(GOLDEN):
        if wanted and c["id"] not in wanted:
            continue
        # mỗi ca một session: ca độc lập không được thấy lịch sử của ca trước
        customer = who(backend, c["customer_id"])
        out, ms = timed(client, arn, new_session(f"eval-{c['id']}"), c["question"], customer)
        bad = score(out, c)["problems"]
        checked += 1
        passed += not bad
        show(f"{c['id']} [{customer}{' 🔑' if backend else ''}]", c["question"], out, ms, bad)
    print(f"Qua Runtime — phần tất định (route + order_lookup + nguồn): {passed}/{checked} đúng")


def run_conversations(client, arn: str, wanted: set[str], backend: Backend | None) -> None:
    checked = passed = 0
    for conv in load(CONVERSATIONS):
        if wanted and conv["id"] not in wanted:
            continue
        print(f"═══ {conv['id']}: {conv['note']}")
        session = new_session(f"chat-{conv['id']}")       # cả hội thoại chung một session
        for i, turn in enumerate(conv["turns"], 1):
            customer = who(backend, turn.get("customer_id", conv["customer_id"]))
            out, ms = timed(client, arn, session, turn["q"], customer)
            bad = problems(out, turn)
            checked += 1
            passed += not bad
            show(f"lượt {i} [{customer}{' 🔑' if backend else ''}]", turn["q"], out, ms, bad)
    print(f"Qua Runtime — hội thoại (route + order_lookup + nguồn): {passed}/{checked} lượt đúng")


def main():
    parser = argparse.ArgumentParser(description="Gọi support-agent trên AgentCore Runtime.")
    parser.add_argument("question", nargs="*", help="câu hỏi, hoặc id ca khi dùng --cases")
    parser.add_argument("--customer", default="C003")
    parser.add_argument("--cases", action="store_true", help="chạy eval/golden.jsonl (chấm + lưu file: scripts/run_eval.py)")
    parser.add_argument("--chat", action="store_true", help="chạy eval/conversation_cases.jsonl")
    parser.add_argument("--session", help="session id để hỏi tiếp một hội thoại (mặc định: mới)")
    parser.add_argument("--auth", action="store_true",
                        help="Day 63: đăng nhập Cognito, customer_id lấy từ token đã kiểm")
    parser.add_argument("--attack", choices=["id_token", "tampered", "garbage"],
                        help="(cần --auth) gửi token hỏng có chủ đích — phải bị chặn trước Runtime")
    parser.add_argument("--token-file", help="(cần --auth) đọc access token từ file thay vì đăng nhập")
    args = parser.parse_args()
    if (args.attack or args.token_file) and not args.auth:
        parser.error("--attack / --token-file cần --auth")

    backend = Backend() if args.auth else None
    client = boto3.client("bedrock-agentcore", region_name=REGION)
    arn = runtime_arn()
    try:
        if args.cases:
            run_cases(client, arn, set(args.question), backend)
        elif args.chat:
            run_conversations(client, arn, set(args.question), backend)
        elif args.question:
            customer = args.customer
            if backend:
                token = Path(args.token_file).read_text().strip() if args.token_file else None
                customer = backend.customer_id(args.customer, args.attack, token)
                print(f"auth: token hợp lệ → customer_id={customer}", file=sys.stderr)
            session = args.session or new_session("cli")
            print(json.dumps(invoke(client, arn, session, " ".join(args.question), customer),
                             ensure_ascii=False, indent=2))
            print(f"session: {session}", file=sys.stderr)
        else:
            parser.error("cần câu hỏi, --cases hoặc --chat")
    except AuthError as e:
        # backend thật trả HTTP 401 (503 nếu JWKS sập) — và KHÔNG gọi Runtime
        code = 503 if e.reason == "jwks_unavailable" else 401
        sys.exit(f"{code} {e.reason} — không gọi Runtime")


if __name__ == "__main__":
    main()
