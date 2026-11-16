# infra/runtime — AgentCore Runtime (tạo bằng CLI, Day 59)

Script tạo / vận hành **IAM execution role** + **AgentCore Runtime** cho `support-agent`.
Giá trị thật (KB ID, image tag…) nằm trong `runtime.env` — **không commit** (`.gitignore`).
Account ID không ghi ở đâu cả: script tự lấy bằng `aws sts get-caller-identity`.

> Tạm thời bằng CLI vì repo chưa có pipeline Terraform. **Ghi nợ:** khi Terraform hoá, `import`
> role `support-agent-runtime`, Runtime `support_agent` (cùng ECR `support-agent`, DynamoDB `support-orders`).

## Cách dùng

```bash
cd support-agent
cp infra/runtime/runtime.env.example infra/runtime/runtime.env   # điền KB_ID, IMAGE_TAG (ORDER_BACKEND, POLICY_BACKEND, GATEWAY_NAME có sẵn)
./infra/runtime/01-create-role.sh        # role + trust policy + inline permissions (chạy lại = cập nhật)
./infra/runtime/02-create-runtime.sh     # tạo Runtime từ image ECR, chờ READY
./infra/runtime/03-invoke.sh "Đơn #1003 còn đổi trả được không?" C003
./infra/runtime/04-logs.sh 15m           # log CloudWatch
./infra/runtime/07-log-retention.sh      # giữ log 14 ngày (sau lần invoke đầu)
python scripts/invoke_runtime.py --cases # 18 ca eval qua endpoint cloud
```

| File | Việc |
|---|---|
| `runtime.env.example` | Danh sách biến (mẫu, commit). Bản thật `runtime.env` không commit |
| `_env.sh` | Nạp + kiểm biến, render policy ra thư mục tạm (tự xoá), hàm tra Runtime theo tên |
| `trust-policy.json.tpl` | Ai được mượn role: chỉ `bedrock-agentcore.amazonaws.com`, chỉ từ account này (`SourceAccount` + `SourceArn` → chống confused deputy) |
| `permissions-policy.json.tpl` | Role làm được gì — least privilege (bảng dưới) |
| `01-create-role.sh` | Tạo / cập nhật role `support-agent-runtime` |
| `02-create-runtime.sh` | Tạo Runtime `support_agent` (image, role, network PUBLIC, lifecycle, biến môi trường), chờ READY |
| `03-invoke.sh` | Gọi 1 câu (CLI), in JSON + session id |
| `04-logs.sh` | Tail log CloudWatch của Runtime |
| `05-update-image.sh` | Đổi image / cấu hình (update thay TOÀN BỘ cấu hình → gửi lại đủ) |
| `06-stop-session.sh` | Dừng 1 session ngay, không chờ idle timeout |
| `07-log-retention.sh` | Đặt thời hạn giữ log (`LOG_RETENTION_DAYS`, mặc định 14). Log group mặc định **không bao giờ hết hạn** — chạy sau lần invoke đầu |
| `99-destroy.sh` | Xoá Runtime + role (bắt gõ lại tên để xác nhận). Không đụng ECR / DynamoDB / KB |

## Permissions (least privilege)

| Sid | Quyền | Phạm vi |
|---|---|---|
| EcrPullThisRepo / EcrToken | kéo image | chỉ repo `support-agent` |
| Logs* | ghi stdout container | chỉ `/aws/bedrock-agentcore/runtimes/*` |
| XRay, Metrics | trace, số đo | metrics khoá namespace `bedrock-agentcore` |
| AppModelOnly | `bedrock:InvokeModel` | chỉ `MODEL_ID` (Nova Lite) — mẫu docs cho `foundation-model/*` |
| AppPolicyKB | `bedrock:Retrieve` | chỉ KB `KB_ID` — **chỉ khi `POLICY_BACKEND=direct`** (Day 61) |
| AppOrdersTable | `dynamodb:GetItem` | chỉ bảng `support-orders` — **chỉ khi `ORDER_BACKEND=direct`** |
| AppGatewayInvoke | `bedrock-agentcore:InvokeGateway` | chỉ gateway `support-gateway` — **chỉ khi `ORDER_BACKEND=gateway`** (Day 60) |

`01-create-role.sh` lọc quyền theo `ORDER_BACKEND` / `POLICY_BACKEND`: tool nào đi qua Gateway thì bỏ
quyền đọc trực tiếp của tool đó. Cả hai qua Gateway → role chỉ còn `InvokeModel` + `InvokeGateway`
(+ ECR / log / X-Ray): container không tự đọc dữ liệu nào. Đổi đường: sửa `runtime.env` →
`01-create-role.sh` → `05-update-image.sh` (không cần build lại image; id + URL Gateway tra theo
`GATEWAY_NAME`). Container chỉ nhận biến của đường đang dùng (`ORDERS_TABLE` / `POLICY_KB_ID` / `GATEWAY_URL`).

Bỏ so với mẫu docs: `GetWorkloadAccessToken*` (code chưa dùng workload identity — thêm ở ngày Identity).

## Lưu ý vận hành

- Tên Runtime chỉ chữ, số, `_` (không `-`).
- Container trả 4xx/5xx → người gọi nhận **424 `RuntimeClientError`** ("Received error (422) from runtime").
- **Mỗi session id mới = 1 microVM mới (cold start)**. `03-invoke.sh` tạo session mới mỗi lần; muốn
  giữ ấm thì đặt `SESSION_ID=<id cũ>`. `scripts/invoke_runtime.py` dùng chung 1 session cho cả lượt.
- Session rảnh `IDLE_TIMEOUT` giây (300) thì tắt → hết tính tiền.
