import { useState, useEffect } from "react";
import { useParams, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { streamChat, autoTitleThread, getThreadMessages } from "../lib/api";
import { Button } from "../components/ui/button";
import MessageList from "../components/MessageList";
import PromptBar from "../components/PromptBar";

function Chat() {
  const { token } = useAuth();
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
  const [threadTitle, setThreadTitle] = useState(null);

  useEffect(() => {
    setLoadingHistory(true);
    setHistoryError("");
    getThreadMessages(token, threadId)
      .then((data) => {
        setMessages(data);
        if (data.length && data[0].title) setThreadTitle(data[0].title);
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
      await streamChat(token, repoId, text, threadId, (chunk) => {
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
        autoTitleThread(token, threadId, text)
          .then((res) => { if (res?.title) setThreadTitle(res.title); })
          .catch(() => {});
        setShouldAutoTitle(false);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-57px)] bg-paper px-4 py-6">
      <div className="w-full max-w-3xl mx-auto">
        {/* The PromptBar lives in the global header. Here we keep an in-card
            sub-header that shows the agent identity (the only serif moment). */}
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="font-display text-xl text-ink tracking-tight">RepoSage</h2>
          <span className="font-mono text-xs text-muted">chat with this repo</span>
        </div>

        <div className="w-full bg-elevated border border-rule rounded-lg shadow-xl flex flex-col h-[78vh]">
          <div className="px-6 py-3 border-b border-rule">
            <PromptBar threadTitle={threadTitle ?? undefined} />
          </div>

          <MessageList messages={messages} loadingHistory={loadingHistory} streamingIndex={streamingIndex} historyError={historyError} />

          <form onSubmit={handleSubmit} className="px-6 py-4 border-t border-rule flex gap-2 items-center">
            <span className="font-mono text-sm text-accent" aria-hidden="true">{">"}</span>
            <input
              type="text"
              placeholder="ask something about the repo..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={sending}
              className="flex-1 bg-paper border border-rule rounded-md px-3 py-2 text-ink font-mono text-sm placeholder:text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent-strong disabled:opacity-50"
            />
            <Button type="submit" disabled={sending} aria-label="Send message">
              {sending ? "sending..." : "send"}
            </Button>
          </form>

          {error && (
            <p role="alert" aria-live="polite" className="px-6 pb-3 text-sm text-danger">
              {error}
            </p>
          )}
        </div>

        <Button
          variant="link"
          size="link"
          onClick={() => navigate(`/repos/${repoId}/threads`)}
          className="mt-3 text-muted hover:text-accent"
        >
          ← all conversations
        </Button>
      </div>
    </div>
  );
}

export default Chat;