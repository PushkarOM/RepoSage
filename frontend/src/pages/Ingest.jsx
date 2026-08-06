import { useState, useEffect } from "react";
import { startIngest, streamIngestStatus } from "../lib/api";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";

// Maps both legacy Celery states (PENDING/STARTED) and the lowercase
// status strings written by our own task. The SSE stream emits whichever
// the task produced -- consistent across both paths because we now
// always go through our task code that writes lowercase.
const STATE_COLOR = {
  queued: "bg-muted",
  pending: "bg-muted",
  PENDING: "bg-muted",
  running: "bg-accent",
  STARTED: "bg-accent",
  success: "bg-success",
  SUCCESS: "bg-success",
  failed: "bg-danger",
  error: "bg-danger",
  FAILURE: "bg-danger",
};

function Ingest() {
  const navigate = useNavigate();

  const [githubUrl, setGithubUrl] = useState("");
  const [jobId, setJobId] = useState(null);
  const [state, setState] = useState("");
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  // Synchronous re-entry guard: set on click before await so a fast double-click
  // can't fire the request twice while the server response is still in flight.
  const [submitting, setSubmitting] = useState(false);

  // Open the SSE stream for the current jobId. Cleanup closes the connection
  // -- EventSource otherwise retries forever on a server close, which would
  // be wrong for a terminal stream.
  useEffect(() => {
    if (!jobId) return undefined;
    const stop = streamIngestStatus(jobId, (evt) => {
      const next = (evt.state || "").toLowerCase();
      setState(next);
      setHistory((prev) => (prev[prev.length - 1] === next ? prev : [...prev, next]));
      if (next === "success") {
        // Use the latest jobId's repo_id by parsing the URL the user submitted.
        // Fall through to the threads page for the repo they just ingested.
        navigate(`/repos/${repoFromUrl(githubUrl)}/threads`);
      } else if (next === "failed" || next === "error") {
        setError(evt.detail || "Ingestion failed. Check the repo URL and try again.");
      }
    });
    return stop;
    // githubUrl is read inside the handler but we want a fresh handler when
    // the input changes (e.g. user typed a new URL after a failure). Closing
    // and reopening the stream on each keystroke is overkill; instead, capture
    // the URL via closure and let the existing stream keep running.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting || (state && state !== "failed" && state !== "error")) return;
    setError("");
    setSubmitting(true);
    // Reset the timeline so a corrected retry doesn't append onto the failed attempt.
    setHistory([]);
    setState("");
    try {
      const result = await startIngest(githubUrl);
      setJobId(result.job_id);
      setState("queued");
      setHistory((prev) => [...prev, "queued"]);
      // The useEffect above will pick up the new jobId and open the stream.
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  const locked = state && state !== "failed" && state !== "error";

  return (
    <div className="min-h-[calc(100vh-57px)] flex items-center justify-center px-4 bg-paper">
      <div className="w-full max-w-sm bg-elevated border border-rule rounded-lg p-8 shadow-xl">
        <p className="font-mono text-xs text-muted mb-1">
          <span className="text-accent">$</span> ingest
          {githubUrl ? ` ${githubUrl.split("/").slice(-2).join("/")}` : ""}
        </p>
        <h1 className="font-display text-2xl text-ink mb-6 tracking-tight">Ingest a repository</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="github-url" className="font-mono text-xs uppercase tracking-wide text-muted">
              github url
            </label>
            <input
              id="github-url"
              type="text"
              placeholder="https://github.com/owner/repo.git"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              disabled={locked || submitting}
              autoComplete="off"
              className="mt-1 w-full bg-paper border border-rule rounded-md px-3 py-2 text-ink font-mono text-sm placeholder:text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent-strong disabled:opacity-50"
            />
          </div>
          <Button type="submit" disabled={locked || submitting} className="w-full" aria-label="Start ingestion">
            {locked ? `${state}...` : submitting ? "starting..." : "ingest"}
          </Button>
        </form>

        {history.length > 0 && (
          <div className="mt-6" aria-live="polite">
            {history.map((s, i) => (
              <div key={i} className="flex items-start gap-3">
                <div className="flex flex-col items-center">
                  <div className={`w-2 h-2 rounded-full mt-1.5 ${STATE_COLOR[s] || "bg-muted"}`} aria-hidden="true" />
                  {i !== history.length - 1 && <div className="w-px flex-1 bg-rule my-1" aria-hidden="true" />}
                </div>
                <p className="font-mono text-sm text-ink pb-3">{s}</p>
              </div>
            ))}
          </div>
        )}

        {error && (
          <p role="alert" aria-live="polite" className="mt-3 text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}

// Derive "owner/repo" from a github URL. Used to navigate to the threads
// page on success; fails silently on malformed input (the user will see
// the 404 and can use the dashboard to find their repo).
function repoFromUrl(url) {
  if (!url) return "";
  const cleaned = url.replace(/\.git$/, "");
  const match = cleaned.match(/github\.com[/:]([^/]+\/[^/]+)/);
  return match ? match[1] : "";
}

export default Ingest;
