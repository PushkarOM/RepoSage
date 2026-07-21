import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

import { streamChat } from "../lib/api"; 

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

    setMessages((prev) => [...prev, { who: "you", text }, { who: "agent", text: "" }]);
    setInput("");
    setSending(true);
    setError("");

    try {
      await streamChat(token, jobId, text, (chunk) => {
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            text: updated[updated.length - 1].text + chunk,
          };
          return updated;
        });
      });
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
             <div className="text-sm text-(--color-bone) leading-relaxed prose-chat">
              <ReactMarkdown
                components={{
                  code({ inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || "");
                    return !inline && match ? (
                      <SyntaxHighlighter
                        style={vscDarkPlus}
                        language={match[1]}
                        PreTag="div"
                        customStyle={{ borderRadius: "8px", fontSize: "13px", margin: "8px 0" }}
                      >
                        {String(children).replace(/\n$/, "")}
                      </SyntaxHighlighter>
                    ) : (
                      <code className="bg-white/10 px-1.5 py-0.5 rounded text-(--color-amber) text-xs" {...props}>
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {m.text}
              </ReactMarkdown>
            </div>
            </div>
          ))}
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
