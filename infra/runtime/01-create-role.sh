#!/usr/bin/env bash
# Bước 2 (day59-runtime-deploy.md): tạo / cập nhật IAM execution role cho AgentCore Runtime.
#   trust policy       → CHỈ Runtime tên $RUNTIME_NAME trong account này được mượn role (SourceArn
#                        runtime/<tên>-*, chống confused deputy — Day 63)
#   permissions policy → ECR pull (1 repo), log, X-Ray, InvokeModel (1 model)
#                        + tra đơn: GetItem 1 bảng (ORDER_BACKEND=direct) · tra chính sách: Retrieve 1 KB
#                        (POLICY_BACKEND=direct) · InvokeGateway 1 gateway (khi có tool đi Gateway)
# Chạy lại được: role đã có thì cập nhật trust + policy (put-role-policy ghi đè).
source "$(dirname "$0")/_env.sh"

TRUST="$(render "$HERE/trust-policy.json.tpl")"
PERMS="$(render "$HERE/permissions-policy.json.tpl")"
# Mỗi tool chỉ giữ quyền của đường đang dùng (Day 60–61):
#   ORDER_BACKEND=direct   → GetItem bảng đơn     · gateway → bỏ GetItem
#   POLICY_BACKEND=direct  → Retrieve KB          · gateway → bỏ Retrieve
#   cả hai tool direct     → bỏ InvokeGateway (ARN ".../gateway/" rỗng cũng vô nghĩa)
# Cả hai qua Gateway → role chỉ còn InvokeModel + InvokeGateway: container không tự đọc dữ liệu nào.
python3 - "$PERMS" "$ORDER_BACKEND" "$POLICY_BACKEND" "$USE_GATEWAY" <<'PY'
import json, sys
path, order, policy, use_gateway = sys.argv[1:]
drop = set()
if order == "gateway":
    drop.add("AppOrdersTable")
if policy == "gateway":
    drop.add("AppPolicyKB")
if use_gateway == "no":
    drop.add("AppGatewayInvoke")
doc = json.load(open(path))
doc["Statement"] = [s for s in doc["Statement"] if s["Sid"] not in drop]
json.dump(doc, open(path, "w"), indent=2)
PY
python3 -m json.tool "$TRUST" >/dev/null && python3 -m json.tool "$PERMS" >/dev/null   # JSON hợp lệ trước khi gửi

if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  echo "Role $ROLE_NAME đã có → cập nhật trust policy"
  aws iam update-assume-role-policy --role-name "$ROLE_NAME" --policy-document "file://$TRUST"
else
  echo "Tạo role $ROLE_NAME"
  aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document "file://$TRUST" \
    --description "Execution role cho AgentCore Runtime $RUNTIME_NAME" \
    --tags Key=project,Value=support-agent --query Role.Arn --output text
fi

echo "Gắn inline policy ${ROLE_NAME}-perms"
aws iam put-role-policy --role-name "$ROLE_NAME" \
  --policy-name "${ROLE_NAME}-perms" --policy-document "file://$PERMS"

echo "Xong: $(role_arn)"
