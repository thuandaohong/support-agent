#!/usr/bin/env bash
# Bước 3b (Day 60): nối Gateway → Lambda get_order bằng một target, kèm tool schema.
#   Tên tool agent thấy = "<TARGET_NAME>___get_order" (Gateway thêm tiền tố, Lambda tự cắt).
#   GATEWAY_IAM_ROLE → Gateway gọi Lambda bằng service role của nó (03-gateway.sh).
# Chạy lại được: target đã có thì cập nhật (đổi schema → chạy lại script này).
source "$(dirname "$0")/_env.sh"

GW="$(gateway_id)"; [[ -n "$GW" ]] || { echo "Chưa có Gateway $GATEWAY_NAME → chạy 03-gateway.sh" >&2; exit 1; }
LAMBDA_ARN="$(lambda_arn)"

# target-configuration: Lambda + schema inline lấy nguyên từ get_order.tool.json (một nguồn duy nhất)
CONFIG="$TMP_DIR/target.json"
ARN="$LAMBDA_ARN" SCHEMA="$HERE/get_order.tool.json" python3 -c 'import json, os
tool = json.load(open(os.environ["SCHEMA"], encoding="utf-8"))
print(json.dumps({"mcp": {"lambda": {"lambdaArn": os.environ["ARN"],
                                      "toolSchema": {"inlinePayload": [tool]}}}}, ensure_ascii=False))' > "$CONFIG"
CREDS='[{"credentialProviderType":"GATEWAY_IAM_ROLE"}]'

TID="$(target_id "$GW")"
if [[ -n "$TID" ]]; then
  echo "Target $TARGET_NAME đã có (id $TID) → cập nhật schema / Lambda"
  aws bedrock-agentcore-control update-gateway-target --gateway-identifier "$GW" --target-id "$TID" \
    --name "$TARGET_NAME" --description "Lambda $LAMBDA_NAME (get_order)" \
    --target-configuration "file://$CONFIG" --credential-provider-configurations "$CREDS" \
    --query status --output text
else
  echo "Tạo target $TARGET_NAME → $LAMBDA_NAME"
  TID="$(aws bedrock-agentcore-control create-gateway-target --gateway-identifier "$GW" \
    --name "$TARGET_NAME" --description "Lambda $LAMBDA_NAME (get_order)" \
    --target-configuration "file://$CONFIG" --credential-provider-configurations "$CREDS" \
    --query targetId --output text)"
  echo "  id: $TID"
fi

wait_status target aws bedrock-agentcore-control get-gateway-target --gateway-identifier "$GW" --target-id "$TID"
echo "Xong: tool ${TARGET_NAME}___get_order trên gateway $GW"
