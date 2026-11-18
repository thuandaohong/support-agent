#!/usr/bin/env bash
# Day 65 — tra id ngẫu nhiên của resource đang chạy THEO TÊN (giống các _env.sh cũ) và ghi ra
# imports.auto.tfvars.json (gitignore). imports.tf đọc var.import_ids → repo public không chứa id.
# Chạy ở máy trước `terraform plan`, và trong CI trước plan/apply. Chỉ gọi API đọc (List/Get).
# Xoá file này cùng imports.tf sau khi import xong.
set -euo pipefail
export AWS_PAGER=""
export AWS_REGION="${AWS_REGION:-us-east-1}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/imports.auto.tfvars.json"

# Tên lấy từ terraform.tfvars (một nguồn duy nhất)
tfvar() { sed -nE "s/^$1[[:space:]]*=[[:space:]]*\"([^\"]*)\".*/\1/p" "$HERE/terraform.tfvars"; }
KB_NAME=$(tfvar kb_name); GATEWAY=$(tfvar gateway_name); RUNTIME=$(tfvar runtime_name)
POOL=$(tfvar pool_name); CLIENT=$(tfvar client_name); API=$(tfvar api_name)

need() { [[ -n "$2" && "$2" != None ]] || { echo "Không tra được $1" >&2; exit 1; }; printf '%s' "$2"; }

kb=$(need "KB $KB_NAME" "$(aws bedrock-agent list-knowledge-bases \
  --query "knowledgeBaseSummaries[?name=='$KB_NAME'].knowledgeBaseId | [0]" --output text)")
kb_ds=$(need "data source của KB" "$(aws bedrock-agent list-data-sources --knowledge-base-id "$kb" \
  --query 'dataSourceSummaries[0].dataSourceId' --output text)")
gw=$(need "Gateway $GATEWAY" "$(aws bedrock-agentcore-control list-gateways \
  --query "items[?name=='$GATEWAY'].gatewayId | [0]" --output text)")
target() { need "target $1" "$(aws bedrock-agentcore-control list-gateway-targets --gateway-identifier "$gw" \
  --query "items[?name=='$1'].targetId | [0]" --output text)"; }
t_orders=$(target orders); t_policies=$(target policies)
rt=$(need "Runtime $RUNTIME" "$(aws bedrock-agentcore-control list-agent-runtimes \
  --query "agentRuntimes[?agentRuntimeName=='$RUNTIME'].agentRuntimeId | [0]" --output text)")
pool=$(need "pool $POOL" "$(aws cognito-idp list-user-pools --max-results 60 \
  --query "UserPools[?Name=='$POOL'].Id | [0]" --output text)")
client=$(need "client $CLIENT" "$(aws cognito-idp list-user-pool-clients --user-pool-id "$pool" \
  --query "UserPoolClients[?ClientName=='$CLIENT'].ClientId | [0]" --output text)")
api=$(need "API $API" "$(aws apigatewayv2 get-apis --query "Items[?Name=='$API'].ApiId | [0]" --output text)")
authorizer=$(need "authorizer" "$(aws apigatewayv2 get-authorizers --api-id "$api" --query 'Items[0].AuthorizerId' --output text)")
integration=$(need "integration" "$(aws apigatewayv2 get-integrations --api-id "$api" --query 'Items[0].IntegrationId' --output text)")
route=$(need "route POST /chat" "$(aws apigatewayv2 get-routes --api-id "$api" \
  --query "Items[?RouteKey=='POST /chat'].RouteId | [0]" --output text)")

python3 - "$OUT" <<EOF
import json, sys
ids = dict(kb="$kb", kb_ds="$kb_ds", gateway="$gw", target_orders="$t_orders", target_policies="$t_policies",
           runtime="$rt", pool="$pool", client="$client", api="$api", authorizer="$authorizer",
           integration="$integration", route="$route")
json.dump({"import_ids": ids}, open(sys.argv[1], "w"), indent=2)
EOF
echo "✅ $(basename "$OUT"): 12 id (không commit, đã gitignore)"
