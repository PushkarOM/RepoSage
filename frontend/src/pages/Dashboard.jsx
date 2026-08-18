import { useState, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useToast } from "../lib/toast.jsx";
import { listRepos, reingestRepo, getStatus, getGithubStatus, getGithubConnectUrl } from "../lib/api";
import { Button } from "../components/ui/button";

// Polling budget for the post-submit path (handleReingest). The SSE stream
// covers the live experience during a fresh ingest; polling is a fallback
// for reingests fired from this dashboard tab -- capped at 30s so a worker
// crash can't pin a row to a spinner forever.
const MAX_REINGEST_POLLS = 15;

function Dashboard() {
  const navigate = useNavigate();
  const { pushToast } = useToast();

  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // Set of repo_id strings for reingests kicked off during THIS dashboard
  // session. A row that's "queued" but not in busyIds is a stale entry
  // from a prior session -- show a retry CTA instead of a spinner.
  const [busyIds, setBusyIds] = useState(new Set());

  const [searchParams, setSearchParams] = useSearchParams();
  const [githubConnected, setGithubConnected] = useState(null);

  useEffect(() => {
    getGithubStatus()
      .then((s) => setGithubConnected(s?.connected ?? false))
      .catch(() => setGithubConnected(false));

    if (searchParams.get("github_connected") === "true") {
      pushToast({ kind: "success", message: "GitHub account connected." });
      setSearchParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pushToast]);

  function handleConnectGithub() {
    window.location.href = getGithubConnectUrl();
  }

  const refresh = useCallback(() => {
    setLoading(true);
    setError("");
    listRepos()
      .then((data) => {
        setRepos(data);
        // Don't auto-poll rows that were already queued on page load.
        // Those entries belong to a prior session -- their SSE stream is
        // long dead. The user can click "reingest" if they want to retry.
      })
      .catch((err) => setError(err.message || "Failed to load repos."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Bounded fallback polling for reingests kicked off from this session.
  // The SSE stream in Ingest.jsx is the primary path; this only runs when
  // the user clicks "reingest" while already on the dashboard and stays on
  // the page. Stops after MAX_REINGEST_POLLS regardless of state so a
  // worker crash can never pin a row to a spinner forever.
  function pollStatus(jobId, repoId) {
    setBusyIds((prev) => new Set(prev).add(repoId));
    let polls = 0;

    async function tick() {
      polls += 1;
      try {
        const result = await getStatus(jobId);
        if (result.state === "SUCCESS" || result.state === "FAILURE") {
          const finalStatus = result.state === "SUCCESS" ? "success" : "failed";
          setRepos((prev) => prev.map((r) => (r.repo_id === repoId ? { ...r, status: finalStatus } : r)));
          setBusyIds((prev) => { const next = new Set(prev); next.delete(repoId); return next; });
          pushToast({
            kind: result.state === "SUCCESS" ? "success" : "error",
            message: result.state === "SUCCESS"
              ? `${repoId} is ready.`
              : `Reingest of ${repoId} failed.`,
          });
          return;
        }
        if (polls >= MAX_REINGEST_POLLS) {
          setBusyIds((prev) => { const next = new Set(prev); next.delete(repoId); return next; });
          return;
        }
        setTimeout(tick, 2000);
      } catch (err) {
        setBusyIds((prev) => { const next = new Set(prev); next.delete(repoId); return next; });
        pushToast({ kind: "error", message: err.message || "Status check failed." });
      }
    }
    tick();
  }

  async function handleReingest(e, repoId) {
    e.stopPropagation();
    setError("");
    try {
      const result = await reingestRepo(repoId);
      setRepos((prev) => prev.map((r) => (r.repo_id === repoId ? { ...r, status: "queued" } : r)));
      pushToast({ kind: "info", message: `Reingest started for ${repoId}.` });
      pollStatus(result.job_id, repoId);
    } catch (err) {
      pushToast({ kind: "error", message: err.message || "Failed to start reingest." });
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
            // Spinner only for ingests WE kicked off this session. A queued
            // row from a prior session doesn't have a live stream behind
            // it -- show it as actionable ("click to retry") rather than
            // pretending it's running.
            const busy = busyIds.has(repo.repo_id);
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
