# Bản đồ quyền IAM (Day 63)

Mỗi thành phần một role, mỗi role chỉ đúng quyền cần. Một tool bị khai thác thì thiệt hại chỉ nằm
trong phạm vi quyền của tool đó. Kiểm bằng máy, chạy lại được:

```bash
./infra/iam-audit.sh      # chỉ đọc; lệch kỳ vọng → exit 1
```

Script gồm 3 phần (logic ở `scripts/iam_audit.py`):
1. **Bản đồ:** trust và permission của 6 role. Account id che thành `<ACC>`, KB id che thành `<KB_ID>`.
2. **IAM Access Analyzer `validate-policy`:** permission policy (`IDENTITY_POLICY`) và trust
   (`AWS::IAM::AssumeRolePolicyDocument`). Có `ERROR` hoặc `SECURITY_WARNING` thì fail.
3. **Ma trận simulate:** mỗi ô là 1 hành động × 1 resource. Gộp nhiều resource vào một lần simulate
   cho kết quả sai, như đã gặp ở Day 61.

Thêm một luật riêng: trust của role dịch vụ AgentCore/Bedrock phải có `aws:SourceAccount` và
`aws:SourceArn` hẹp, để chống *confused deputy*. `SourceArn` kết thúc bằng `:*` bị coi là quá rộng.

## 6 role

| Role | Ai được mượn (trust) | Được làm gì |
|---|---|---|
| `support-agent-runtime` | `bedrock-agentcore`, SourceAccount, SourceArn `runtime/support_agent-*` | InvokeModel 1 model · InvokeGateway 1 gateway · ECR pull 1 repo · log, X-Ray, metric |
| `support-gateway` | `bedrock-agentcore`, SourceAccount, SourceArn `gateway/support-gateway-*` | `lambda:InvokeFunction` đúng 2 ARN |
| `support-get-order-lambda` | `lambda.amazonaws.com` | `dynamodb:GetItem` bảng `support-orders` · log group của chính nó |
| `support-search-policy-lambda` | `lambda.amazonaws.com` | `bedrock:Retrieve` KB `support-policy-kb` · log group của chính nó |
| `support-chat-bridge` (Day 64) | `lambda.amazonaws.com` | `bedrock-agentcore:InvokeAgentRuntime` trên ARN runtime **và** `…/runtime-endpoint/DEFAULT` của `support_agent` (đo thật: thiếu một trong hai → AccessDenied) · log group của chính nó |
| KB role (console tạo) | `bedrock`, SourceAccount, SourceArn `knowledge-base/*` | S3 List/Get bucket tài liệu · PutMetricData (namespace KB) |
| `support-agent-tf-plan` (Day 65, bootstrap) | OIDC GitHub, `aud = sts.amazonaws.com`, `sub = repo:…support-agent…:pull_request` (theo id bất biến) | `ReadOnlyAccess` · đọc AgentCore · ghi **đúng** file `live.tfstate.tflock` |
| `support-agent-tf-apply` (Day 65, bootstrap) | OIDC GitHub, `sub = …:environment:production` (chỉ sau Approve) | `PowerUserAccess` · `iam:*` chỉ trên `role/support-*` + role/policy KB `_1uz0d` · **Deny** sửa `role/support-agent-tf-*` (không tự nới quyền) |

Ghi chú:
- **6 role ứng dụng nay do Terraform quản** (`infra/terraform/modules/*`, Day 65): policy viết bằng
  `aws_iam_policy_document`, resource tham chiếu ARN của module khác thay vì `.json.tpl` + `envsubst`.
  2 role CI do `infra/terraform/bootstrap/` quản (pipeline không tự sửa quyền của chính nó).
- **KB loại MANAGED** (embedding và vector store do Bedrock quản lý), nên role KB **không** cần quyền gọi
  model embed hay quyền vào vector store.
- **Trust của 2 Lambda không có điều kiện:** với `lambda.amazonaws.com`, đây là mẫu execution role chuẩn
  của AWS. Ai được *gắn* role vào Lambda thì đã do `iam:PassRole` kiểm.
- Lambda không có resource policy, nên chỉ principal IAM trong account có `lambda:InvokeFunction` gọi được.
- Phần **người dùng** (AuthN) nằm ở `infra/auth/` (Cognito) và `auth/tokens.py`. Runtime vẫn IAM.

## Ma trận được/chặn

| Role | ✅ phải ĐƯỢC | ⛔ phải BỊ CHẶN |
|---|---|---|
| runtime | InvokeModel nova-lite · InvokeGateway support-gateway | InvokeModel model khác · InvokeGateway gateway khác · Retrieve KB · GetItem bảng đơn · InvokeFunction 2 Lambda |
| gateway | InvokeFunction get-order, search-policy | InvokeFunction Lambda khác · GetItem · Retrieve |
| lambda get_order | GetItem `support-orders` | PutItem · Scan · Query · GetItem bảng khác · Retrieve |
| lambda search_policy | Retrieve KB support | Retrieve KB khác · GetItem · InvokeModel |
| KB | GetObject bucket tài liệu | PutObject · GetObject bucket khác |
| bridge (Day 64) | InvokeAgentRuntime runtime + endpoint DEFAULT | InvokeAgentRuntime Runtime khác · InvokeGateway · InvokeModel · GetItem · Retrieve |

## Kết quả đo (2026-11-16)

| Lần chạy | Ma trận | Access Analyzer | Vấn đề |
|---|---|---|---|
| Trước khi siết | 26/26 | 0 finding (5 role) | 1: trust runtime `SourceArn = arn:aws:bedrock-agentcore:us-east-1:<ACC>:*` (mọi tài nguyên AgentCore trong account mượn được role) |
| Sau khi siết | 26/26 | 0 finding | 0 → exit 0 |
| Day 64: thêm role Bridge | 33/33 | 0 finding | 0 → exit 0 |

Sau khi siết trust, Runtime vẫn mượn được role khi tạo microVM mới: chạy `--cases g01 g07` và
`--chat c01` trong session mới đều đúng, rồi `--cases --auth` 18/18.
