#!/usr/bin/env bash
# Đổi Runtime sang image / cấu hình mới mà không xoá Runtime.
#   sửa IMAGE_TAG (hoặc biến khác) trong runtime.env → ./05-update-image.sh
# update-agent-runtime THAY TOÀN BỘ cấu hình → gửi lại đủ role, network, lifecycle, biến môi trường.
source "$(dirname "$0")/_env.sh"

ID="$(runtime_id)"; [[ -n "$ID" ]] || { echo "Chưa có Runtime $RUNTIME_NAME — chạy 02-create-runtime.sh" >&2; exit 1; }
aws ecr describe-images --repository-name "$ECR_REPO" --image-ids "imageTag=$IMAGE_TAG" >/dev/null \
  || { echo "Không thấy image $IMAGE_URI trên ECR" >&2; exit 1; }

echo "Cập nhật Runtime $ID ← $IMAGE_URI"
aws bedrock-agentcore-control update-agent-runtime --agent-runtime-id "$ID" \
  --description "support-agent (LangGraph) image $IMAGE_TAG" \
  --agent-runtime-artifact "$(artifact_json)" \
  --role-arn "$(role_arn)" \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --lifecycle-configuration "$(lifecycle_json)" \
  --environment-variables "$(env_vars_json)" \
  --query agentRuntimeVersion --output text
wait_ready "$ID"
