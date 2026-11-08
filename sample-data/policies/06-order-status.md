# Trạng thái đơn hàng (Order Status)

| Trạng thái | Ý nghĩa | Đổi trả | Bảo hành |
|---|---|---|---|
| `processing` | Đã đặt, đang chuẩn bị hàng, chưa xuất kho | Chưa (chờ giao) | Chưa |
| `shipped` | Đã xuất kho, đang vận chuyển; có mã theo dõi qua email | Chưa (chờ giao) | Chưa |
| `delivered` | Đã giao cho khách | Có, nếu còn thời hạn theo gói | Có, trong thời gian bảo hành |
| `cancelled` | Đơn đã hủy trước khi giao, không thu tiền | Không áp dụng | Không áp dụng |
| `refunded` | Đã trả hàng và hoàn tiền xong | Không (đã đổi trả rồi) | Không áp dụng |

## Lưu ý
- Thời hạn đổi trả tính từ ngày đặt hàng, không phải ngày giao. Đơn giao chậm vẫn bị trừ vào thời hạn.
- Đơn "processing" có thể hủy miễn phí bằng cách liên hệ CSKH. Đơn đã "shipped" không hủy được, chỉ
  có thể đổi trả sau khi giao.
