import { useEffect } from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { setNavigateToLogin } from "./lib/api";
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
  const { isAuthenticated, authChecked } = useAuth();
  // Don't render either the protected page OR a redirect until we've
  // verified the cookie -- otherwise a reload on /dashboard briefly
  // flashes /login before /refresh succeeds.
  if (!authChecked) {
    return (
      <p
        aria-live="polite"
        className="min-h-[calc(100vh-57px)] flex items-center justify-center font-mono text-sm text-muted loading-breathe"
      >
        checking session...
      </p>
    );
  }
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

// LoginGate: handles the three states on /login:
//  1. !authChecked                 -> render a breathe loader (no paint race).
//  2. authChecked && isAuthenticated -> <Navigate replace> to /dashboard in
//     the SAME commit (no useEffect, so the login form never paints).
//  3. authChecked && !isAuthenticated -> render the login form.
function LoginGate() {
  const { isAuthenticated, authChecked } = useAuth();
  if (!authChecked) {
    return (
      <p
        aria-live="polite"
        className="min-h-[calc(100vh-57px)] flex items-center justify-center font-mono text-sm text-muted loading-breathe"
      >
        checking session...
      </p>
    );
  }
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }
  return <Auth />;
}

function App() {
  const { isAuthenticated, authChecked, checkAuth } = useAuth();
  const navigate = useNavigate();
  // Mounts the theme hook so the class is applied + persisted on first load
  useTheme();

  // Register an in-app router redirect for authFetch's 401 fall-through.
  // Cleanup on unmount keeps the module-level binding from leaking into
  // a stale Router instance after HMR or remount.
  useEffect(() => {
    setNavigateToLogin(() => navigate("/login", { replace: true }));
    return () => setNavigateToLogin(null);
  }, [navigate]);

  // Runs the silent /refresh on mount so every page below sees
  // `authChecked` flip true exactly once. Done here (not per-route) so
  // a reload on /dashboard doesn't briefly flash /login before /refresh
  // resolves -- once checked, RequireAuth + LoginGate can both trust it.
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // While authCheck is in flight, default the catch-all to / for any
  // unrecognized URL -- sending an authenticated user to /dashboard
  // before /refresh resolves would trigger a redirect to /login flash.
  // Once authChecked flips, prefer /dashboard for authed users.
  const fallbackTarget = !authChecked ? "/" : isAuthenticated ? "/dashboard" : "/";

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="w-full px-8 py-4 flex items-center justify-between border-b border-rule">
        <PromptBar />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          {isAuthenticated && <LogoutButton />}
        </div>
      </header>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<LoginGate />} />
        <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
        <Route path="/ingest" element={<RequireAuth><Ingest /></RequireAuth>} />
        <Route path="/repos/:owner/:name/threads" element={<RequireAuth><ThreadList /></RequireAuth>} />
        <Route path="/repos/:owner/:name/threads/:threadId" element={<RequireAuth><Chat /></RequireAuth>} />
        <Route path="*" element={<Navigate to={fallbackTarget} replace />} />
      </Routes>
    </div>
  );
}

export default App;