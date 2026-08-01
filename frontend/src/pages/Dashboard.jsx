import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { listRepos, reingestRepo, getStatus, getGithubStatus, getGithubConnectUrl } from "../lib/api";
import { Button } from "../components/ui/button";

function Dashboard() {
  const { token } = useAuth();
  const navigate = useNavigate();

  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyIds, setBusyIds] = useState(new Set());

  const [searchParams, setSearchParams] = useSearchParams();
  const [githubConnected, setGithubConnected] = useState(null);
  const [justConnected, setJustConnected] = useState(false);

  useEffect(() => {
    getGithubStatus(token)
      .then((s) => setGithubConnected(s?.connected ?? false))
      .catch(() => setGithubConnected(false));

    if (searchParams.get("github_connected") === "true") {
      setJustConnected(true);
      setSearchParams({}, { replace: true });
      const timer = setTimeout(() => setJustConnected(false), 4000);
      return () => clearTimeout(timer);
    }
  }, [token]);

  function handleConnectGithub() {
    window.location.href = getGithubConnectUrl(token);
  }

  useEffect(() => {
    refresh();
  }, [token]);

  function refresh() {
    setLoading(true);
    setError("");
    listRepos(token)
      .then((data) => {
        setRepos(data);
        data.filter((r) => r.status === "queued").forEach((r) => pollStatus(r.job_id, r.repo_id));
      })
      .catch((err) => setError(err.message || "Failed to load repos."))
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
    setError("");
    try {
      const result = await reingestRepo(token, repoId);
      setRepos((prev) => prev.map((r) => (r.repo_id === repoId ? { ...r, status: "queued" } : r)));
      pollStatus(result.job_id, repoId);
    } catch (err) {
      setError(err.message || "Failed to start reingest.");
    }
  }

  return (
    <div className="min-h-[calc(100vh-57px)] bg-paper px-4 py-8">
      <div className="w-full max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="font-display text-2xl text-ink tracking-tight">Your repos</h1>
          <div className="flex items-center gap-3">
            {githubConnected === false && (
              <Button variant="ghost" size="sm" onClick={handleConnectGithub}>
                connect github
              </Button>
            )}
            {githubConnected === true && (
              <span className="font-mono text-xs text-success">✓ github connected</span>
            )}
            <Button onClick={() => navigate("/ingest")}>+ ingest new</Button>
          </div>
        </div>

        {justConnected && (
          <p role="status" aria-live="polite" className="text-sm text-success mb-4">GitHub account connected successfully.</p>
        )}

        {loading && <p aria-live="polite" className="font-mono text-sm text-muted loading-breathe">loading...</p>}
        {error && (
          <p role="alert" aria-live="polite" className="text-sm text-danger">
            {error}
          </p>
        )}
        {!loading && !error && repos.length === 0 && (
          <p className="font-mono text-sm text-muted">// no repos ingested yet</p>
        )}

        <div className="space-y-2">
          {repos.map((repo) => {
            const busy = busyIds.has(repo.repo_id) || repo.status === "queued";
            const clickable = repo.status === "success" && !busy;
            // Dim only the informational parts of the row, not the action button.
            // The reingest button is fully functional even for failed/busy rows,
            // so it should never inherit the row's disabled opacity.
            const infoDim = !clickable ? "opacity-60" : "";
            return (
              <div
                key={repo.id}
                onClick={() => clickable && navigate(`/repos/${repo.repo_id}/threads`)}
                className={`bg-elevated border border-rule rounded-lg px-4 py-3 hover:border-accent/50 transition flex items-center justify-between gap-3 ${
                  clickable ? "cursor-pointer" : "cursor-default"
                }`}
              >
                <div className={`flex items-center gap-3 min-w-0 flex-1 ${infoDim}`}>
                  <span className="font-mono text-sm text-ink truncate min-w-0" title={repo.repo_id}>
                    {repo.repo_id}
                  </span>
                  <span className={`font-mono text-xs px-2 py-0.5 rounded flex items-center gap-1 shrink-0 ${
                    repo.status === "success" ? "text-success"
                    : repo.status === "failed" ? "text-danger"
                    : "text-muted"
                  }`} aria-label={`Status: ${repo.status}`}>
                    {busy && <span className="inline-block animate-spin" aria-hidden="true">⟳</span>}
                    {busy ? "ingesting" : repo.status}
                  </span>
                </div>
                <Button
                  variant="link"
                  size="link"
                  onClick={(e) => handleReingest(e, repo.repo_id)}
                  disabled={busy}
                  aria-label={`Reingest ${repo.repo_id}`}
                  className="text-muted hover:text-accent disabled:opacity-30 shrink-0"
                >
                  ↻ reingest
                </Button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;