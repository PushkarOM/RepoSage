import { useState } from "react";
import Auth from "./Auth";
import Ingest from "./Ingest";
import Chat from "./Chat";

function App() {
  const [token, setToken] = useState(null);
  const [jobId, setJobId] = useState(null);

  function handleLogout() {
    setToken(null);
    setJobId(null);
  }

  if (!token) {
    return <Auth onLogin={setToken} />;
  }

  return (
    <div className="relative">
      <button
        onClick={handleLogout}
        className="fixed top-4 right-4 z-10 font-mono-ui text-xs text-(--color-steel) hover:text-(--color-amber) border border-white/10 rounded-md px-3 py-1.5 bg-(--color-slate) transition"
      >
        $ logout
      </button>

      {!jobId ? (
        <Ingest token={token} onIngestComplete={setJobId} />
      ) : (
        <Chat token={token} jobId={jobId} />
      )}
    </div>
  );
}

export default App;
