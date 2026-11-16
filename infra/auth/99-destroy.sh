#!/usr/bin/env bash
# XOÁ HẲN Cognito của infra/auth: app client → user pool (kéo theo mọi user) + test-users.env.
# Không hoàn tác được → bắt gõ lại tên pool để xác nhận. Runtime, Gateway, Lambda KHÔNG bị đụng tới
# (Runtime vẫn IAM — chỉ scripts/invoke_runtime.py --auth và Day 64 cần pool này).
source "$(dirname "$0")/_env.sh"

read -r -p "Gõ '$POOL_NAME' để xoá user pool + app client $CLIENT_NAME + mọi user: " ans
[[ "$ans" == "$POOL_NAME" ]] || { echo "Huỷ."; exit 1; }

POOL="$(pool_id)"
if [[ -n "$POOL" ]]; then
  CID="$(client_id "$POOL")"
  if [[ -n "$CID" ]]; then
    aws cognito-idp delete-user-pool-client --user-pool-id "$POOL" --client-id "$CID"
    echo "Đã xoá app client $CLIENT_NAME"
  fi
  aws cognito-idp delete-user-pool --user-pool-id "$POOL"
  echo "Đã xoá user pool $POOL_NAME"
fi
rm -f "$USERS_FILE" && echo "Đã xoá test-users.env"
