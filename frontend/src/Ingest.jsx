import { useState, useRef, useEffect } from "react";
import { startIngest, getStatus } from "./api";

const STATE_COLOR = {
  queued: "bg-(--color-steel)",
  PENDING: "bg-(--color-steel)",
  STARTED: "bg-(--color-amber)",
  SUCCESS: "bg-(--color-diff-add)",
  FAILURE: "bg-(--color-diff-remove)",
};

function Ingest({ token, onIngestComplete }) {
  const [githubUrl, setGithubUrl] = useState("");
  const [jobId, setJobId] = useState(null);
  const [state, setState] = useState("");
  const [history, setHistory] = useState([]); // ordered log of distinct states seen
  const [error, setError] = useState("");
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
    setError("");
    try {
      const result = await startIngest(token, githubUrl);
      setJobId(result.job_id);
      logState("queued");
      poll(result.job_id);
    } catch (err) {
      setError(err.message);
    }
  }

  async function poll(id) {
    try {
      const result = await getStatus(token, id);
      logState(result.state);

      if (result.state === "SUCCESS") {
        onIngestComplete(id);
      } else if (result.state === "FAILURE") {
        setError("Ingestion failed. Check the repo URL and try again.");
      } else {
        pollTimeoutRef.current = setTimeout(() => poll(id), 2000);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  const locked = state && state !== "FAILURE";

  return (
    <div className="min-h-screen flex items-center justify-center bg-(--color-ink) px-4">
      <div className="w-full max-w-sm bg-(--color-slate) border border-white/5 rounded-lg p-8 shadow-xl">
        <p className="font-mono-ui text-xs text-(--color-amber) mb-1">
          $ ingest {githubUrl ? `--repo ${githubUrl.split("/").slice(-2).join("/")}` : ""}
        </p>
        <h1 className="font-mono-ui text-lg text-(--color-bone) mb-6">Ingest a repository</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="font-mono-ui text-xs uppercase tracking-wide text-(--color-steel)">
              github url
            </label>
            <input
              type="text"
              placeholder="https://github.com/owner/repo.git"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              disabled={locked}
              className="mt-1 w-full bg-(--color-ink) border border-white/10 rounded-md px-3 py-2 text-(--color-bone) text-sm placeholder:text-(--color-steel)/50 focus:outline-none focus:ring-2 focus:ring-(--color-amber) disabled:opacity-50"
            />
          </div>
          <button
            type="submit"
            disabled={locked}
            className="w-full bg-(--color-amber) text-(--color-ink) font-mono-ui text-sm font-medium rounded-md py-2 hover:brightness-110 transition disabled:opacity-50 disabled:hover:brightness-100"
          >
            ingest
          </button>
        </form>

        {history.length > 0 && (
          <div className="mt-6">
            {history.map((s, i) => (
              <div key={i} className="flex items-start gap-3">
                <div className="flex flex-col items-center">
                  <div className={`w-2 h-2 rounded-full mt-1.5 ${STATE_COLOR[s] || "bg-(--color-steel)"}`} />
                  {i !== history.length - 1 && <div className="w-px flex-1 bg-white/10 my-1" />}
                </div>
                <p className="font-mono-ui text-sm text-(--color-bone) pb-3">{s}</p>
              </div>
            ))}
          </div>
        )}

        {error && <p className="mt-3 text-sm text-(--color-diff-remove)">{error}</p>}
      </div>
    </div>
  );
}

export default Ingest;
