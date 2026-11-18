// Đăng nhập Cognito (Day 63 pool support-users, app client public support-web) bằng Amplify Auth v6.
// - signIn mặc định dùng SRP: chứng minh biết mật khẩu mà KHÔNG gửi mật khẩu đi.
// - Token lưu sessionStorage (không phải localStorage): đóng tab là đăng xuất, token không nằm
//   lại trên máy lâu. Amplify tự làm mới access token bằng refresh token khi hết hạn.
// - Pool id / client id không phải bí mật (frontend nào cũng lộ), nhưng repo không commit id:
//   đọc từ .env.local do infra/api/03-frontend-env.sh sinh ra.
import { Amplify } from "aws-amplify";
import { fetchAuthSession, getCurrentUser, signIn, signOut } from "aws-amplify/auth";
import { cognitoUserPoolsTokenProvider } from "aws-amplify/auth/cognito";
import { sessionStorage } from "aws-amplify/utils";

const userPoolId = import.meta.env.VITE_USER_POOL_ID;
const userPoolClientId = import.meta.env.VITE_USER_POOL_CLIENT_ID;
export const configured = Boolean(userPoolId && userPoolClientId);

if (configured) {
  Amplify.configure({ Auth: { Cognito: { userPoolId, userPoolClientId } } });
  cognitoUserPoolsTokenProvider.setKeyValueStorage(sessionStorage);
}

// Pool không phân biệt hoa/thường nên Cognito lưu "c003" → hiển thị đúng mã khách "C003"
const displayName = (username) => (username || "").toUpperCase();

export async function currentUser() {
  try {
    const { username } = await getCurrentUser();
    return displayName(username);
  } catch {
    return null; // chưa đăng nhập / token hết hạn hẳn
  }
}

export async function login(username, password) {
  // Đang có phiên cũ (vd F5 giữa chừng) → đăng xuất trước, tránh lỗi "already signed in"
  if (await currentUser()) await signOut();
  const { isSignedIn, nextStep } = await signIn({ username: username.trim(), password });
  if (!isSignedIn) {
    // Pool cho khoá học không bật MFA / đổi mật khẩu lần đầu — bước khác là cấu hình lạ
    throw new Error(`Cần thêm bước đăng nhập chưa hỗ trợ: ${nextStep.signInStep}`);
  }
  return currentUser();
}

export async function logout() {
  await signOut();
}

// Access token (KHÔNG phải ID token — route /chat bắt buộc scope chỉ access token có)
export async function accessToken() {
  const { tokens } = await fetchAuthSession();
  return tokens?.accessToken?.toString() || null;
}
