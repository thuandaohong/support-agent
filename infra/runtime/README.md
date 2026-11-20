# infra/runtime — AgentCore Runtime (Day 59; Terraform từ Day 65)

> **Day 65:** resource do Terraform quản ([infra/terraform/modules/runtime](../terraform/README.md)) — đổi gì thì sửa `.tf` / `terraform.tfvars` → PR → plan → merge → Approve. Script tạo / `99-destroy.sh` đã xoá; ở đây chỉ còn script vận hành / test.

Script vận hành **AgentCore Runtime** `support_agent`. Role `support-agent-runtime`, Runtime (image,
lifecycle, biến môi trường) và log group nằm trong `infra/terraform/modules/runtime`.
`runtime.env` (không commit) chỉ còn cần `AWS_REGION` + `RUNTIME_NAME` cho script dưới, và tên role /
model cho `infra/iam-audit.sh`.

## Cách dùng

```bash
cd support-agent
cp infra/runtime/runtime.env.example infra/runtime/runtime.env
./infra/runtime/03-invoke.sh "Đơn #1003 còn đổi trả được không?" C003
./infra/runtime/04-logs.sh 15m           # log CloudWatch
python scripts/invoke_runtime.py --cases # 18 ca eval qua endpoint cloud
```

| File | Việc |
|---|---|
| `runtime.env.example` | Danh sách biến (mẫu, commit). Bản thật `runtime.env` không commit |
| `_env.sh` | Nạp + kiểm biến, thư mục tạm (tự xoá), hàm tra Runtime theo tên |
| `03-invoke.sh` | Gọi 1 câu (CLI), in JSON + session id |
| `04-logs.sh` | Tail log CloudWatch của Runtime |
| `06-stop-session.sh` | Dừng 1 session ngay, không chờ idle timeout |

Đổi image: build + push ECR (tag = git SHA) → sửa `image_tag` trong `infra/terraform/live/terraform.tfvars` → PR.
Trust policy của role: chỉ `bedrock-agentcore.amazonaws.com`, chỉ từ account này (`SourceAccount` +
`SourceArn` → chống confused deputy).

## Permissions (least privilege, `modules/runtime/main.tf`)

| Sid | Quyền | Phạm vi |
|---|---|---|
| EcrPullThisRepo / EcrToken | kéo image | chỉ repo `support-agent` |
| Logs* | ghi stdout container | chỉ `/aws/bedrock-agentcore/runtimes/*` |
| XRay, Metrics | trace, số đo | metrics khoá namespace `bedrock-agentcore` |
| AppModelOnly | `bedrock:InvokeModel` | chỉ `MODEL_ID` (Nova Lite) — mẫu docs cho `foundation-model/*` |
| AppPolicyKB | `bedrock:Retrieve` | chỉ KB `KB_ID` — **chỉ khi `POLICY_BACKEND=direct`** (Day 61) |
| AppOrdersTable | `dynamodb:GetItem` | chỉ bảng `support-orders` — **chỉ khi `ORDER_BACKEND=direct`** |
| AppGatewayInvoke | `bedrock-agentcore:InvokeGateway` | chỉ gateway `support-gateway` — **chỉ khi `ORDER_BACKEND=gateway`** (Day 60) |

Từ Day 61 cả hai tool đi qua Gateway → role chỉ còn `InvokeModel` + `InvokeGateway` (+ ECR / log /
X-Ray): container không tự đọc dữ liệu nào. Terraform chỉ dựng đường Gateway (`ORDER_BACKEND` /
`POLICY_BACKEND = gateway`, `GATEWAY_URL` lấy từ output `module.gateway`). Đường `direct` vẫn còn trong
code agent (chạy local), nhưng role cloud không có `GetItem` / `Retrieve`.

Bỏ so với mẫu docs: `GetWorkloadAccessToken*` (code chưa dùng workload identity — thêm ở ngày Identity).

## Lưu ý vận hành

- Tên Runtime chỉ chữ, số, `_` (không `-`).
- Container trả 4xx/5xx → người gọi nhận **424 `RuntimeClientError`** ("Received error (422) from runtime").
- **Mỗi session id mới = 1 microVM mới (cold start)**. `03-invoke.sh` tạo session mới mỗi lần; muốn
  giữ ấm thì đặt `SESSION_ID=<id cũ>`. `scripts/invoke_runtime.py` dùng chung 1 session cho cả lượt.
- Session rảnh `IDLE_TIMEOUT` giây (300) thì tắt → hết tính tiền.
