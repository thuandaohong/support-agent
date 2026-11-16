#!/usr/bin/env bash
# Bước 3a (Day 60): service role + AgentCore Gateway (MCP server).
#   role    → CHỈ bedrock-agentcore của gateway tên này được mượn; CHỈ được gọi 2 Lambda tool
#             (get_order, search_policy — liệt kê từng ARN, không wildcard)
#   gateway → protocol MCP, inbound AWS_IAM: người gọi phải ký SigV4 + có bedrock-agentcore:InvokeGateway
# Chạy lại được: role cập nhật policy; gateway đã có thì giữ nguyên, chỉ in URL.
source "$(dirname "$0")/_env.sh"

TRUST="$(render "$HERE/gateway-trust-policy.json.tpl")"
PERMS="$(render "$HERE/gateway-permissions-policy.json.tpl")"
python3 -m json.tool "$TRUST" >/dev/null && python3 -m json.tool "$PERMS" >/dev/null
ensure_role "$GATEWAY_ROLE" "$TRUST" "$PERMS" "Service role cho AgentCore Gateway $GATEWAY_NAME"

ID="$(gateway_id)"
if [[ -n "$ID" ]]; then
  echo "Gateway $GATEWAY_NAME đã có (id $ID)"
else
  echo "Tạo Gateway $GATEWAY_NAME (MCP, inbound AWS_IAM)"
  # Role vừa tạo cần vài giây mới mượn được → thử lại tối đa ~60s khi lỗi nhắc tới role
  for i in $(seq 1 6); do
    if ID="$(aws bedrock-agentcore-control create-gateway --name "$GATEWAY_NAME" \
          --description "MCP tools cho support-agent (get_order)" \
          --role-arn "$(role_arn "$GATEWAY_ROLE")" \
          --protocol-type MCP --authorizer-type AWS_IAM \
          --tags project=support-agent \
          --query gatewayId --output text 2>"$TMP_DIR/err")"; then
      break
    fi
    grep -qi "role" "$TMP_DIR/err" || { cat "$TMP_DIR/err" >&2; exit 1; }
    [[ $i -eq 6 ]] && { cat "$TMP_DIR/err" >&2; exit 1; }
    echo "  role chưa lan tỏa, thử lại sau 10s…"; sleep 10
  done
  echo "  id: $ID"
fi

wait_status gateway aws bedrock-agentcore-control get-gateway --gateway-identifier "$ID"
echo "Xong. MCP endpoint: $(aws bedrock-agentcore-control get-gateway --gateway-identifier "$ID" --query gatewayUrl --output text)"
