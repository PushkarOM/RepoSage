import { useState, useRef, useEffect } from "react";
import { sendChat } from "./api";

function Chat({ token, jobId }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const logEndRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function handleSubmit(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    setMessages((prev) => [...prev, { who: "you", text }]);
    setInput("");
    setSending(true);
    setError("");

    try {
      const result = await sendChat(token, jobId, text);
      setMessages((prev) => [...prev, { who: "agent", text: result.reply }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-(--color-ink) px-4 py-8">
      <div className="w-full max-w-2xl bg-(--color-slate) border border-white/5 rounded-lg shadow-xl flex flex-col h-[80vh]">
        <div className="px-6 py-4 border-b border-white/5">
          <p className="font-mono-ui text-xs text-(--color-amber)">$ chat --job {jobId.slice(0, 8)}</p>
          <h1 className="font-mono-ui text-lg text-(--color-bone) mt-1">RepoSage</h1>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <p className="font-mono-ui text-sm text-(--color-steel)">
              // repo ingested — ask about implementation, structure, or good-first-issues
            </p>
          )}
          {messages.map((m, i) => (
            <div key={i} className="flex gap-2">
              <span
                className={`font-mono-ui text-sm shrink-0 ${
                  m.who === "you" ? "text-(--color-amber)" : "text-(--color-diff-add)"
                }`}
              >
                {m.who === "you" ? ">" : "$"}
              </span>
              <p className="text-sm text-(--color-bone) leading-relaxed">{m.text}</p>
            </div>
          ))}
          {sending && (
            <div className="flex gap-2">
              <span className="font-mono-ui text-sm text-(--color-diff-add)">$</span>
              <p className="font-mono-ui text-sm text-(--color-steel) animate-pulse">thinking...</p>
            </div>
          )}
          <div ref={logEndRef} />
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 border-t border-white/5 flex gap-2">
          <span className="font-mono-ui text-sm text-(--color-amber) pt-2">{">"}</span>
          <input
            type="text"
            placeholder="ask something about the repo..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
            className="flex-1 bg-(--color-ink) border border-white/10 rounded-md px-3 py-2 text-(--color-bone) text-sm placeholder:text-(--color-steel)/50 focus:outline-none focus:ring-2 focus:ring-(--color-amber) disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={sending}
            className="bg-(--color-amber) text-(--color-ink) font-mono-ui text-sm font-medium rounded-md px-4 hover:brightness-110 transition disabled:opacity-50"
          >
            send
          </button>
        </form>

        {error && <p className="px-6 pb-3 text-sm text-(--color-diff-remove)">{error}</p>}
      </div>
    </div>
  );
}

export default Chat;
