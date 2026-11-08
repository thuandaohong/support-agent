# Dữ liệu synthetic

Toàn bộ dữ liệu là **bịa** (tên, đơn hàng, chính sách) — không có thông tin thật của ai, nên được commit.

| File | Nạp vào | Agent dùng |
|---|---|---|
| `policies/*.md` (6 file) | Bedrock Knowledge Base | Policy agent (RAG) |
| `orders.csv` (50 đơn, 44 khách) | DynamoDB | Order agent |

## `orders.csv`

| Cột | Ý nghĩa |
|---|---|
| `order_id` | Mã đơn, 1001–1050 |
| `customer_id` | Mã khách `C001`… — dùng để kiểm tra "khách chỉ xem được đơn của mình" |
| `customer` | Tên khách. **Có 2 người khác nhau cùng tên "Le Linh"** (`C020`, `C035`) — cố ý |
| `plan` | Gói **hiện tại** của khách (Basic / Premium / Pro), giống nhau ở mọi đơn của 1 khách |
| `product` | Sản phẩm đã mua |
| `status` | `processing` · `shipped` · `delivered` · `cancelled` · `refunded` (xem `policies/06-order-status.md`) |
| `order_date` | Ngày đặt — mốc tính hạn đổi trả và bảo hành |
| `amount` | Giá sản phẩm (USD) |

## ⚠️ Quy ước ngày: `AS_OF_DATE = 2026-11-08`

Hạn đổi trả phụ thuộc "hôm nay". Nếu agent dùng ngày thật của hệ thống thì đáp án đổi theo thời
gian (tính tại 2026-12-08, cả 21 đơn đã giao đều quá hạn) → golden set và eval hỏng dần.

→ Agent **không tự lấy ngày hệ thống**, mà nhận "hôm nay" từ cấu hình `AS_OF_DATE`. Eval luôn chạy
với `AS_OF_DATE=2026-11-08`. Demo có thể bỏ trống để dùng ngày thật.

Tại `AS_OF_DATE=2026-11-08`: 21 đơn đã giao → **12 còn hạn đổi trả**, 9 quá hạn.

## Trường hợp đặc biệt (cố ý, cho golden set)

| Đơn | Tình huống | Đáp án đúng |
|---|---|---|
| 1001 | Pro, delivered, 15 ngày | Đổi trả được (hạn 30) |
| 1002 | Pro, processing, 35 ngày | Không: chưa giao, và đã quá hạn |
| 1003 | Premium, delivered, 6 ngày | Đổi trả được (hạn 14) |
| 1019 | Pro, delivered, **đúng 30 ngày** | Được — tính cả ngày cuối |
| 1014 | Premium, delivered, **đúng 14 ngày** | Được |
| 1008 | Premium, delivered, **15 ngày** | Không — quá hạn 1 ngày |
| 1050 | Basic, delivered, **đúng 7 ngày** | Được |
| 1026 | Basic, shipped, 8 ngày | Không: chưa giao, và khi giao cũng đã quá hạn |
| 1007, 1022 | refunded | Không: đã hoàn tiền |
| 1012 | cancelled | Không áp dụng |
| "đơn của Le Linh" | 2 khách trùng tên | Phải hỏi lại / dùng `customer_id`, không đoán |
| 9999 | Mã đơn không tồn tại | Nói không tìm thấy, không bịa |
