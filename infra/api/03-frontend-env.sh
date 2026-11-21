#!/usr/bin/env bash
# Bước 5 (Day 64): sinh frontend/.env.local cho Vite — URL HTTP API + pool id + client id.
#   Không phải bí mật (frontend nào cũng lộ các giá trị này cho trình duyệt), nhưng repo public
#   không commit id tài nguyên → tra theo tên lúc chạy, file nằm trong .gitignore.
# Chạy lại được: ghi đè .env.local. Sau đó: cd frontend && npm run dev
source "$(dirname "$0")/_env.sh"

POOL="$(pool_id)"; [[ -n "$POOL" ]] || { echo "Chưa có user pool $POOL_NAME (infra/auth)" >&2; exit 1; }
CLIENT="$(client_id "$POOL")"; [[ -n "$CLIENT" ]] || { echo "Chưa có app client $CLIENT_NAME" >&2; exit 1; }
API="$(api_id)"; [[ -n "$API" ]] || { echo "Chưa có HTTP API $API_NAME — Terraform tạo (infra/terraform, modules/web_api)" >&2; exit 1; }
URL="$(aws apigatewayv2 get-api --api-id "$API" --query ApiEndpoint --output text)"

OUT="$REPO/frontend/.env.local"
cat > "$OUT" <<ENV
# Sinh bởi infra/api/03-frontend-env.sh — không commit, không sửa tay
VITE_API_URL=$URL
VITE_USER_POOL_ID=$POOL
VITE_USER_POOL_CLIENT_ID=$CLIENT
ENV
echo "Đã ghi frontend/.env.local (API $API_NAME, pool $POOL_NAME, client $CLIENT_NAME)"
echo "Origin được CORS cho phép: $ALLOWED_ORIGIN → chạy: cd frontend && npm run dev"
