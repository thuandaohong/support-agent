import { useEffect, useRef, useState } from "react";
import { AuthExpired, askAgent } from "./api";
import { configured, currentUser, logout } from "./auth";
import Login from "./Login";

const MAX_QUESTION = 2000; // giống giới hạn của Bridge Lambda / serve.py

// Nguồn agent trả: "01-return-policy.md" (tài liệu chính sách) hoặc "orders/1003" (dữ liệu đơn)
function sourceName(s) {
  const order = s.match(/^orders\/(\d+)$/);
  if (order) return `Đơn #${order[1]}`;
  return s.replace(/\.md$/, "").replace(/^\d+-/, "").replace(/-/g, " ");
}

// Render markdown tối giản AN TOÀN: escape HTML trước, rồi chỉ cho phép **đậm**.
// Không dùng thư viện, không dangerouslySet với nội dung chưa escape.
function renderText(text) {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const withBold = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  return { __html: withBold };
}

export default function App() {
  // undefined = đang kiểm phiên cũ, null = chưa đăng nhập, "C003" = đã đăng nhập
  const [user, setUser] = useState(undefined);
  // Mỗi tin: { role: "user" | "bot", text, sources?, error? }
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  // Một uuid cho mỗi cuộc trò chuyện → server băm kèm mã khách → agent nhớ các lượt trước
  const sessionId = useRef(crypto.randomUUID());
  const endRef = useRef(null);

  useEffect(() => {
    currentUser().then(setUser);
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function newConversation() {
    setMessages([]);
    sessionId.current = crypto.randomUUID();
  }

  async function handleLogout() {
    await logout();
    newConversation();
    setUser(null);
  }

  async function handleSend() {
    const q = input.trim();
    if (!q || loading) return;

    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setInput("");
    setLoading(true);

    try {
      const data = await askAgent(q, sessionId.current);
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: data.answer || "(không có câu trả lời)", sources: data.sources || [] },
      ]);
    } catch (e) {
      if (e instanceof AuthExpired) {
        // Token không còn dùng được → về màn đăng nhập (giữ nguyên câu vừa hỏi để hỏi lại)
        setInput(q);
        setMessages((prev) => prev.slice(0, -1));
        await logout().catch(() => {});
        setUser(null);
        return;
      }
      setMessages((prev) => [...prev, { role: "bot", text: e.message || "Không gọi được API", error: true }]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    // isComposing: đang gõ dở chữ bằng bộ gõ tiếng Việt (Telex/VNI) -> Enter để chốt chữ, không gửi
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  }

  if (!configured) {
    return <p className="empty">Thiếu cấu hình Cognito — chạy infra/api/03-frontend-env.sh rồi khởi động lại.</p>;
  }
  if (user === undefined) return <p className="empty">Đang tải…</p>;
  if (user === null) return <Login onLogin={setUser} />;

  return (
    <div className="app">
      <header className="header">
        <h1>Trợ lý CSKH</h1>
        <span className="tag">{user}</span>
        <div className="header-actions">
          {messages.length > 0 && !loading && (
            <button className="clear" onClick={newConversation}>
              Cuộc trò chuyện mới
            </button>
          )}
          <button className="clear" onClick={handleLogout} disabled={loading}>
            Đăng xuất
          </button>
        </div>
      </header>

      <main className="chat">
        {messages.length === 0 && (
          <p className="empty">Hỏi về đơn hàng hoặc chính sách, vd "Đơn #1003 còn đổi trả được không?"</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.role === "bot" && !m.error ? (
              <div className="bubble" dangerouslySetInnerHTML={renderText(m.text)} />
            ) : (
              <div className={`bubble ${m.error ? "error" : ""}`}>{m.text}</div>
            )}
            {m.sources && m.sources.length > 0 && (
              <div className="sources">
                <span className="sources-label">Nguồn:</span>
                {m.sources.map((s, j) => (
                  <span key={j} className={`source ${s.startsWith("orders/") ? "order" : ""}`} title={s}>
                    {sourceName(s)}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="msg bot">
            <div className="bubble typing">Đang trả lời…</div>
          </div>
        )}
        <div ref={endRef} />
      </main>

      <footer className="composer">
        {/* Không disable textarea khi loading: vẫn gõ trước được câu sau, không mất focus.
            Việc chặn gửi trùng đã do nút Gửi + check `loading` trong handleSend lo. */}
        <textarea
          rows={1}
          maxLength={MAX_QUESTION}
          placeholder="Nhập câu hỏi…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button onClick={handleSend} disabled={!input.trim() || loading}>
          Gửi
        </button>
      </footer>
    </div>
  );
}
