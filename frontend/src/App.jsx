import { useState } from "react";

import Auth from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Ingest from "./pages/Ingest";
import Chat from "./pages/Chat";

function App() {
  const [token, setToken] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [view, setView] = useState("dashboard"); // "dashboard" | "ingest" | "chat"

  function handleLogout() {
    setToken(null);
    setJobId(null);
    setView("dashboard");
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

      {view === "dashboard" && (
        <Dashboard
          token={token}
          onSelectRepo={(id) => { setJobId(id); setView("chat"); }}
          onNewIngest={() => setView("ingest")}
        />
      )}
      {view === "ingest" && (
        <Ingest token={token} onIngestComplete={(id) => { setJobId(id); setView("chat"); }} />
      )}
      {view === "chat" && <Chat token={token} jobId={jobId} />}
    </div>
  );
}

export default App;
