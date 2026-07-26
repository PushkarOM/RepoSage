import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { register, login as loginApi } from "../lib/api";

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
    <div className="min-h-screen flex items-center justify-center bg-(--color-ink) px-4">
      <div className="w-full max-w-sm bg-(--color-slate) border border-white/5 rounded-lg p-8 shadow-xl">
        <p className="font-mono-ui text-xs text-(--color-amber) mb-1">
          $ auth --mode {mode}
        </p>
        <h1 className="font-mono-ui text-lg text-[(--color-bone) mb-6">RepoSage</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="font-mono-ui text-xs uppercase tracking-wide text-(--color-steel)">
              username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="mt-1 w-full bg-(--color-ink) border border-white/10 rounded-md px-3 py-2 text-[(--color-bone) text-sm focus:outline-none focus:ring-2 focus:ring-(--color-amber)"
            />
          </div>
          <div>
            <label className="font-mono-ui text-xs uppercase tracking-wide text-(--color-steel)">
              password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full bg-(--color-ink) border border-white/10 rounded-md px-3 py-2 text-[(--color-bone) text-sm focus:outline-none focus:ring-2 focus:ring-(--color-amber)"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-(--color-amber) text-(--color-ink) font-mono-ui text-sm font-medium rounded-md py-2 hover:brightness-110 transition disabled:opacity-50"
          >
            {loading ? (mode === "login" ? "logging in..." : "registering...") : (mode === "login" ? "login" : "register")}
          </button>
        </form>

        <button
          className="mt-4 text-xs text-(--color-steel) hover:text-(--color-amber) transition"
          onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); setNotice(""); }}
        >
          {mode === "login" ? "need an account? register" : "have an account? login"}
        </button>

        {notice && <p className="mt-3 text-sm text-(--color-diff-add)">{notice}</p>}
        {error && <p className="mt-3 text-sm text-(--color-diff-remove)">{error}</p>}
      </div>
    </div>
  );
}

export default Auth;
