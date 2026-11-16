# shellcheck shell=bash
# Dùng chung cho các script infra/gateway/*.sh — nạp biến, kiểm thiếu, hàm tiện ích.
# Không chạy trực tiếp: các script khác `source` file này.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
ENV_FILE="${GATEWAY_ENV:-$HERE/gateway.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Thiếu $ENV_FILE — chạy: cp $HERE/gateway.env.example $HERE/gateway.env rồi kiểm giá trị" >&2
  exit 1
fi
set -a; source "$ENV_FILE"; set +a

for v in AWS_REGION ORDERS_TABLE LAMBDA_NAME LAMBDA_ROLE GATEWAY_NAME GATEWAY_ROLE TARGET_NAME \
         KB_NAME POLICY_LAMBDA_NAME POLICY_LAMBDA_ROLE POLICY_TARGET_NAME; do
  [[ -n "${!v:-}" ]] || { echo "Biến $v trống trong $ENV_FILE" >&2; exit 1; }
done
command -v envsubst >/dev/null || { echo "Cần envsubst (brew install gettext)" >&2; exit 1; }

export AWS_PAGER=""
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export ACCOUNT_ID

# KB chính sách (Day 61): tra id theo tên mỗi lần chạy — không lưu id vào file nào
KB_ID="$(aws bedrock-agent list-knowledge-bases \
      --query "knowledgeBaseSummaries[?name=='$KB_NAME'].knowledgeBaseId | [0]" --output text)"
[[ -n "$KB_ID" && "$KB_ID" != "None" ]] || { echo "Không thấy Knowledge Base $KB_NAME" >&2; exit 1; }
export KB_ID

# Thư mục tạm cho policy đã render (có account ID thật) + file zip — tự xoá khi script kết thúc
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# render <file.tpl> → in đường dẫn file JSON đã thay biến (chỉ thay đúng các biến liệt kê)
render() {
  local out="$TMP_DIR/$(basename "${1%.tpl}")"
  envsubst '${ACCOUNT_ID} ${AWS_REGION} ${ORDERS_TABLE} ${LAMBDA_NAME} ${GATEWAY_NAME} ${KB_ID} ${POLICY_LAMBDA_NAME}' < "$1" > "$out"
  echo "$out"
}

# ensure_role <tên> <trust.json> <perms.json> <mô tả> — tạo role hoặc cập nhật trust; ghi đè inline policy
ensure_role() {
  if aws iam get-role --role-name "$1" >/dev/null 2>&1; then
    echo "Role $1 đã có → cập nhật trust policy"
    aws iam update-assume-role-policy --role-name "$1" --policy-document "file://$2"
  else
    echo "Tạo role $1"
    aws iam create-role --role-name "$1" --assume-role-policy-document "file://$2" \
      --description "$4" --tags Key=project,Value=support-agent --query Role.Arn --output text
  fi
  aws iam put-role-policy --role-name "$1" --policy-name "${1}-perms" --policy-document "file://$3"
}

# lambda_arn [tên] — mặc định Lambda get_order
lambda_arn() {
  aws lambda get-function --function-name "${1:-$LAMBDA_NAME}" --query Configuration.FunctionArn --output text
}

role_arn() {
  aws iam get-role --role-name "$1" --query Role.Arn --output text
}

# gateway_id → id của Gateway tên $GATEWAY_NAME, rỗng nếu chưa có (tra theo tên, không lưu file trạng thái)
gateway_id() {
  local id
  id="$(aws bedrock-agentcore-control list-gateways \
        --query "items[?name=='$GATEWAY_NAME'].gatewayId | [0]" --output text)"
  [[ "$id" == "None" ]] && id=""
  echo "$id"
}

# target_id <gateway_id> [tên target] → id target (mặc định $TARGET_NAME), rỗng nếu chưa có
target_id() {
  local id
  id="$(aws bedrock-agentcore-control list-gateway-targets --gateway-identifier "$1" \
        --query "items[?name=='${2:-$TARGET_NAME}'].targetId | [0]" --output text)"
  [[ "$id" == "None" ]] && id=""
  echo "$id"
}

# wait_status <mô tả> <lệnh get…> — chờ READY (tối đa ~5 phút), in statusReasons nếu hỏng
wait_status() {
  local what="$1" status; shift
  for _ in $(seq 1 30); do
    status="$("$@" --query status --output text)"
    echo "  $what: $status"
    case "$status" in
      READY) return 0 ;;
      *FAILED*|*UNSUCCESSFUL*) "$@" --query statusReasons --output text >&2; return 1 ;;
    esac
    sleep 10
  done
  echo "Quá 5 phút chưa READY" >&2
  return 1
}

# deploy_lambda <tên> <role> <thư mục code> <perms.json.tpl> <biến môi trường> <mô tả>
#   role riêng (trust lambda.amazonaws.com) + log group tạo TRƯỚC với retention (role khỏi cần
#   logs:CreateLogGroup) + hàm python3.14 arm64. Chạy lại được: đã có thì cập nhật code + cấu hình.
#   <biến môi trường> dạng CLI: "Variables={KEY=value}"
deploy_lambda() {
  local name="$1" role="$2" src="$3" perms_tpl="$4" env="$5" desc="$6"
  local trust="$HERE/lambda-trust-policy.json" perms role_arn log_group zip i
  perms="$(render "$perms_tpl")"
  python3 -m json.tool "$trust" >/dev/null && python3 -m json.tool "$perms" >/dev/null
  ensure_role "$role" "$trust" "$perms" "Lambda $name ($desc)"
  role_arn="$(role_arn "$role")"

  log_group="/aws/lambda/$name"
  if [[ -z "$(aws logs describe-log-groups --log-group-name-prefix "$log_group" \
              --query "logGroups[?logGroupName=='$log_group'].logGroupName" --output text)" ]]; then
    aws logs create-log-group --log-group-name "$log_group" --tags project=support-agent
  fi
  aws logs put-retention-policy --log-group-name "$log_group" --retention-in-days "${LOG_RETENTION_DAYS:-14}"
  echo "Log group $log_group giữ ${LOG_RETENTION_DAYS:-14} ngày"

  # Gói chỉ handler.py (boto3 có sẵn trong runtime Lambda). -X: bỏ metadata → zip giống nhau mỗi lần build
  zip="$TMP_DIR/$name.zip"
  (cd "$src" && zip -qX "$zip" handler.py)

  # timeout 10s = timeout của mcp_client: Lambda chạy lâu hơn thì client đã bỏ cuộc rồi
  if aws lambda get-function --function-name "$name" >/dev/null 2>&1; then
    echo "Lambda $name đã có → cập nhật code"
    aws lambda update-function-code --function-name "$name" --zip-file "fileb://$zip" \
      --query LastUpdateStatus --output text
    aws lambda wait function-updated-v2 --function-name "$name"
    aws lambda update-function-configuration --function-name "$name" \
      --role "$role_arn" --timeout 10 --memory-size 256 \
      --environment "$env" --query LastUpdateStatus --output text
    aws lambda wait function-updated-v2 --function-name "$name"
  else
    echo "Tạo Lambda $name (python3.14, arm64)"
    # Role vừa tạo cần vài giây mới mượn được → thử lại tối đa ~60s
    for i in $(seq 1 6); do
      if aws lambda create-function --function-name "$name" \
           --runtime python3.14 --architectures arm64 \
           --handler handler.lambda_handler --zip-file "fileb://$zip" \
           --role "$role_arn" --timeout 10 --memory-size 256 \
           --environment "$env" --description "$desc (support-agent)" \
           --tags project=support-agent --query FunctionArn --output text 2>"$TMP_DIR/err"; then
        break
      fi
      grep -q "cannot be assumed" "$TMP_DIR/err" || { cat "$TMP_DIR/err" >&2; return 1; }
      [[ $i -eq 6 ]] && { echo "Role vẫn chưa mượn được sau 60s" >&2; return 1; }
      echo "  role chưa lan tỏa, thử lại sau 10s…"; sleep 10
    done
    aws lambda wait function-active-v2 --function-name "$name"
  fi
  echo "Xong: $(lambda_arn "$name")"
}

# lambda_tool_context <tên tool đầy đủ> → ClientContext base64 như Gateway gửi
#   (Python đọc ở context.client_context.custom["bedrockAgentCoreToolName"])
lambda_tool_context() {
  TOOL="$1" python3 -c 'import base64, json, os
print(base64.b64encode(json.dumps({"custom": {"bedrockAgentCoreToolName": os.environ["TOOL"]}}).encode()).decode())'
}

# ensure_target <gateway_id> <tên target> <tên Lambda> <tool schema .json> — tạo hoặc cập nhật target
#   Lambda + schema inline (lấy nguyên file .json, một nguồn duy nhất) + GATEWAY_IAM_ROLE (Gateway gọi
#   Lambda bằng service role của nó). Tên tool agent thấy = "<tên target>___<name trong schema>".
ensure_target() {
  local gw="$1" target="$2" fn="$3" schema="$4" config="$TMP_DIR/target-$2.json" tid
  local creds='[{"credentialProviderType":"GATEWAY_IAM_ROLE"}]'
  ARN="$(lambda_arn "$fn")" SCHEMA="$schema" python3 -c 'import json, os
tool = json.load(open(os.environ["SCHEMA"], encoding="utf-8"))
print(json.dumps({"mcp": {"lambda": {"lambdaArn": os.environ["ARN"],
                                      "toolSchema": {"inlinePayload": [tool]}}}}, ensure_ascii=False))' > "$config"

  tid="$(target_id "$gw" "$target")"
  if [[ -n "$tid" ]]; then
    echo "Target $target đã có (id $tid) → cập nhật schema / Lambda"
    aws bedrock-agentcore-control update-gateway-target --gateway-identifier "$gw" --target-id "$tid" \
      --name "$target" --description "Lambda $fn" \
      --target-configuration "file://$config" --credential-provider-configurations "$creds" \
      --query status --output text
  else
    echo "Tạo target $target → $fn"
    tid="$(aws bedrock-agentcore-control create-gateway-target --gateway-identifier "$gw" \
      --name "$target" --description "Lambda $fn" \
      --target-configuration "file://$config" --credential-provider-configurations "$creds" \
      --query targetId --output text)"
    echo "  id: $tid"
  fi
  wait_status "target $target" aws bedrock-agentcore-control get-gateway-target --gateway-identifier "$gw" --target-id "$tid"
}
