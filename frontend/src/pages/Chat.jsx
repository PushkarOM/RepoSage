import { useState, useEffect } from "react";
import { useParams, useLocation, useNavigate } from "react-router-dom";
import { useToast } from "../lib/toast.jsx";
import { streamChat, autoTitleThread, getThreadMessages } from "../lib/api";
import { Button } from "../components/ui/button";
import MessageList from "../components/MessageList";

function Chat() {
  const { pushToast } = useToast();
  const { owner, name, threadId } = useParams();
  const repoId = `${owner}/${name}`;
  const location = useLocation();
  const navigate = useNavigate();
  const isNewThread = location.state?.isNew ?? false;

  const [messages, setMessages] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [shouldAutoTitle, setShouldAutoTitle] = useState(isNewThread);

  useEffect(() => {
    setLoadingHistory(true);
    setHistoryError("");
    getThreadMessages(threadId)
      .then((data) => {
        setMessages(data);
      })
      .catch((err) => {
        setHistoryError(err.message || "Failed to load conversation history.");
      })
      .finally(() => setLoadingHistory(false));
  }, [threadId]);

  // True only for the last message, which is the in-flight agent bubble.
  const streamingIndex = sending ? messages.length - 1 : -1;

  async function handleSubmit(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    setMessages((prev) => [...prev, { who: "you", text }, { who: "agent", text: "" }]);
    setInput("");
    setSending(true);
    setError("");

    try {
      await streamChat(repoId, text, threadId, (chunk) => {
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            text: updated[updated.length - 1].text + chunk,
          };
          return updated;
        });
      });

      if (shouldAutoTitle) {
        autoTitleThread(threadId, text)
          .catch(() => {});
        setShouldAutoTitle(false);
      }
    } catch (err) {
      // Optimistic bubble was appended on submit so the user sees immediate
      // feedback — on failure we owe it removal, otherwise it sits above the
      // input bar forever. Drop the trailing empty assistant message before
      // surfacing the error.
      setMessages((prev) => prev.slice(0, -1));
      // 429 (rate limit) lives mid-conversation; toast is the right surface.
      // Other failures are surfaced inline so the user can read and retry.
      if (err.status === 429) {
        pushToast({ kind: "error", message: err.message });
      } else {
        setError(err.message);
      }
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-57px)] bg-paper px-4 py-6">
      <div className="w-full max-w-3xl mx-auto flex flex-col h-[calc(100vh-57px-3rem)]">
        {/* Sub-header — open canvas, no card. The PromptBar in the global
            header already shows repo + thread context; this strip is just
            an agent identity tag (the only serif moment in the chat view). */}
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="font-display text-xl text-ink tracking-tight">RepoSage</h2>
          <span className="font-mono text-xs text-muted">chat with this repo</span>
        </div>

        {/* Messages live directly on the page canvas — no wrapping card.
            Conversation reads top-to-bottom in open whitespace. */}
        <MessageList
          messages={messages}
          loadingHistory={loadingHistory}
          streamingIndex={streamingIndex}
          historyError={historyError}
        />

        {error && (
          <p role="alert" aria-live="polite" className="mb-2 text-sm text-danger">
            {error}
          </p>
        )}

        {/* Input is the only outlined surface, and only on focus. When
            idle it's a hairline rule that floats — like Claude/ChatGPT. */}
        <form
          onSubmit={handleSubmit}
          className="mt-auto flex gap-2 items-center bg-elevated rounded-xl border border-rule focus-within:border-accent/60 px-4 py-3 transition"
        >
          <span className="font-mono text-sm text-accent" aria-hidden="true">{">"}</span>
          <input
            type="text"
            placeholder="ask something about the repo..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
            className="flex-1 bg-transparent text-ink font-mono text-sm placeholder:text-muted/50 focus:outline-none disabled:opacity-50"
          />
          <Button type="submit" disabled={sending} aria-label="Send message">
            {sending ? "sending..." : "send"}
          </Button>
        </form>

        <Button
          variant="link"
          size="link"
          onClick={() => navigate(`/repos/${repoId}/threads`)}
          className="mt-3 self-start text-muted hover:text-accent"
        >
          ← all conversations
        </Button>
      </div>
    </div>
  );
}

export default Chat;