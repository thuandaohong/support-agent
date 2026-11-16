"""Rà IAM của support-agent bằng máy (Day 63) — CHỈ ĐỌC, chạy lại bao nhiêu lần cũng được.

Ba phần:
  1. Bản đồ quyền: trust + permission của 5 role (runtime, gateway, 2 Lambda, KB). Account ID che thành <ACC>.
  2. IAM Access Analyzer validate-policy: lỗi cú pháp, wildcard rộng, cảnh báo bảo mật.
  3. Ma trận simulate: mỗi role thử cả việc PHẢI ĐƯỢC lẫn việc PHẢI BỊ CHẶN. Mỗi lần simulate đúng
     1 hành động × 1 resource — gộp nhiều resource vào một lần cho kết quả sai (bài học Day 61).
Thêm một luật riêng: trust của role dịch vụ AgentCore/Bedrock phải có SourceAccount + SourceArn hẹp
(chống confused deputy) — SourceArn kết thúc bằng ":*" bị coi là quá rộng.

Có ERROR / SECURITY_WARNING, trust quá rộng, hoặc ô ma trận lệch kỳ vọng → exit 1.

Chạy qua infra/iam-audit.sh (nạp tên role/bảng/model từ runtime.env + gateway.env).
"""
from __future__ import annotations

import json
import os
import re
import sys

import boto3

REGION = os.environ["AWS_REGION"]
ACCOUNT = os.environ["ACCOUNT_ID"]
env = os.environ.__getitem__

iam = boto3.client("iam")
analyzer = boto3.client("accessanalyzer", region_name=REGION)
bedrock_agent = boto3.client("bedrock-agent", region_name=REGION)
agentcore = boto3.client("bedrock-agentcore-control", region_name=REGION)


HIDE: dict[str, str] = {}   # giá trị thật → nhãn (KB id...), điền sau khi tra


def mask(value) -> str:
    """Che account ID + KB id: output này được chép vào docs/iam.md (repo public)."""
    text = re.sub(r"\d{12}", "<ACC>", value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))
    for real, label in HIDE.items():
        text = text.replace(real, label)
    return text


def as_list(x):
    return x if isinstance(x, list) else [x]


# ─── tra tài nguyên theo tên (không lưu id nào vào file) ───

def kb(name: str) -> dict | None:
    for s in bedrock_agent.list_knowledge_bases()["knowledgeBaseSummaries"]:
        if s["name"] == name:
            return bedrock_agent.get_knowledge_base(knowledgeBaseId=s["knowledgeBaseId"])["knowledgeBase"]
    return None


def kb_bucket(role: str) -> str:
    """Bucket tài liệu của KB. KB loại MANAGED không ghi bucket trong data source → lấy từ chính
    statement s3:GetObject của role KB (ARN "arn:aws:s3:::<bucket>/*")."""
    for _, doc in permission_policies(role):
        for s in doc["Statement"]:
            if "s3:GetObject" in as_list(s["Action"]):
                return as_list(s["Resource"])[0].removesuffix("/*")
    sys.exit(f"Role {role} không có s3:GetObject — không xác định được bucket của KB")


def gateway_id(name: str) -> str:
    for g in agentcore.list_gateways()["items"]:
        if g["name"] == name:
            return g["gatewayId"]
    sys.exit(f"Không thấy Gateway {name}")



# ─── đọc policy ───

def permission_policies(role: str) -> list[tuple[str, dict]]:
    """(tên, document) của inline + managed policy gắn vào role."""
    docs = [(name, iam.get_role_policy(RoleName=role, PolicyName=name)["PolicyDocument"])
            for name in iam.list_role_policies(RoleName=role)["PolicyNames"]]
    for p in iam.list_attached_role_policies(RoleName=role)["AttachedPolicies"]:
        version = iam.get_policy(PolicyArn=p["PolicyArn"])["Policy"]["DefaultVersionId"]
        doc = iam.get_policy_version(PolicyArn=p["PolicyArn"], VersionId=version)["PolicyVersion"]["Document"]
        docs.append((p["PolicyName"], doc))
    return docs


def trust_problems(trust: dict) -> list[str]:
    """Role dịch vụ AgentCore/Bedrock phải khoá SourceAccount + SourceArn hẹp. Lambda: mẫu chuẩn AWS, bỏ qua."""
    problems = []
    for s in trust["Statement"]:
        services = as_list(s.get("Principal", {}).get("Service", []))
        if not any(svc.startswith(("bedrock", "bedrock-agentcore")) for svc in services):
            continue
        cond = s.get("Condition", {})
        if "aws:SourceAccount" not in json.dumps(cond):
            problems.append("thiếu aws:SourceAccount")
        arns = [a for op in ("ArnLike", "ArnEquals") for a in as_list(cond.get(op, {}).get("aws:SourceArn", []))]
        if not arns:
            problems.append("thiếu aws:SourceArn")
        problems += [f"SourceArn quá rộng: {mask(a)}" for a in arns if a.endswith(":*")]
    return problems


def validate(doc: dict, policy_type: str, resource_type: str | None = None) -> list[dict]:
    kw = {"policyDocument": json.dumps(doc), "policyType": policy_type}
    if resource_type:
        kw["validatePolicyResourceType"] = resource_type
    return analyzer.validate_policy(**kw)["findings"]


def simulate(role_arn: str, action: str, resource: str) -> str:
    r = iam.simulate_principal_policy(PolicySourceArn=role_arn, ActionNames=[action], ResourceArns=[resource])
    return r["EvaluationResults"][0]["EvalDecision"]


# ─── tài nguyên + ma trận (tra theo tên lúc chạy) ───

support_kb = kb(env("KB_NAME")) or sys.exit(f"Không thấy KB {env('KB_NAME')}")
HIDE[support_kb["knowledgeBaseId"]] = "<KB_ID>"
KB_ROLE = support_kb["roleArn"].rsplit("/", 1)[-1]
BUCKET = kb_bucket(KB_ROLE)
GW_ID = gateway_id(env("GATEWAY_NAME"))

ARN = {
    "model": f"arn:aws:bedrock:{REGION}::foundation-model/{env('MODEL_ID')}",
    "model_other": f"arn:aws:bedrock:{REGION}::foundation-model/amazon.nova-pro-v1:0",
    "gateway": f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:gateway/{GW_ID}",
    "gateway_other": f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:gateway/other-gateway-abcdefghij",
    "kb": support_kb["knowledgeBaseArn"],
    "kb_other": f"arn:aws:bedrock:{REGION}:{ACCOUNT}:knowledge-base/OTHERKB000",
    "table": f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/{env('ORDERS_TABLE')}",
    "table_other": f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/other-table",
    "fn_order": f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{env('LAMBDA_NAME')}",
    "fn_policy": f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{env('POLICY_LAMBDA_NAME')}",
    "fn_other": f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:other-function",
    "bucket_obj": f"{BUCKET}/policies/example.md",
    "bucket_other_obj": "arn:aws:s3:::other-bucket-example/file.md",
}

ROLES = {   # nhãn ngắn → tên role thật
    "runtime": env("ROLE_NAME"),
    "gateway": env("GATEWAY_ROLE"),
    "lambda get_order": env("LAMBDA_ROLE"),
    "lambda search_policy": env("POLICY_LAMBDA_ROLE"),
    "KB": KB_ROLE,
}

# (role, action, resource, kỳ vọng: True = phải được, False = phải bị chặn)
MATRIX = [
    ("runtime", "bedrock:InvokeModel", "model", True),
    ("runtime", "bedrock-agentcore:InvokeGateway", "gateway", True),
    ("runtime", "bedrock:InvokeModel", "model_other", False),
    ("runtime", "bedrock-agentcore:InvokeGateway", "gateway_other", False),
    ("runtime", "bedrock:Retrieve", "kb", False),
    ("runtime", "dynamodb:GetItem", "table", False),
    ("runtime", "lambda:InvokeFunction", "fn_order", False),
    ("runtime", "lambda:InvokeFunction", "fn_policy", False),
    ("gateway", "lambda:InvokeFunction", "fn_order", True),
    ("gateway", "lambda:InvokeFunction", "fn_policy", True),
    ("gateway", "lambda:InvokeFunction", "fn_other", False),
    ("gateway", "dynamodb:GetItem", "table", False),
    ("gateway", "bedrock:Retrieve", "kb", False),
    ("lambda get_order", "dynamodb:GetItem", "table", True),
    ("lambda get_order", "dynamodb:PutItem", "table", False),
    ("lambda get_order", "dynamodb:Scan", "table", False),
    ("lambda get_order", "dynamodb:Query", "table", False),
    ("lambda get_order", "dynamodb:GetItem", "table_other", False),
    ("lambda get_order", "bedrock:Retrieve", "kb", False),
    ("lambda search_policy", "bedrock:Retrieve", "kb", True),
    ("lambda search_policy", "bedrock:Retrieve", "kb_other", False),
    ("lambda search_policy", "dynamodb:GetItem", "table", False),
    ("lambda search_policy", "bedrock:InvokeModel", "model", False),
    ("KB", "s3:GetObject", "bucket_obj", True),
    ("KB", "s3:PutObject", "bucket_obj", False),
    ("KB", "s3:GetObject", "bucket_other_obj", False),
]



def main() -> int:
    bad = 0
    arns = {}

    print("═══ 1. Bản đồ quyền + 2. Access Analyzer ═══")
    for label, role in ROLES.items():
        info = iam.get_role(RoleName=role)["Role"]
        arns[label] = info["Arn"]
        trust = info["AssumeRolePolicyDocument"]
        print(f"\n▶ {label}: {role}")
        for s in trust["Statement"]:
            print(f"   trust  {mask(s['Principal'])}  điều kiện {mask(s.get('Condition', {}))}")
        for p in trust_problems(trust):
            print(f"   ❌ trust: {p}")
            bad += 1
        findings = [("trust", f) for f in validate(trust, "RESOURCE_POLICY", "AWS::IAM::AssumeRolePolicyDocument")]
        for name, doc in permission_policies(role):
            for s in doc["Statement"]:
                print(f"   allow  {s.get('Sid', '-'):<28} {mask(s['Action'])}  →  {mask(s['Resource'])}")
            findings += [(name, f) for f in validate(doc, "IDENTITY_POLICY")]
        for where, f in findings:
            serious = f["findingType"] in ("ERROR", "SECURITY_WARNING")
            bad += serious
            print(f"   {'❌' if serious else 'ℹ️ '} analyzer[{where}] {f['findingType']} {f['issueCode']}")
        if not findings:
            print("   ✅ Access Analyzer: không có finding")

    print("\n═══ 3. Ma trận simulate (✅ = đúng kỳ vọng) ═══")
    ok = 0
    for label, action, res, want in MATRIX:
        decision = simulate(arns[label], action, ARN[res])
        good = (decision == "allowed") == want
        ok += good
        bad += not good
        sign = "ĐƯỢC" if want else "CHẶN"
        print(f"   {'✅' if good else '❌'} {label:<21} phải {sign}  {action:<34} {res:<17} → {decision}")
    print(f"\nMa trận: {ok}/{len(MATRIX)} đúng kỳ vọng · tổng vấn đề: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
