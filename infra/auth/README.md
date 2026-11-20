# infra/auth: Cognito cho NGƯỜI DÙNG (Day 63)

> **Day 65:** resource do Terraform quản ([infra/terraform/modules/auth](../terraform/README.md)) — đổi gì thì sửa `.tf` / `terraform.tfvars` → PR → plan → merge → Approve. Script tạo / `99-destroy.sh` đã xoá; ở đây chỉ còn script vận hành / test.

Trả lời câu "**ai đang hỏi?**" (AuthN). Khách đăng nhập và nhận **access token** (JWT do pool ký
RS256). Backend kiểm token rồi mới lấy `customer_id` từ đó. Trước Day 63, `customer_id` là chuỗi
người gọi tự điền.

```
Khách ──login──▶ Cognito (support-users) ──access token──▶ Backend: auth/tokens.py kiểm 6 bước
                                                              │ customer_id = claim username
                                                              ▼
                                       Runtime (IAM, không đổi) → Gateway (AWS_IAM) → Lambda
```

Cognito đặt **trước** Runtime chứ không đặt ở Runtime hay Gateway, vì:
- Runtime chỉ nhận *hoặc* IAM *hoặc* JWT. Giữ IAM thì chỉ backend của mình gọi được Runtime.
- Chặng Runtime → Gateway là máy gọi máy trong AWS. IAM dùng credential tạm tự xoay vòng, không
  có secret nào phải giữ. Đổi sang OAuth `client_credentials` là phải giữ một secret sống lâu và trả
  tiền theo từng token M2M.
- Day 64: API Gateway (JWT authorizer) kiểm token, Lambda gọi Runtime bằng IAM. Đó đúng là việc
  `scripts/invoke_runtime.py --auth` đang làm ở local.

## Chạy

```bash
cp infra/auth/auth.env.example infra/auth/auth.env
# pool support-users + client support-web: Terraform (modules/auth)
./infra/auth/03-test-users.sh    # 8 user = 8 khách trong eval, mật khẩu → test-users.env (chmod 600)

python scripts/invoke_runtime.py "Đơn #1003 tới đâu?" --customer C003 --auth
python scripts/invoke_runtime.py --cases --auth
python scripts/invoke_runtime.py "Đơn #1003 tới đâu?" --auth --attack tampered   # → 401 bad_signature
```

User test **không** ở trong Terraform: mật khẩu sẽ nằm plaintext trong state. `03-test-users.sh` chạy
lại được; pool id tra theo **tên** mỗi lần chạy. `auth.env` và `test-users.env` đã gitignore. Pool có
`prevent_destroy` trong Terraform: plan nào định xoá / tạo lại pool (mất cả 8 user) đều bị chặn.

## Cấu hình và lý do

| Cấu hình | Vì sao |
|---|---|
| Tier **LITE** | Đủ dùng, miễn phí tới 10k MAU. Chỉ đăng nhập người dùng, không có token M2M (M2M không có free tier) |
| `AllowAdminCreateUserOnly` | Không cho tự đăng ký. Username = customer_id, nên nếu người lạ tự đăng ký được, họ có thể chiếm một mã khách |
| App client **public**, không secret | Day 64 là SPA: code trong trình duyệt ai cũng đọc được, không giữ được secret |
| `ALLOW_USER_SRP_AUTH` | Frontend chứng minh biết mật khẩu mà không gửi mật khẩu đi |
| `ALLOW_ADMIN_USER_PASSWORD_AUTH` | Cho script test. Flow này đòi quyền IAM `cognito-idp:AdminInitiateAuth` |
| **Không** bật `ALLOW_USER_PASSWORD_AUTH` | Gửi mật khẩu thô và không cần quyền gì |
| Access/ID token 60 phút, refresh 1 ngày, revocation | Token lộ thì chỉ dùng được ít thời gian, và thu hồi được |
| `PreventUserExistenceErrors` | Đăng nhập sai không tiết lộ username có tồn tại hay không |
| Username không phân biệt hoa/thường | Khuyến nghị của AWS. Cognito **lưu chữ thường**: claim là `"c003"`, nên `tokens.py` chuẩn hoá `.upper()` |

## Kiểm access token: 6 bước (`auth/tokens.py`)

| # | Kiểm | Sai → `AuthError` |
|---|---|---|
| 1 | Header `alg` phải là RS256 (chặn `none` và HS256), key chọn theo `kid` trong JWKS của pool, chữ ký khớp | `bad_signature` |
| 2 | `iss` = `https://cognito-idp.<region>.amazonaws.com/<pool_id>` | `wrong_issuer` |
| 3 | `exp` chưa qua (leeway 30 s) | `expired` |
| 4 | `token_use == "access"` (ID token không dùng để gọi API) | `not_access_token` |
| 5 | `client_id` là app client của mình | `wrong_client` |
| 6 | `username.upper()` khớp `^C\d{3,6}$` | `bad_customer_id` |

Không tải được JWKS thì trả `jwks_unavailable`: backend trả **503**, không phải 401, vì hạ tầng hỏng
không phải lỗi của người dùng. Log chỉ ghi `auth=ok` hoặc `auth=fail reason=…`, không ghi token, `sub`
hay username.

## Giới hạn đã biết

- **Username = customer_id** là cách đơn giản cho bài học. Production nên để username là email hoặc
  `sub`, rồi ánh xạ `sub → customer_id` bằng bảng, hoặc thêm claim bằng Pre Token Generation trigger
  (cần tier Essentials).
- **Không dùng thuộc tính tự đặt** (`custom:customer_id`): access token có scope
  `aws.cognito.signin.user.admin`, nên người dùng **tự sửa được** thuộc tính của chính mình. Username
  thì người dùng không tự đổi được.
- Không MFA, không email thật. Đây là pool cho khoá học.
- Hôm nay `auth/tokens.py` chạy ở máy dev (script đóng vai backend). Day 64 đưa nó vào chỗ thật.
