# infra/api: web chat (Day 64): HTTP API + Bridge Lambda

> ⚠️ **Day 65:** resource ở đây nay do Terraform quản ([infra/terraform/](../terraform/README.md)). **Không chạy script tạo / sửa / `99-destroy.sh`** nữa (sẽ lệch state; xoá sau khi apply). Script chỉ đọc / vận hành (invoke, logs, test…) vẫn dùng được.

```
Trình duyệt (frontend/, đăng nhập Cognito SRP)
  │ POST /chat · Authorization: Bearer <access token> · {question, session_id}
  ▼
HTTP API support-chat-api
  CORS (chỉ ALLOWED_ORIGIN) → throttle → JWT authorizer (iss, audience, chữ ký, exp)
  → route POST /chat bắt buộc scope aws.cognito.signin.user.admin → access log (không body)
  ▼ payload 2.0: requestContext.authorizer.jwt.claims
Bridge Lambda support-chat-bridge (lambdas/chat_bridge/handler.py)
  customer_id = claims.username.upper() · body chỉ {question, session_id}
  runtimeSessionId = "web-" + sha256(customer:session) · InvokeAgentRuntime (SigV4, không retry)
  ▼
AgentCore Runtime → Gateway → Lambda tools (không đổi)
```

## Vì sao cần Bridge Lambda

Runtime xác thực IAM (SigV4). Trình duyệt **không được giữ AWS key**, vì code web ai cũng đọc được.
HTTP API cũng không có integration gọi thẳng `InvokeAgentRuntime`. Lambda có IAM role, nên nó ký
được thay cho khách. Role chỉ có **`InvokeAgentRuntime` trên đúng 1 Runtime**: bị chiếm thì cũng
chỉ hỏi được agent, không đọc thẳng được DynamoDB hay KB.

## Chạy

```bash
cp infra/api/api.env.example infra/api/api.env
./infra/api/01-bridge-lambda.sh     # role + Lambda (timeout 29 s)
./infra/api/02-http-api.sh          # API + authorizer + route + stage + quyền gọi Lambda
./infra/api/03-frontend-env.sh      # frontend/.env.local
python scripts/api_smoke.py --throttle    # 11 ca qua API thật
```

Script nào cũng chạy lại được, mọi id tra theo **tên**. Cần có trước: `infra/auth` (Cognito) và
`infra/runtime` (Runtime). `99-destroy.sh` xoá API, Lambda, role và log (bắt gõ lại tên API để xác nhận).

## Các quyết định và lý do

| Quyết định | Vì sao |
|---|---|
| Authorizer **bắt buộc** (ghi chú gốc để "tuỳ chọn") | Agent trả dữ liệu đơn hàng thật, mà URL API thì công khai. Không có authorizer thì ai cũng hỏi được và tự điền được `customer_id` |
| Route bắt buộc scope `aws.cognito.signin.user.admin` | JWT authorizer **không phân biệt access token với ID token** (AWS docs). ID token Cognito có `aud = client_id` nên lọt qua. Chỉ access token có scope này. Bridge kiểm thêm `token_use` |
| `customer_id` chỉ lấy từ claims, body có `customer_id` → 400 | Body thì trình duyệt sửa được, token thì có chữ ký |
| `runtimeSessionId = "web-" + sha256(customer:session)` | Runtime chọn microVM theo id này và không kiểm id thuộc ai. Băm kèm mã khách thì khách khác dùng lại session id vẫn ra microVM khác. Thoả luôn điều kiện ≥ 33 ký tự |
| Timeout Lambda 29 s, boto3 đọc 25 s, **không retry** | HTTP API cắt integration ở 30 s. Retry nghĩa là hỏi Bedrock 2 lần, tốn tiền gấp đôi |
| CORS chỉ `http://localhost:5173` | CORS bảo vệ **trình duyệt** người dùng: web lạ không đọc được kết quả bằng token của họ. Curl bỏ qua CORS, nên vẫn cần authorizer |
| Access log chỉ metadata | Có request id, status, latency, `authError`. Không có body, token hay claims |
| Quyền gọi Lambda khoá `SourceArn = <api>/*/POST/chat` + `SourceAccount` | API khác, route khác không gọi được Bridge |

## Số đo thật (2026-11-16)

| Đo | Kết quả |
|---|---|
| IAM của Bridge | Chỉ ARN runtime → `AccessDenied`. Chỉ `…/runtime-endpoint/DEFAULT` → `AccessDenied`. **Cần cả hai** → 200 |
| Smoke test (`scripts/api_smoke.py --throttle`) | 11/11: preflight đúng origin 204 + allow-origin, origin lạ thì không có. Không token, rác, sửa username → 401. ID token → 403. Body có `customer_id` → 400. C003 hỏi #1003 → 200 có `orders/1003`. Lượt 2 cùng session vẫn nhớ #1003. C020 dùng lại session của C003 → không thấy đơn |
| Throttle | Request **không token** bị authorizer trả 401 và **không bị throttle đếm** (100 request → 100 lần 401). Khoảng 60 req/s đã đăng nhập → 18/150 bị 429. Throttle của stage là **gần đúng**, không phải giới hạn cứng |
| Giới hạn cứng thực tế | Account có **10 concurrency Lambda**. 30 request cùng lúc → 503 (`integrationStatus: 429`, tức Lambda bị throttle). Không đặt được reserved concurrency (phần chưa giữ chỗ phải ≥ 10) |
| Thời gian | C003 hỏi qua web khoảng 2.3–3.5 s (Bridge đo, Runtime đang ấm) |
| Log | Bridge chỉ ghi `chat ok q_len=… ms=…` hoặc `chat rejected status=… reason=…`. Không có câu hỏi, mã đơn, mã khách hay token (đã grep) |

## Giới hạn và việc sau

- Throttle tính **chung cho mọi người**: một người spam thì cả hệ chậm. HTTP API không có usage plan
  theo người, còn WAF chỉ gắn được REST API, CloudFront hoặc ALB. Khi có CloudFront thì gắn WAF rate-based rule.
- Đăng xuất chỉ thu hồi refresh token. Access token đã cấp vẫn qua authorizer cho tới khi hết hạn (≤ 60 phút).
- Frontend mới chạy local (`npm run dev`). Hosting S3 + CloudFront cùng Terraform hoá là việc của Day 65+.
