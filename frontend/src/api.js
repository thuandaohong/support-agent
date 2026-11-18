// Gọi POST /chat của HTTP API (Day 64). URL đọc từ biến môi trường (không hardcode).
// Bỏ dấu "/" thừa ở cuối để ghép "/chat" không bị "//chat".
import { accessToken } from "./auth";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

// 401 → token không còn dùng được: App đưa về màn đăng nhập
export class AuthExpired extends Error {}

// Thông báo cho người dùng theo mã lỗi — không hiện chi tiết kỹ thuật
const MESSAGES = {
  400: "Câu hỏi không hợp lệ (trống hoặc quá dài).",
  403: "Tài khoản không có quyền dùng trợ lý.",
  429: "Bạn hỏi nhanh quá, đợi vài giây rồi thử lại nhé.",
  502: "Hệ thống đang bận, bạn thử lại sau ít phút.",
  503: "Hệ thống đang bận, bạn thử lại sau ít phút.",
  504: "Hệ thống phản hồi quá lâu, bạn thử lại nhé.",
};

// sessionId: uuid của cuộc trò chuyện. Server băm kèm mã khách lấy từ token → agent nhớ các lượt
// trước trong cùng cuộc trò chuyện. KHÔNG gửi customer_id: danh tính chỉ nằm trong token.
export async function askAgent(question, sessionId) {
  if (!API_URL) {
    throw new Error("Chưa cấu hình VITE_API_URL — chạy infra/api/03-frontend-env.sh");
  }
  const token = await accessToken();
  if (!token) throw new AuthExpired("Phiên đăng nhập đã hết");

  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ question, session_id: sessionId }),
  });
  if (res.status === 401) throw new AuthExpired("Phiên đăng nhập đã hết");
  if (!res.ok) throw new Error(MESSAGES[res.status] || `Lỗi ${res.status}`);

  // Thành công: { answer, sources, route, error? }
  return res.json();
}
