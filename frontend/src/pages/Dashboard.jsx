import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { listRepos, reingestRepo, getStatus } from "../lib/api";

function Dashboard() {
  const { token } = useAuth();
  const navigate = useNavigate();

  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyIds, setBusyIds] = useState(new Set());

  useEffect(() => {
    refresh();
  }, [token]);

  function refresh() {
    setLoading(true);
    listRepos(token)
      .then((data) => {
        setRepos(data);
        // resume polling for anything still mid-ingestion (e.g. after a page reload)
        data.filter((r) => r.status === "queued").forEach((r) => pollStatus(r.job_id, r.repo_id));
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  function pollStatus(jobId, repoId) {
    setBusyIds((prev) => new Set(prev).add(repoId));

    async function tick() {
      try {
        const result = await getStatus(token, jobId);
        if (result.state === "SUCCESS" || result.state === "FAILURE") {
          const finalStatus = result.state === "SUCCESS" ? "success" : "failed";
          setRepos((prev) => prev.map((r) => (r.repo_id === repoId ? { ...r, status: finalStatus } : r)));
          setBusyIds((prev) => { const next = new Set(prev); next.delete(repoId); return next; });
        } else {
          setTimeout(tick, 2000);
        }
      } catch (err) {
        setError(err.message);
        setBusyIds((prev) => { const next = new Set(prev); next.delete(repoId); return next; });
      }
    }
    tick();
  }

  async function handleReingest(e, repoId) {
    e.stopPropagation();
    try {
      const result = await reingestRepo(token, repoId);
      setRepos((prev) => prev.map((r) => (r.repo_id === repoId ? { ...r, status: "queued" } : r)));
      pollStatus(result.job_id, repoId);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="min-h-screen bg-(--color-ink) px-4 py-8">
      <div className="w-full max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="font-mono-ui text-lg text-(--color-bone)">$ your repos</h1>
          <button onClick={() => navigate("/ingest")}  className="bg-(--color-amber) text-(--color-ink) font-mono-ui text-sm font-medium rounded-md px-4 py-2 hover:brightness-110 transition">
            + ingest new
          </button>
        </div>

        {loading && <p className="font-mono-ui text-sm text-(--color-steel)">loading...</p>}
        {error && <p className="text-sm text-(--color-diff-remove)">{error}</p>}
        {!loading && repos.length === 0 && (
          <p className="font-mono-ui text-sm text-(--color-steel)">// no repos ingested yet</p>
        )}

        <div className="space-y-2">
          {repos.map((repo) => {
            const busy = busyIds.has(repo.repo_id) || repo.status === "queued";
            const clickable = repo.status === "success" && !busy;
            return (
              <div
                key={repo.id}
                onClick={() => clickable && navigate(`/repos/${repo.repo_id}/threads`)}
                className={`bg-(--color-slate) border border-white/5 rounded-lg px-4 py-3 hover:border-(--color-amber)/50 transition flex items-center justify-between ${
                  clickable ? "cursor-pointer" : "cursor-default opacity-60"
                }`}
              >
                <span className="font-mono-ui text-sm text-(--color-bone)">{repo.repo_id}</span>
                <div className="flex items-center gap-3">
                  <span className={`font-mono-ui text-xs px-2 py-0.5 rounded flex items-center gap-1 ${
                    repo.status === "success" ? "text-(--color-diff-add)"
                    : repo.status === "failed" ? "text-(--color-diff-remove)"
                    : "text-(--color-steel)"
                  }`}>
                    {busy && <span className="inline-block animate-spin">⟳</span>}
                    {busy ? "ingesting" : repo.status}
                  </span>
                  <button
                    onClick={(e) => handleReingest(e, repo.repo_id)}
                    disabled={busy}
                    className="font-mono-ui text-xs text-(--color-steel) hover:text-(--color-amber) transition disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    ↻ reingest
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
