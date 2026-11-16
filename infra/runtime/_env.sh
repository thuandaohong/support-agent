# shellcheck shell=bash
# Dùng chung cho các script infra/runtime/*.sh — nạp biến, kiểm thiếu, hàm tiện ích.
# Không chạy trực tiếp: các script khác `source` file này.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${RUNTIME_ENV:-$HERE/runtime.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Thiếu $ENV_FILE — chạy: cp $HERE/runtime.env.example $HERE/runtime.env rồi điền giá trị" >&2
  exit 1
fi
set -a; source "$ENV_FILE"; set +a

for v in AWS_REGION KB_ID ORDERS_TABLE MODEL_ID ECR_REPO IMAGE_TAG ROLE_NAME RUNTIME_NAME IDLE_TIMEOUT MAX_LIFETIME; do
  [[ -n "${!v:-}" ]] || { echo "Biến $v trống trong $ENV_FILE" >&2; exit 1; }
done
ORDER_BACKEND="${ORDER_BACKEND:-direct}"; POLICY_BACKEND="${POLICY_BACKEND:-direct}"
for b in ORDER_BACKEND POLICY_BACKEND; do
  [[ "${!b}" == direct || "${!b}" == gateway ]] || { echo "$b phải là direct hoặc gateway" >&2; exit 1; }
done
# USE_GATEWAY: có ít nhất một tool đi qua Gateway → cần tra Gateway + quyền InvokeGateway
USE_GATEWAY=no
[[ "$ORDER_BACKEND" == gateway || "$POLICY_BACKEND" == gateway ]] && USE_GATEWAY=yes
[[ "$USE_GATEWAY" == no || -n "${GATEWAY_NAME:-}" ]] \
  || { echo "ORDER_BACKEND / POLICY_BACKEND=gateway cần GATEWAY_NAME" >&2; exit 1; }
[[ "$RUNTIME_NAME" =~ ^[a-zA-Z][a-zA-Z0-9_]*$ ]] || { echo "RUNTIME_NAME chỉ được chữ, số, '_' (không '-')" >&2; exit 1; }
command -v envsubst >/dev/null || { echo "Cần envsubst (brew install gettext)" >&2; exit 1; }

export AWS_PAGER=""          # không mở less cho output CLI
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export ACCOUNT_ID
export IMAGE_URI="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG"

# Gateway (Day 60): tra id + URL theo tên mỗi lần chạy — Gateway tạo lại thì id đổi, file không phải sửa
GATEWAY_ID=""; GATEWAY_URL=""
if [[ "$USE_GATEWAY" == yes ]]; then
  GATEWAY_ID="$(aws bedrock-agentcore-control list-gateways \
        --query "items[?name=='$GATEWAY_NAME'].gatewayId | [0]" --output text)"
  [[ -n "$GATEWAY_ID" && "$GATEWAY_ID" != "None" ]] \
    || { echo "Không thấy Gateway $GATEWAY_NAME — chạy infra/gateway/03-gateway.sh" >&2; exit 1; }
  GATEWAY_URL="$(aws bedrock-agentcore-control get-gateway --gateway-identifier "$GATEWAY_ID" \
        --query gatewayUrl --output text)"
fi
export ORDER_BACKEND POLICY_BACKEND USE_GATEWAY GATEWAY_ID GATEWAY_URL

# Thư mục tạm cho policy đã render (có account ID / KB ID thật) — tự xoá khi script kết thúc
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# render <file.tpl> → in đường dẫn file JSON đã thay biến. Liệt kê rõ biến được thay để envsubst
# không đụng vào ký tự "$" nào khác.
render() {
  local out="$TMP_DIR/$(basename "${1%.tpl}")"
  envsubst '${ACCOUNT_ID} ${AWS_REGION} ${KB_ID} ${ORDERS_TABLE} ${MODEL_ID} ${ECR_REPO} ${GATEWAY_ID} ${RUNTIME_NAME}' < "$1" > "$out"
  echo "$out"
}

# runtime_id → id của Runtime tên $RUNTIME_NAME, rỗng nếu chưa có (tra theo tên, không lưu file trạng thái)
runtime_id() {
  local id
  id="$(aws bedrock-agentcore-control list-agent-runtimes \
        --query "agentRuntimes[?agentRuntimeName=='$RUNTIME_NAME'].agentRuntimeId | [0]" --output text)"
  [[ "$id" == "None" ]] && id=""
  echo "$id"
}

runtime_arn() {
  aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id "$1" --query agentRuntimeArn --output text
}

role_arn() {
  aws iam get-role --role-name "$ROLE_NAME" --query Role.Arn --output text
}

# Biến môi trường cho container (JSON). Không có .env trong image → cấu hình đến từ đây.
# AWS_REGION không cần: Runtime tự đặt.
env_vars_json() {
  python3 -c 'import json, os
print(json.dumps({
    "ROUTER_MODEL_ID": os.environ["MODEL_ID"],
    "WRITER_MODEL_ID": os.environ["MODEL_ID"],
    "AS_OF_DATE": os.environ.get("AS_OF_DATE", ""),
    "ORDER_BACKEND": os.environ["ORDER_BACKEND"],
    "POLICY_BACKEND": os.environ["POLICY_BACKEND"],
    # chỉ truyền biến của đường đang dùng: direct cần tên bảng / KB id, gateway cần URL
    **({"ORDERS_TABLE": os.environ["ORDERS_TABLE"]} if os.environ["ORDER_BACKEND"] == "direct" else {}),
    **({"POLICY_KB_ID": os.environ["KB_ID"]} if os.environ["POLICY_BACKEND"] == "direct" else {}),
    **({"GATEWAY_URL": os.environ["GATEWAY_URL"]} if os.environ["USE_GATEWAY"] == "yes" else {}),
}))'
}

artifact_json() {
  printf '{"containerConfiguration":{"containerUri":"%s"}}' "$IMAGE_URI"
}

lifecycle_json() {
  printf '{"idleRuntimeSessionTimeout":%s,"maxLifetime":%s}' "$IDLE_TIMEOUT" "$MAX_LIFETIME"
}

# wait_ready <id> — chờ Runtime READY (tối đa ~5 phút), in lý do nếu FAILED
wait_ready() {
  local status
  for _ in $(seq 1 30); do
    status="$(aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id "$1" --query status --output text)"
    echo "  status: $status"
    case "$status" in
      READY) return 0 ;;
      *FAILED*)
        aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id "$1" --query failureReason --output text >&2
        return 1 ;;
    esac
    sleep 10
  done
  echo "Quá 5 phút chưa READY" >&2
  return 1
}
