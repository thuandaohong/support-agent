# frontend: web chat cho support-agent (Day 64)

React 18 + Vite 5 (khung từ `rag-chatbot/frontend` của project 1), thêm **đăng nhập Cognito** bằng
Amplify Auth v6 (`aws-amplify@6.22.2`, chỉ dùng phần auth).

```
Login.jsx ── signIn (SRP: không gửi mật khẩu) ──▶ Cognito support-users
App.jsx   ── POST /chat  Authorization: Bearer <access token>
             body {question, session_id}  ──▶ HTTP API → Bridge Lambda → AgentCore Runtime
```

- **Không gửi `customer_id`.** Danh tính chỉ nằm trong token. Bridge lấy mã khách từ claims đã được
  HTTP API kiểm.
- **`session_id`** = `crypto.randomUUID()` cho mỗi cuộc trò chuyện. Server băm kèm mã khách, nên
  agent nhớ các lượt trước. Nút "Cuộc trò chuyện mới" tạo uuid mới.
- **Token lưu `sessionStorage`:** đóng tab là đăng xuất. Amplify tự làm mới access token.
- **Lỗi:** 401 → về màn đăng nhập (giữ lại câu đang hỏi) · 429 → "hỏi nhanh quá" · 502/503 → "hệ thống bận".
  Không hiện chi tiết kỹ thuật.
- Câu trả lời render an toàn: escape HTML trước, chỉ cho `**đậm**`.

## Chạy

```bash
./infra/api/03-frontend-env.sh      # sinh frontend/.env.local (URL API, pool id, client id; gitignore)
cd frontend && npm install && npm run dev
# mở http://localhost:5173. Đúng origin này mới được CORS cho phép (allowed_origin trong infra/terraform/live/terraform.tfvars)
```

Đăng nhập bằng user test (`C003`, `C020`, …). Mật khẩu nằm trong `infra/auth/test-users.env`
(do `infra/auth/03-test-users.sh` sinh, chỉ máy bạn có).

`npm run build` → `dist/`. Hosting (S3 + CloudFront) chưa làm. Khi có domain thật thì đổi
`allowed_origin` trong `infra/terraform/live/terraform.tfvars` (và `ALLOWED_ORIGIN` trong `infra/api/api.env`) → PR.
