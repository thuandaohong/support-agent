#!/usr/bin/env bash
# Bước 3 (Day 64): HTTP API $API_NAME — cổng web vào agent. Thứ tự một request đi qua:
#   CORS       → chỉ origin $ALLOWED_ORIGIN, POST, header authorization + content-type (bảo vệ
#                TRÌNH DUYỆT của người dùng; curl bỏ qua CORS nên vẫn cần authorizer)
#   throttle   → stage $default: $THROTTLE_RATE req/s, burst $THROTTLE_BURST → 429 (cộng chung mọi
#                người dùng — HTTP API không có usage plan theo người)
#   authorizer → JWT: iss = pool Cognito, audience = app client $CLIENT_NAME, chữ ký RS256 + exp → 401
#   route      → POST /chat BẮT BUỘC scope aws.cognito.signin.user.admin: JWT authorizer không
#                phân biệt access / ID token (AWS docs); chỉ access token có scope này → ID token 403
#   integration→ Bridge Lambda, payload 2.0 (claims ở requestContext.authorizer.jwt.claims), 29 s
#   access log → CloudWatch: requestId, status, latency, lỗi authorizer — KHÔNG body, KHÔNG token
#   permission → apigateway.amazonaws.com chỉ được gọi Lambda từ ĐÚNG route này của API này
# Chạy lại được: mọi thứ tra theo tên; đã có thì cập nhật cấu hình.
source "$(dirname "$0")/_env.sh"

POOL="$(pool_id)"; [[ -n "$POOL" ]] || { echo "Chưa có user pool $POOL_NAME (infra/auth)" >&2; exit 1; }
CLIENT="$(client_id "$POOL")"; [[ -n "$CLIENT" ]] || { echo "Chưa có app client $CLIENT_NAME" >&2; exit 1; }
ISSUER="https://cognito-idp.$AWS_REGION.amazonaws.com/$POOL"
LAMBDA_ARN="$(aws lambda get-function --function-name "$BRIDGE_NAME" --query Configuration.FunctionArn --output text)"
SCOPE="aws.cognito.signin.user.admin"
AUTHORIZER_NAME="cognito-$CLIENT_NAME"

CORS="$(python3 -c 'import json, os; print(json.dumps({"AllowOrigins": [os.environ["ALLOWED_ORIGIN"]],
  "AllowMethods": ["POST"], "AllowHeaders": ["authorization", "content-type"], "MaxAge": 600}))')"

# ── 1. API
API="$(api_id)"
if [[ -n "$API" ]]; then
  echo "HTTP API $API_NAME đã có → cập nhật CORS"
  aws apigatewayv2 update-api --api-id "$API" --cors-configuration "$CORS" >/dev/null
else
  echo "Tạo HTTP API $API_NAME"
  API="$(aws apigatewayv2 create-api --name "$API_NAME" --protocol-type HTTP \
    --cors-configuration "$CORS" --tags project=support-agent --query ApiId --output text)"
fi

# ── 2. JWT authorizer (Cognito)
JWT="$(ISSUER="$ISSUER" CLIENT="$CLIENT" python3 -c 'import json, os
print(json.dumps({"Issuer": os.environ["ISSUER"], "Audience": [os.environ["CLIENT"]]}))')"
AUTH_ID="$(aws apigatewayv2 get-authorizers --api-id "$API" \
  --query "Items[?Name=='$AUTHORIZER_NAME'].AuthorizerId | [0]" --output text)"
if [[ "$AUTH_ID" != "None" && -n "$AUTH_ID" ]]; then
  aws apigatewayv2 update-authorizer --api-id "$API" --authorizer-id "$AUTH_ID" \
    --identity-source '$request.header.Authorization' --jwt-configuration "$JWT" >/dev/null
else
  AUTH_ID="$(aws apigatewayv2 create-authorizer --api-id "$API" --name "$AUTHORIZER_NAME" \
    --authorizer-type JWT --identity-source '$request.header.Authorization' \
    --jwt-configuration "$JWT" --query AuthorizerId --output text)"
fi
echo "JWT authorizer $AUTHORIZER_NAME (iss = pool $POOL_NAME, audience = $CLIENT_NAME)"

# ── 3. Integration → Bridge Lambda
INT_ID="$(aws apigatewayv2 get-integrations --api-id "$API" \
  --query "Items[?IntegrationUri=='$LAMBDA_ARN'].IntegrationId | [0]" --output text)"
INT_CFG=(--payload-format-version 2.0 --timeout-in-millis 29000)
if [[ "$INT_ID" != "None" && -n "$INT_ID" ]]; then
  aws apigatewayv2 update-integration --api-id "$API" --integration-id "$INT_ID" "${INT_CFG[@]}" >/dev/null
else
  INT_ID="$(aws apigatewayv2 create-integration --api-id "$API" --integration-type AWS_PROXY \
    --integration-uri "$LAMBDA_ARN" "${INT_CFG[@]}" --query IntegrationId --output text)"
fi

# ── 4. Route POST /chat — bắt buộc JWT + scope của access token
ROUTE_CFG=(--target "integrations/$INT_ID" --authorization-type JWT --authorizer-id "$AUTH_ID"
           --authorization-scopes "$SCOPE")
ROUTE_ID="$(aws apigatewayv2 get-routes --api-id "$API" \
  --query "Items[?RouteKey=='POST /chat'].RouteId | [0]" --output text)"
if [[ "$ROUTE_ID" != "None" && -n "$ROUTE_ID" ]]; then
  aws apigatewayv2 update-route --api-id "$API" --route-id "$ROUTE_ID" "${ROUTE_CFG[@]}" >/dev/null
else
  aws apigatewayv2 create-route --api-id "$API" --route-key "POST /chat" "${ROUTE_CFG[@]}" >/dev/null
fi
echo "Route POST /chat → $BRIDGE_NAME (JWT + scope $SCOPE)"

# ── 5. Access log + stage $default (auto-deploy, throttle)
LOG_GROUP="/aws/apigateway/$API_NAME"
if [[ -z "$(aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" \
            --query "logGroups[?logGroupName=='$LOG_GROUP'].logGroupName" --output text)" ]]; then
  aws logs create-log-group --log-group-name "$LOG_GROUP" --tags project=support-agent
fi
aws logs put-retention-policy --log-group-name "$LOG_GROUP" --retention-in-days "${LOG_RETENTION_DAYS:-14}"
LOG_ARN="arn:aws:logs:$AWS_REGION:$ACCOUNT_ID:log-group:$LOG_GROUP"
# Chỉ metadata: không body, không token, không claims (username/sub)
ACCESS_LOG="$(LOG_ARN="$LOG_ARN" python3 -c 'import json, os
fmt = json.dumps({"requestId": "$context.requestId", "time": "$context.requestTime",
                  "route": "$context.routeKey", "status": "$context.status",
                  "latencyMs": "$context.responseLatency", "integrationStatus": "$context.integrationStatus",
                  "integrationMs": "$context.integrationLatency", "authError": "$context.authorizer.error",
                  "error": "$context.error.message"})
print(json.dumps({"DestinationArn": os.environ["LOG_ARN"], "Format": fmt}))')"
THROTTLE="ThrottlingRateLimit=$THROTTLE_RATE,ThrottlingBurstLimit=$THROTTLE_BURST"
if aws apigatewayv2 get-stage --api-id "$API" --stage-name '$default' >/dev/null 2>&1; then
  aws apigatewayv2 update-stage --api-id "$API" --stage-name '$default' --auto-deploy \
    --default-route-settings "$THROTTLE" --access-log-settings "$ACCESS_LOG" >/dev/null
else
  aws apigatewayv2 create-stage --api-id "$API" --stage-name '$default' --auto-deploy \
    --default-route-settings "$THROTTLE" --access-log-settings "$ACCESS_LOG" \
    --tags project=support-agent >/dev/null
fi
echo "Stage \$default: throttle $THROTTLE_RATE req/s burst $THROTTLE_BURST, access log $LOG_GROUP"

# ── 6. Quyền gọi Lambda: chỉ từ route POST /chat của API này (xoá statement cũ rồi thêm lại)
SID="apigw-$API_NAME-post-chat"
aws lambda remove-permission --function-name "$BRIDGE_NAME" --statement-id "$SID" >/dev/null 2>&1 || true
aws lambda add-permission --function-name "$BRIDGE_NAME" --statement-id "$SID" \
  --action lambda:InvokeFunction --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$ACCOUNT_ID:$API/*/POST/chat" \
  --source-account "$ACCOUNT_ID" >/dev/null
echo "Lambda permission: chỉ $API_NAME POST /chat"

echo "Xong. Endpoint: $(aws apigatewayv2 get-api --api-id "$API" --query ApiEndpoint --output text)/chat"
