import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { listThreads, createThread, renameThread } from "../lib/api";

function ThreadList() {
  const { token } = useAuth();
  const { owner, name } = useParams();
  const repoId = `${owner}/${name}`;
  const navigate = useNavigate();

  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState("");

  useEffect(() => {
    listThreads(token, repoId).then(setThreads).finally(() => setLoading(false));
  }, [repoId]);

  async function handleNewChat() {
    setCreating(true);
    try {
      const thread = await createThread(token, repoId);
      navigate(`/repos/${repoId}/threads/${thread.thread_id}`, { state: { isNew: true } });
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
    await renameThread(token, thread.thread_id, editValue);
    setThreads((prev) => prev.map((t) => (t.id === thread.id ? { ...t, title: editValue } : t)));
    setEditingId(null);
  }

  return (
    <div className="min-h-screen bg-(--color-ink) px-4 py-8">
      <div className="w-full max-w-2xl mx-auto">
        <button onClick={() => navigate("/dashboard")} className="font-mono-ui text-xs text-(--color-steel) hover:text-(--color-amber) mb-4">
          ← back
        </button>
        <div className="flex items-center justify-between mb-6">
          <h1 className="font-mono-ui text-lg text-(--color-bone)">$ {repoId}</h1>
          <button
            onClick={handleNewChat}
            disabled={creating}
            className="bg-(--color-amber) text-(--color-ink) font-mono-ui text-sm font-medium rounded-md px-4 py-2 hover:brightness-110 transition disabled:opacity-50"
          >
            {creating ? "creating..." : "+ new chat"}
          </button>
        </div>

        {loading && <p className="font-mono-ui text-sm text-(--color-steel)">loading...</p>}
        {!loading && threads.length === 0 && (
          <p className="font-mono-ui text-sm text-(--color-steel)">// no conversations yet -- start one above</p>
        )}

        <div className="space-y-2">
          {threads.map((t) => (
            <div
              key={t.id}
              onClick={() => editingId !== t.id && navigate(`/repos/${repoId}/threads/${t.thread_id}`, { state: { isNew: false } })}
              className="bg-(--color-slate) border border-white/5 rounded-lg px-4 py-3 hover:border-(--color-amber)/50 transition flex items-center justify-between cursor-pointer"
            >
              {editingId === t.id ? (
                <div className="flex items-center gap-2 flex-1" onClick={(e) => e.stopPropagation()}>
                  <input
                    autoFocus
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && saveRename(t)}
                    className="bg-(--color-ink) border border-white/10 rounded px-2 py-1 text-sm text-(--color-bone) flex-1"
                  />
                  <button onClick={() => saveRename(t)} className="font-mono-ui text-xs text-(--color-diff-add) px-2 py-1">save</button>
                  <button onClick={() => setEditingId(null)} className="font-mono-ui text-xs text-(--color-steel) px-2 py-1">cancel</button>
                </div>
              ) : (
                <>
                  <span className="font-mono-ui text-sm text-(--color-bone)">{t.title}</span>
                  <button onClick={(e) => startEditing(e, t)} className="font-mono-ui text-xs text-(--color-steel) hover:text-(--color-amber)">✎ rename</button>
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
