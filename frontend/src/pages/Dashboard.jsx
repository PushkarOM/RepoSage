import { useState, useEffect } from "react";
import { listRepos } from "../lib/api";     

function Dashboard({ token, onSelectRepo, onNewIngest }) {
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listRepos(token)
      .then(setRepos)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="min-h-screen bg-(--color-ink) px-4 py-8">
      <div className="w-full max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="font-mono-ui text-lg text-(--color-bone)">$ your repos</h1>
          <button
            onClick={onNewIngest}
            className="bg-(--color-amber) text-(--color-ink) font-mono-ui text-sm font-medium rounded-md px-4 py-2 hover:brightness-110 transition"
          >
            + ingest new
          </button>
        </div>

        {loading && <p className="font-mono-ui text-sm text-(--color-steel)">loading...</p>}
        {error && <p className="text-sm text-(--color-diff-remove)">{error}</p>}

        {!loading && repos.length === 0 && (
          <p className="font-mono-ui text-sm text-(--color-steel)">
            // no repos ingested yet -- click "ingest new" to get started
          </p>
        )}

        <div className="space-y-2">
          {repos.map((repo) => (
            <button
              key={repo.id}
              onClick={() => repo.status === "success" && onSelectRepo(repo.job_id)}
              disabled={repo.status !== "success"}
              className="w-full text-left bg-(--color-slate) border border-white/5 rounded-lg px-4 py-3 hover:border-(--color-amber)/50 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono-ui text-sm text-(--color-bone)">{repo.repo_id}</span>
                <span
                  className={`font-mono-ui text-xs px-2 py-0.5 rounded ${
                    repo.status === "success"
                      ? "text-(--color-diff-add)"
                      : repo.status === "failed"
                      ? "text-(--color-diff-remove)"
                      : "text-(--color-steel)"
                  }`}
                >
                  {repo.status}
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
