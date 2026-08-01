import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { register, login as loginApi } from "../lib/api";
import { Button } from "../components/ui/button";

function Auth() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [mode, setMode] = useState("login");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(""); setNotice(""); setLoading(true);
    try {
      if (mode === "register") {
        await register(username, password);
        setMode("login");
        setNotice("Registered — now log in.");
        return;
      }
      const result = await loginApi(username, password);
      login(result.access_token);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
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
            <label className="font-mono text-xs uppercase tracking-wide text-muted">
              username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="mt-1 w-full bg-paper border border-rule rounded-md px-3 py-2 text-ink font-mono text-sm focus:outline-none focus:ring-2 focus:ring-accent-strong"
            />
          </div>
          <div>
            <label className="font-mono text-xs uppercase tracking-wide text-muted">
              password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
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
          onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); setNotice(""); }}
          className="mt-4 text-muted hover:text-accent"
        >
          {mode === "login" ? "need an account? register" : "have an account? login"}
        </Button>

        {notice && <p className="mt-3 text-sm text-success">{notice}</p>}
        {error && <p className="mt-3 text-sm text-danger">{error}</p>}
      </div>
    </div>
  );
}

export default Auth;