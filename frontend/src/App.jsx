import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Auth from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Ingest from "./pages/Ingest";
import ThreadList from "./pages/ThreadList";
import Chat from "./pages/Chat";
import Landing from "./pages/Landing";
import LogoutButton from "./components/LogoutButton";
import PromptBar from "./components/PromptBar";
import ThemeToggle from "./components/ThemeToggle";
import { useTheme } from "./lib/useTheme";

function RequireAuth({ children }) {
  const { token } = useAuth();
  return token ? children : <Navigate to="/login" replace />;
}

function App() {
  const { token } = useAuth();
  const { pathname } = useLocation();
  // Mounts the theme hook so the class is applied + persisted on first load
  useTheme();

  // The landing route renders its own PromptBar inside the hero. To avoid
  // a duplicate, the global header on `/` is collapsed — the theme/logout
  // controls are surfaced by the Landing page itself.
  const onLanding = pathname === "/";

  return (
    <div className="min-h-screen bg-paper text-ink">
      {(
        <header className="w-full px-8 py-6 flex items-center justify-between border-b border-rule">
          <PromptBar />
          {token && (
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <LogoutButton />
            </div>
          )}
          {!token && <ThemeToggle />}
        </header>
      )}
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={token ? <Navigate to="/dashboard" replace /> : <Auth />} />
        <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
        <Route path="/ingest" element={<RequireAuth><Ingest /></RequireAuth>} />
        <Route path="/repos/:owner/:name/threads" element={<RequireAuth><ThreadList /></RequireAuth>} />
        <Route path="/repos/:owner/:name/threads/:threadId" element={<RequireAuth><Chat /></RequireAuth>} />
        <Route path="*" element={<Navigate to={token ? "/dashboard" : "/"} replace />} />
      </Routes>
    </div>
  );
}

export default App;