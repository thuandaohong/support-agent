#!/usr/bin/env bash
# XOÁ HẲN Runtime + execution role. Không hoàn tác được → bắt gõ lại tên Runtime để xác nhận.
# ECR repo, DynamoDB, KB KHÔNG bị đụng tới.
source "$(dirname "$0")/_env.sh"

read -r -p "Gõ '$RUNTIME_NAME' để xoá Runtime + role $ROLE_NAME: " ans
[[ "$ans" == "$RUNTIME_NAME" ]] || { echo "Huỷ."; exit 1; }

ID="$(runtime_id)"
if [[ -n "$ID" ]]; then
  aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-id "$ID" >/dev/null
  echo "Đã yêu cầu xoá Runtime $ID"
fi
if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam delete-role-policy --role-name "$ROLE_NAME" --policy-name "${ROLE_NAME}-perms" || true
  aws iam delete-role --role-name "$ROLE_NAME"
  echo "Đã xoá role $ROLE_NAME"
fi
