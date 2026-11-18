# infra/gateway — tool get_order + search_policy qua AgentCore Gateway (tạo bằng CLI, Day 60–61)

> ⚠️ **Day 65:** resource ở đây nay do Terraform quản ([infra/terraform/](../terraform/README.md)). **Không chạy script tạo / sửa / `99-destroy.sh`** nữa (sẽ lệch state; xoá sau khi apply). Script chỉ đọc / vận hành (invoke, logs, test…) vẫn dùng được.

Đưa hai tool ra khỏi container agent: agent gọi **AgentCore Gateway** (MCP server do AWS quản lý)
→ Gateway gọi Lambda theo tên tool:

| Tool agent thấy | Target | Lambda | Đọc gì |
|---|---|---|---|
| `orders___get_order` | `orders` | `support-get-order` | DynamoDB `support-orders` (GetItem) |
| `policies___search_policy` | `policies` | `support-search-policy` | Knowledge Base `support-policy-kb` (Retrieve) |

Role Runtime không còn quyền đọc dữ liệu nào: chỉ `InvokeModel` + "nhờ Gateway" (`InvokeGateway`).

Giá trị thật nằm trong `gateway.env` — **không commit** (`.gitignore`). Account ID, gateway id, URL,
KB id không ghi ở đâu cả: script tra theo tên mỗi lần chạy (`GATEWAY_NAME`, `KB_NAME`).

> Tạm thời bằng CLI như `infra/runtime`. **Ghi nợ:** khi Terraform hoá, `import` Lambda
> `support-get-order`, `support-search-policy`, Gateway `support-gateway`, target `orders`, `policies`
> và 3 role bên dưới.

## Cách dùng

```bash
cd support-agent
cp infra/gateway/gateway.env.example infra/gateway/gateway.env   # giá trị mẫu dùng được luôn
./infra/gateway/01-lambda.sh        # role Lambda + log group 14 ngày + Lambda (chạy lại = cập nhật code)
./infra/gateway/02-test-lambda.sh   # gọi Lambda trực tiếp, đóng vai Gateway (3 ca)
./infra/gateway/03-gateway.sh       # role Gateway + Gateway MCP (inbound AWS_IAM), chờ READY
./infra/gateway/04-target.sh        # target "orders" → Lambda + tool schema (chạy lại = cập nhật schema)
./infra/gateway/05-policy-lambda.sh # role + log group + Lambda search_policy (Day 61)
./infra/gateway/06-test-policy-lambda.sh   # gọi Lambda trực tiếp, đóng vai Gateway (3 ca)
./infra/gateway/03-gateway.sh       # chạy LẠI: role Gateway được gọi thêm Lambda search_policy
./infra/gateway/07-policy-target.sh # target "policies" → Lambda search_policy
python scripts/mcp_call.py          # tools/list + ca chuẩn của 2 tool + ca input sai, qua Gateway thật
# nối agent: infra/runtime/runtime.env đặt ORDER_BACKEND / POLICY_BACKEND=gateway
#            → 01-create-role.sh → 05-update-image.sh
```

| File | Việc |
|---|---|
| `gateway.env.example` | Danh sách biến (mẫu, commit). Bản thật `gateway.env` không commit |
| `_env.sh` | Nạp + kiểm biến, tra KB id theo tên, render policy ra thư mục tạm (tự xoá), `ensure_role`, `deploy_lambda`, `ensure_target`, tra Lambda/Gateway/target theo tên, `wait_status` |
| `get_order.tool.json`, `search_policy.tool.json` | Tool schema (MCP `inputSchema`) — một nguồn duy nhất, test so với `handler.REQUIRED` |
| `lambda-trust-policy.json` | Chỉ `lambda.amazonaws.com` mượn (dùng chung cho 2 role Lambda) |
| `lambda-permissions-policy.json.tpl` | Lambda get_order: chỉ `GetItem` 1 bảng + log của chính nó |
| `lambda-policy-permissions-policy.json.tpl` | Lambda search_policy: chỉ `Retrieve` 1 KB + log của chính nó |
| `gateway-*.json*` | Role Gateway: chỉ Gateway `support-gateway-*` của account này mượn; chỉ `InvokeFunction` đúng 2 Lambda (liệt kê ARN, không wildcard) |
| `01-lambda.sh` … `07-policy-target.sh` | Tạo / cập nhật, chạy lại được |
| `99-destroy.sh` | Xoá 2 target → Gateway → 2 Lambda → 2 log group → 3 role (gõ lại tên để xác nhận). Không đụng DynamoDB / KB / Runtime |

## Các lớp quyền trên đường gọi tool

| Chặng | Ai ký | Quyền cần | Ở đâu |
|---|---|---|---|
| Runtime → Gateway | role `support-agent-runtime` (SigV4, service `bedrock-agentcore`) | `bedrock-agentcore:InvokeGateway` trên đúng 1 gateway | `infra/runtime/permissions-policy.json.tpl` (`AppGatewayInvoke`) |
| Gateway → Lambda | role `support-gateway` (target `GATEWAY_IAM_ROLE`) | `lambda:InvokeFunction` trên đúng 2 function | `gateway-permissions-policy.json.tpl` |
| Lambda get_order → DynamoDB | role `support-get-order-lambda` | `dynamodb:GetItem` trên đúng 1 bảng | `lambda-permissions-policy.json.tpl` |
| Lambda search_policy → KB | role `support-search-policy-lambda` | `bedrock:Retrieve` trên đúng 1 KB | `lambda-policy-permissions-policy.json.tpl` |

Cùng account → Lambda **không cần** resource policy (role của Gateway có quyền là đủ). Lambda không
có Function URL: chỉ gọi được qua API Invoke có IAM.

## Gateway hành xử thế nào (đo khi gọi thật, Day 60–61)

- `tools/list`, `tools/call` chạy **không cần `initialize`**, không có `Mcp-Session-Id` → mỗi request độc lập.
- Response là JSON thường (không SSE). Không ký SigV4 → HTTP 401 (JSON-RPC `-32001`).
- Tên tool = `<target>___<tool>` (`orders___get_order`). Gateway định tuyến theo tên này; Lambda nhận
  tên đầy đủ trong `context.client_context.custom["bedrockAgentCoreToolName"]` và tự cắt tiền tố.
- Gateway **tự kiểm `inputSchema`**: thiếu trường bắt buộc hoặc sai kiểu (`top_k: "3"`) → `isError: true`,
  Lambda không bị gọi. Tool không tồn tại → JSON-RPC `-32602`.
- Tool schema của Gateway **chỉ nhận** `type`, `properties`, `required`, `items`, `description`.
  `maxLength` / `minimum` / `maximum` bị từ chối lúc tạo target → giới hạn độ dài / khoảng giá trị
  ghi bằng chữ trong `description` và **Lambda tự kiểm** (`tool_invalid_input`).
- Response 2.5 KB (3 đoạn chính sách) vẫn JSON thường, không bị cắt.
- Lambda trả `{"error": ...}` thì Gateway vẫn báo `isError: false` → client phải tự đọc nội dung.
- Lambda get_order warm 6–34 ms, cold init ~0.4–0.5 s. Lambda search_policy ~0.4 s (gần hết là
  KB `retrieve`), cold init ~0.3 s. Log search_policy chỉ có `query_len`, không có nội dung câu hỏi.

## Lưu ý vận hành

- Gateway hỏng (mạng, quyền, Lambda / KB lỗi) → `order_lookup` / `policy_lookup` = `"error"`, câu cố
  định "hệ thống tra cứu … đang bận", `error` = `order_unavailable` / `policy_unavailable` /
  `tools_unavailable` — **không bao giờ** nói "không tìm thấy đơn" hay "không có thông tin".
- `policy_node` và `order_node` gọi Gateway **song song** → `mcp_client` giữ tối đa 4 kết nối/host
  (mặc định urllib3 là 1 → mất keep-alive, đo được Day 61).
- Đổi schema tool: sửa `get_order.tool.json` + `lambdas/get_order/handler.py` → `01-lambda.sh` → `04-target.sh`.
- Quay về đường cũ (từng tool riêng): `ORDER_BACKEND=direct` / `POLICY_BACKEND=direct` trong
  `runtime.env` → `01-create-role.sh` (cấp lại `GetItem` / `Retrieve`) → `05-update-image.sh`.
  Không cần build image mới.
