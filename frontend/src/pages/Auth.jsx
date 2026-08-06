import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../lib/toast.jsx";
import { register, login as loginApi } from "../lib/api";
import { Button } from "../components/ui/button";

function Auth() {
  const { onLoginSuccess } = useAuth();
  const navigate = useNavigate();
  const { pushToast } = useToast();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState("login");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === "register") {
        await register(username, password);
        setMode("login");
        pushToast({ kind: "success", message: "Account created — log in to continue." });
        return;
      }
      // /login response carries both cookies via Set-Cookie headers.
      // We don't need to read the body -- flip isAuthenticated on, then
      // bounce to /dashboard. No need to re-run /refresh here: the
      // cookies are brand new, and re-rotating them would race with
      // the dashhboard's first request.
      await loginApi(username, password);
      onLoginSuccess();
      pushToast({ kind: "success", message: "Logged in." });
      navigate("/dashboard");
    } catch (err) {
      pushToast({ kind: "error", message: err.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-57px)] flex items-center justify-center px-4 bg-paper">
      <div className="w-full max-w-sm bg-elevated border border-rule rounded-lg p-8 shadow-xl">
        <p className="font-mono text-xs text-muted mb-1">
          <span className="text-accent">$</span> auth --mode {mode}
        </p>
        <h1 className="font-display text-3xl text-ink mb-6 tracking-tight">RepoSage</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="username" className="font-mono text-xs uppercase tracking-wide text-muted">
              username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className="mt-1 w-full bg-paper border border-rule rounded-md px-3 py-2 text-ink font-mono text-sm focus:outline-none focus:ring-2 focus:ring-accent-strong"
            />
          </div>
          <div>
            <label htmlFor="password" className="font-mono text-xs uppercase tracking-wide text-muted">
              password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              className="mt-1 w-full bg-paper border border-rule rounded-md px-3 py-2 text-ink font-mono text-sm focus:outline-none focus:ring-2 focus:ring-accent-strong"
            />
          </div>

          <Button type="submit" disabled={loading} className="w-full">
            {loading ? (mode === "login" ? "logging in..." : "registering...") : (mode === "login" ? "login" : "register")}
          </Button>
        </form>

        <Button
          variant="link"
          size="link"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
          className="mt-4 text-muted hover:text-accent"
        >
          {mode === "login" ? "need an account? register" : "have an account? login"}
        </Button>
      </div>
    </div>
  );
}

export default Auth;