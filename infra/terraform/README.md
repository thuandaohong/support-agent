# Terraform (Day 65)

Toàn bộ hạ tầng AWS của support-agent nằm trong Terraform. Các resource chạy từ Day 51–64 (tạo bằng
CLI/console) đã được **nhận vào state bằng `import {}`** (PR #9, khối import đã xoá sau khi apply), không tạo lại: 50 đơn, 8 user, KB id, URL Gateway,
ARN Runtime, pool id, URL API đều giữ nguyên.

```
infra/terraform/
├── bootstrap/        apply Ở MÁY 1 lần — bucket state (00-state-bucket.sh) + role OIDC tf-plan / tf-apply
├── live/             root chính — CHỈ GitHub Actions apply
│   ├── main.tf       nối 8 module: output module này = input module kia
│   └── terraform.tfvars  tên, origin, throttle, image_tag… (không bí mật, không id)
└── modules/
    ├── data/             DynamoDB · S3 chính sách · ECR (+ lifecycle)         🔒 prevent_destroy
    ├── knowledge_base/   role + 2 policy console tạo · KB MANAGED 🔒 · data source
    ├── lambda_function/  ★ dùng 3 lần: role + inline policy + log group + function arm64
    ├── gateway/          role · Gateway MCP AWS_IAM · target orders, policies (schema từ infra/gateway/*.tool.json)
    ├── runtime/          execution role · Runtime (image = ecr:var.image_tag) · log group
    ├── auth/             Cognito pool 🔒 + client public (SRP)
    └── web_api/          HTTP API · JWT authorizer + scope · route · stage throttle · Lambda permission
```

Thứ tự Terraform tự suy từ tham chiếu:

```
data ──table_arn──▶ lambda_get_order ─┐
data ──bucket────▶ knowledge_base ──kb──▶ lambda_search_policy ─┴─arn─▶ gateway ──url, arn──▶ runtime ──arn──▶ lambda_bridge ──▶ web_api
data ──ecr_url──────────────────────────────────────────────────────────────────────────────────▶ runtime          auth ──issuer, client──▶ web_api
```

## Đường thay đổi

1. Nhánh mới, sửa `.tf` → `cd infra/terraform/live && terraform plan` (ở máy, chỉ đọc).
2. Mở PR → job `plan` (role `support-agent-tf-plan`, ReadOnly) comment **bản tóm tắt** vào PR.
3. Đọc tóm tắt: `delete` / `replace` phải bằng 0 — job tự đỏ nếu không (`ALLOW_DESTROY=1` để cố ý xoá).
4. Merge → job `apply` dừng ở environment `production` → bấm **Approve** → role `support-agent-tf-apply` plan lại,
   kiểm lại luật, apply đúng file plan đó.

**Repo public:** output thô của `terraform plan/apply` có account id, pool id, KB id, ARN → workflow không in
nó ra log, chỉ in [scripts/tf_plan_summary.py](../../scripts/tf_plan_summary.py) (địa chỉ resource, hành động, tên
thuộc tính). Output `terraform output` đánh dấu `sensitive`. Xem giá trị: chạy ở máy.

## Việc thường gặp

| Việc | Làm gì |
|---|---|
| Đổi image agent | build + push ECR (tag = git SHA, xem README gốc) → sửa `image_tag` trong `terraform.tfvars` → PR |
| Sửa code Lambda | sửa `lambdas/<tên>/handler.py` → PR (Terraform zip lại, hash đổi → deploy) |
| Đổi tool schema | sửa `infra/gateway/*.tool.json` → PR |
| Đổi origin web / throttle | `terraform.tfvars` → PR |
| Thêm quyền cho Lambda | `policy_statements` trong `live/main.tf` → PR → chạy `./infra/iam-audit.sh` sau apply |

## Cố ý KHÔNG ở trong Terraform

| Thứ | Vì sao · làm bằng gì |
|---|---|
| 5 file chính sách + sync KB | dữ liệu, không phải hạ tầng · `aws s3 sync` + `start-ingestion-job` (data source id: `terraform output`) |
| 50 đơn | dữ liệu · `scripts/load_orders.py` |
| User test + mật khẩu | vào Terraform = mật khẩu plaintext trong state · `infra/auth/03-test-users.sh` |
| Build / push image | artifact, không phải hạ tầng · `docker buildx` + `docker push` |
| OIDC provider GitHub | thuộc Project 1 (mỗi account 1 provider) · `data` source trong bootstrap |
| Endpoint DEFAULT của Runtime, log group `vendedlogs` của KB | AWS tự tạo / quản |

## Bootstrap (1 lần, ở máy)

```bash
./infra/terraform/bootstrap/00-state-bucket.sh       # bucket state: versioning, SSE, chặn public, chỉ HTTPS
cd infra/terraform/bootstrap && terraform init && terraform plan -out=tfplan   # 6 to add, 0 change, 0 destroy
terraform apply tfplan && terraform output            # 2 ARN
```
Rồi trên GitHub: **Settings → Secrets → Actions** thêm `AWS_TF_PLAN_ROLE_ARN`, `AWS_TF_APPLY_ROLE_ARN`;
**Settings → Environments** tạo `production`, bật **Required reviewers** (chính bạn).

## Kết quả đo

| Lần | Kết quả | Ngày |
|---|---|---|
| Plan ở máy sau bước 7 | `42 to import, 0 to add, 11 to change, 0 to destroy` — 6 thêm tag `project`, 2 chỉ khác khoảng trắng JSON, 3 Lambda deploy lại code giống hệt (đã so byte với code đang chạy) | 2026-11-18 |
| CI apply (PR #9, Approve) | 42 import · 11 update · 0 add/destroy. Sau đó plan **No changes**; state 42 resource + 17 data source; iam-audit 33/33 · api_smoke 11/11 · Runtime cases 18/18 | 2026-11-20 |
| Dọn import + script cũ (bước 9b) | plan vẫn **No changes** | 2026-11-20 |
