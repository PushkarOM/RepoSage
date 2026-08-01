import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { listThreads, createThread, renameThread } from "../lib/api";
import { Button } from "../components/ui/button";

function ThreadList() {
  const { token } = useAuth();
  const { owner, name } = useParams();
  const repoId = `${owner}/${name}`;
  const navigate = useNavigate();

  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState("");

  useEffect(() => {
    setError("");
    listThreads(token, repoId)
      .then(setThreads)
      .catch((err) => setError(err.message || "Failed to load conversations."))
      .finally(() => setLoading(false));
  }, [repoId]);

  async function handleNewChat() {
    setCreating(true);
    setError("");
    try {
      const thread = await createThread(token, repoId);
      navigate(`/repos/${repoId}/threads/${thread.thread_id}`, { state: { isNew: true } });
    } catch (err) {
      setError(err.message || "Failed to start a new conversation.");
    } finally {
      setCreating(false);
    }
  }

  function startEditing(e, thread) {
    e.stopPropagation();
    setEditingId(thread.id);
    setEditValue(thread.title);
  }

  async function saveRename(thread) {
    const next = editValue;
    try {
      await renameThread(token, thread.thread_id, next);
      setThreads((prev) => prev.map((t) => (t.id === thread.id ? { ...t, title: next } : t)));
      setEditingId(null);
    } catch (err) {
      // Surface the error and drop the user out of edit mode so they aren't stuck.
      setError(err.message || "Failed to rename conversation.");
      setEditingId(null);
    }
  }

  return (
    <div className="min-h-[calc(100vh-57px)] bg-paper px-4 py-8">
      <div className="w-full max-w-2xl mx-auto">
        <Button
          variant="link"
          size="link"
          onClick={() => navigate("/dashboard")}
          className="mb-4 text-muted hover:text-accent"
        >
          ← back
        </Button>

        <div className="flex items-center justify-between mb-6 gap-3">
          <h1 className="font-display text-2xl text-ink tracking-tight truncate min-w-0">
            {repoId}
          </h1>
          <Button onClick={handleNewChat} disabled={creating} className="shrink-0">
            {creating ? "creating..." : "+ new chat"}
          </Button>
        </div>

        {loading && <p className="font-mono text-sm text-muted loading-breathe" aria-live="polite">loading...</p>}
        {error && (
          <p role="alert" aria-live="polite" className="font-mono text-sm text-danger mb-3">
            // {error}
          </p>
        )}
        {!loading && !error && threads.length === 0 && (
          <p className="font-mono text-sm text-muted">// no conversations yet — start one above</p>
        )}

        <div className="space-y-2">
          {threads.map((t) => (
            <div
              key={t.id}
              onClick={() => editingId !== t.id && navigate(`/repos/${repoId}/threads/${t.thread_id}`, { state: { isNew: false } })}
              className="bg-elevated border border-rule rounded-lg px-4 py-3 hover:border-accent/50 transition flex items-center justify-between gap-3 cursor-pointer"
            >
              {editingId === t.id ? (
                <div className="flex items-center gap-2 flex-1 min-w-0" onClick={(e) => e.stopPropagation()}>
                  <input
                    autoFocus
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && saveRename(t)}
                    maxLength={60}
                    aria-label="Rename conversation"
                    className="bg-paper border border-rule rounded px-2 py-1 text-sm text-ink flex-1 min-w-0"
                  />
                  <Button variant="link" size="link" onClick={() => saveRename(t)} aria-label="Save rename" className="text-success shrink-0">
                    save
                  </Button>
                  <Button variant="link" size="link" onClick={() => setEditingId(null)} aria-label="Cancel rename" className="text-muted shrink-0">
                    cancel
                  </Button>
                </div>
              ) : (
                <>
                  <span className="font-mono text-sm text-ink truncate min-w-0 flex-1" title={t.title}>{t.title}</span>
                  <Button
                    variant="link"
                    size="link"
                    onClick={(e) => startEditing(e, t)}
                    aria-label={`Rename "${t.title}"`}
                    className="text-muted hover:text-accent shrink-0"
                  >
                    ✎ rename
                  </Button>
                </>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default ThreadList;
