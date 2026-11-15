#!/usr/bin/env bash
# Bước 3: tạo AgentCore Runtime trỏ tới image ECR, gắn execution role, tiêm biến môi trường; chờ READY.
# Runtime đã có → không tạo lại, dùng 05-update-image.sh.
source "$(dirname "$0")/_env.sh"

if [[ -n "$(runtime_id)" ]]; then
  echo "Runtime $RUNTIME_NAME đã có (id $(runtime_id)) → dùng 05-update-image.sh để đổi image/cấu hình" >&2
  exit 1
fi
aws ecr describe-images --repository-name "$ECR_REPO" --image-ids "imageTag=$IMAGE_TAG" >/dev/null \
  || { echo "Không thấy image $IMAGE_URI trên ECR" >&2; exit 1; }

echo "Tạo Runtime $RUNTIME_NAME ← $IMAGE_URI"
ID="$(aws bedrock-agentcore-control create-agent-runtime \
  --agent-runtime-name "$RUNTIME_NAME" \
  --description "support-agent (LangGraph) image $IMAGE_TAG" \
  --agent-runtime-artifact "$(artifact_json)" \
  --role-arn "$(role_arn)" \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --lifecycle-configuration "$(lifecycle_json)" \
  --environment-variables "$(env_vars_json)" \
  --tags project=support-agent \
  --query agentRuntimeId --output text)"
echo "  id: $ID"

wait_ready "$ID"
echo "Xong: $(runtime_arn "$ID")"
