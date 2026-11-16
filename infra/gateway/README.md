# infra/gateway — tool get_order qua AgentCore Gateway (tạo bằng CLI, Day 60)

Đưa tool tra đơn ra khỏi container agent: agent gọi **AgentCore Gateway** (MCP server do AWS quản
lý) → Gateway gọi **Lambda `support-get-order`** → Lambda đọc DynamoDB. Role Runtime không còn quyền
đọc bảng đơn hàng — chỉ còn quyền "nhờ Gateway".

Giá trị thật nằm trong `gateway.env` — **không commit** (`.gitignore`). Account ID, gateway id, URL
không ghi ở đâu cả: script tra theo tên mỗi lần chạy.

> Tạm thời bằng CLI như `infra/runtime`. **Ghi nợ:** khi Terraform hoá, `import` Lambda
> `support-get-order`, Gateway `support-gateway`, target `orders` và 2 role bên dưới.

## Cách dùng

```bash
cd support-agent
cp infra/gateway/gateway.env.example infra/gateway/gateway.env   # giá trị mẫu dùng được luôn
./infra/gateway/01-lambda.sh        # role Lambda + log group 14 ngày + Lambda (chạy lại = cập nhật code)
./infra/gateway/02-test-lambda.sh   # gọi Lambda trực tiếp, đóng vai Gateway (3 ca)
./infra/gateway/03-gateway.sh       # role Gateway + Gateway MCP (inbound AWS_IAM), chờ READY
./infra/gateway/04-target.sh        # target "orders" → Lambda + tool schema (chạy lại = cập nhật schema)
python scripts/mcp_call.py          # tools/list + 3 ca + ca thiếu customer_id qua Gateway thật
# nối agent: infra/runtime/runtime.env đặt ORDER_BACKEND=gateway → 01-create-role.sh → 05-update-image.sh
```

| File | Việc |
|---|---|
| `gateway.env.example` | Danh sách biến (mẫu, commit). Bản thật `gateway.env` không commit |
| `_env.sh` | Nạp + kiểm biến, render policy ra thư mục tạm (tự xoá), `ensure_role`, tra Lambda/Gateway/target theo tên, `wait_status` |
| `get_order.tool.json` | Tool schema (MCP `inputSchema`) — một nguồn duy nhất, test so với `handler.REQUIRED` |
| `lambda-*.json*` | Role Lambda: chỉ `lambda.amazonaws.com` mượn; chỉ `GetItem` 1 bảng + ghi log của chính nó |
| `gateway-*.json*` | Role Gateway: chỉ Gateway `support-gateway-*` của account này mượn; chỉ `InvokeFunction` 1 Lambda |
| `01-lambda.sh` … `04-target.sh` | Tạo / cập nhật, chạy lại được |
| `99-destroy.sh` | Xoá target → Gateway → Lambda → log group → 2 role (gõ lại tên để xác nhận). Không đụng DynamoDB / Runtime |

## Ba lớp quyền trên đường tra đơn

| Chặng | Ai ký | Quyền cần | Ở đâu |
|---|---|---|---|
| Runtime → Gateway | role `support-agent-runtime` (SigV4, service `bedrock-agentcore`) | `bedrock-agentcore:InvokeGateway` trên đúng 1 gateway | `infra/runtime/permissions-policy.json.tpl` (`AppGatewayInvoke`) |
| Gateway → Lambda | role `support-gateway` (target `GATEWAY_IAM_ROLE`) | `lambda:InvokeFunction` trên đúng 1 function | `gateway-permissions-policy.json.tpl` |
| Lambda → DynamoDB | role `support-get-order-lambda` | `dynamodb:GetItem` trên đúng 1 bảng | `lambda-permissions-policy.json.tpl` |

Cùng account → Lambda **không cần** resource policy (role của Gateway có quyền là đủ). Lambda không
có Function URL: chỉ gọi được qua API Invoke có IAM.

## Gateway hành xử thế nào (đo khi gọi thật, Day 60)

- `tools/list`, `tools/call` chạy **không cần `initialize`**, không có `Mcp-Session-Id` → mỗi request độc lập.
- Response là JSON thường (không SSE). Không ký SigV4 → HTTP 401 (JSON-RPC `-32001`).
- Tên tool = `<target>___<tool>` (`orders___get_order`). Gateway định tuyến theo tên này; Lambda nhận
  tên đầy đủ trong `context.client_context.custom["bedrockAgentCoreToolName"]` và tự cắt tiền tố.
- Gateway **tự kiểm `inputSchema`**: thiếu trường bắt buộc → `isError: true`, Lambda không bị gọi.
  Tool không tồn tại → JSON-RPC `-32602`.
- Lambda trả `{"error": ...}` thì Gateway vẫn báo `isError: false` → client phải tự đọc nội dung.
- Lambda warm 6–34 ms; cold start init ~0.4–0.5 s.

## Lưu ý vận hành

- Gateway hỏng (mạng, quyền, Lambda lỗi) → agent trả `order_lookup="error"`, câu cố định "hệ thống
  tra cứu đơn hàng đang bận", `error="order_unavailable"` — **không bao giờ** nói "không tìm thấy đơn".
- Đổi schema tool: sửa `get_order.tool.json` + `lambdas/get_order/handler.py` → `01-lambda.sh` → `04-target.sh`.
- Quay về đường cũ: `ORDER_BACKEND=direct` trong `runtime.env` → `01-create-role.sh` (cấp lại `GetItem`,
  bỏ `InvokeGateway`) → `05-update-image.sh`. Không cần build image mới.
