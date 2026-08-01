import { useState, useRef, useEffect } from "react";
import { startIngest, getStatus } from "../lib/api";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";

const STATE_COLOR = {
  queued: "bg-muted",
  PENDING: "bg-muted",
  STARTED: "bg-accent",
  SUCCESS: "bg-success",
  FAILURE: "bg-danger",
};

function Ingest() {
  const { token } = useAuth();
  const navigate = useNavigate();

  const [githubUrl, setGithubUrl] = useState("");
  const [jobId, setJobId] = useState(null);
  const [state, setState] = useState("");
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  // Synchronous re-entry guard: set on click before await so a fast double-click
  // can't fire the request twice while the server response is still in flight.
  const [submitting, setSubmitting] = useState(false);
  const pollTimeoutRef = useRef(null);

  useEffect(() => {
    return () => clearTimeout(pollTimeoutRef.current);
  }, []);

  function logState(newState) {
    setState(newState);
    setHistory((prev) => (prev[prev.length - 1] === newState ? prev : [...prev, newState]));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting || (state && state !== "FAILURE")) return;
    setError("");
    setSubmitting(true);
    // Reset the timeline so a corrected retry doesn't append onto the failed attempt.
    setHistory([]);
    setState("");
    try {
      const result = await startIngest(token, githubUrl);
      setJobId(result.job_id);
      logState("queued");
      poll(result.job_id, result.repo_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function poll(id, repoId) {
    try {
      const result = await getStatus(token, id);
      logState(result.state);

      if (result.state === "SUCCESS") {
        navigate(`/repos/${repoId}/threads`);
      } else if (result.state === "FAILURE") {
        setError("Ingestion failed. Check the repo URL and try again.");
      } else {
        pollTimeoutRef.current = setTimeout(() => poll(id, repoId), 2000);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  const locked = state && state !== "FAILURE";

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
            {state && state !== "FAILURE" ? state.toLowerCase() + "..." : (submitting ? "starting..." : "ingest")}
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

export default Ingest;
