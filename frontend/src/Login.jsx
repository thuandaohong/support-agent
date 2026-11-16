import { useState } from "react";
import { login } from "./auth";

// Form đăng nhập Cognito. Lỗi hiện chung chung — không nói "sai user" hay "sai mật khẩu"
// (pool cũng bật PreventUserExistenceErrors: không lộ user có tồn tại hay không).
export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!username.trim() || !password || busy) return;
    setBusy(true);
    setError("");
    try {
      onLogin(await login(username, password));
    } catch (err) {
      const name = err?.name || "";
      setError(
        name === "NotAuthorizedException" || name === "UserNotFoundException"
          ? "Tên đăng nhập hoặc mật khẩu không đúng."
          : err?.message || "Không đăng nhập được, thử lại sau."
      );
    } finally {
      setPassword("");
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>Trợ lý CSKH</h1>
        <p className="login-hint">Đăng nhập để hỏi về đơn hàng và chính sách.</p>
        <label>
          Mã khách hàng
          <input
            autoFocus
            autoComplete="username"
            placeholder="vd C003"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </label>
        <label>
          Mật khẩu
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && <p className="login-error">{error}</p>}
        <button type="submit" disabled={busy || !username.trim() || !password}>
          {busy ? "Đang đăng nhập…" : "Đăng nhập"}
        </button>
      </form>
    </div>
  );
}
