// All API URLs are relative -- the Vite dev server proxies /api/* to the
// FastAPI backend (see vite.config.js), and the prod deploy does the same
// at the edge. Single origin means httpOnly cookies set by /api/login ride
// on every subsequent /api/* request without any CORS dance.
const API_BASE = import.meta.env.VITE_API_BASE;

// `authFetch` is a plain function with no router context, so it can't
// call `useNavigate` directly. The App component registers a closure
// over its `navigate` instance via `setNavigateToLogin` so 401 fall-throughs
// route through React Router (no full reload) when a router is present.
// Falls back to `window.location.href` for code paths outside a Router
// (tests, anything that imports api.js before App mounts).
let navigateToLogin = null;
export function setNavigateToLogin(fn) {
  navigateToLogin = fn;
}

function redirectToLogin() {
  if (navigateToLogin) {
    navigateToLogin();
  } else {
    window.location.href = "/login";
  }
}

// Carries the HTTP status alongside the message so callers can branch on
// it (e.g. show a friendly toast for 429 vs. inline text for everything
// else). Plain `new Error(detail)` would lose the status -- the streaming
// endpoint doesn't return a response_model, so the catch path needs the
// original code to make any decision.
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function handleResponse(response) {
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    // FastAPI 422 sends detail as an array of {loc, msg, type} objects --
    // collapse to a readable string so it never reaches the UI as "[object Object]".
    let detail = errorBody.detail;
    if (Array.isArray(detail)) {
      detail = detail.map((e) => e.msg).join("; ");
    }
    throw new ApiError(detail || `Request failed: ${response.status}`, response.status);
  }
  return response.json();
}

// In-flight refresh Promise shared across all 401-retry paths. If five
// requests 401 at the same time, only ONE /refresh is issued -- the rest
// reuse the same Promise. Avoids the "thundering refresh" race where
// the first refresh rotates the token, then the second refresh fails
// because the cookie it relied on was already invalidated.
//
// CRITICAL: the assignment to refreshInFlight must be synchronous in the
// same tick as the null check. The previous implementation had an
// `if (!refreshInFlight) { refreshInFlight = ... }` pattern that LOOKED
// guarded but was not: two callers in the same microtask tick (e.g.
// React 18 StrictMode double-invoking the mount effect) both saw
// `refreshInFlight === null`, both fired /refresh, and the server
// rotated the token hash twice while the browser only kept ONE of the
// two Set-Cookie responses. The cookie's token and the DB hash drifted
// out of sync by one rotation, and every subsequent /refresh failed
// with "Invalid refresh token" -- the user-visible bug.
//
// Fix: assign the Promise synchronously before any await, then return it.
let refreshInFlight = null;

async function refreshTokens() {
  if (!refreshInFlight) {
    // Synchronously seed the slot so a second concurrent caller can't
    // observe `null` and create its own Promise. The body of the IIFE
    // is the only thing that resolves/rejects the shared Promise.
    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/refresh`, {
          method: "POST",
          credentials: "include",
        });
        if (!response.ok) {
          throw new ApiError("Refresh failed", response.status);
        }
        // Drain the body so the browser fully commits Set-Cookie BEFORE
        // we clear refreshInFlight -- otherwise the next caller could
        // race in with a request that races against the cookie write.
        await response.json();
      } finally {
        // Reset on settle so future 401s can trigger a fresh refresh.
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

export { refreshTokens };

async function authFetch(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    credentials: "include",
  });
  if (response.status !== 401) {
    return response;
  }

  // 401 -- try silent refresh. If we have no refresh cookie, or refresh
  // itself fails, fall through to redirect. The single-flight guard
  // (refreshInFlight) ensures only one /refresh fires even if multiple
  // authed requests 401 concurrently.
  try {
    await refreshTokens();
    // Re-issue the original request; cookies (including the new access
    // cookie set by /refresh) ride automatically with credentials:"include".
    const retryResponse = await fetch(url, { ...options, credentials: "include" });
    if (retryResponse.status !== 401) {
      return retryResponse;
    }
    // Retry itself 401'd -- the new cookie is already invalid. Bail.
  } catch {
    // refreshTokens threw -- refresh cookie is bad/expired.
  }

  redirectToLogin();
  throw new Error("Session expired");
}

export async function register(username, password) {
  const response = await fetch(`${API_BASE}/api/register`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return handleResponse(response);
}

export async function login(username, password) {
  // FastAPI's OAuth2PasswordRequestForm expects form-encoded data,
  // not JSON -- URLSearchParams produces the right content-type automatically.
  // Response sets both cookies (reposage_token, reposage_refresh) via
  // Set-Cookie headers; the body is just { message, username }.
  const body = new URLSearchParams({ username, password });
  const response = await fetch(`${API_BASE}/api/login`, {
    method: "POST",
    credentials: "include",
    body,
  });
  return handleResponse(response);
}

export async function logout() {
  // Server-side cookie deletion + DB-side refresh-token revocation.
  // Best-effort: even if the request fails (e.g. expired session), we
  // still redirect the user to /login.
  await fetch(`${API_BASE}/api/logout`, {
    method: "POST",
    credentials: "include",
  }).catch(() => {});
}

export async function startIngest(githubUrl) {
  const response = await authFetch(`${API_BASE}/api/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ github_url: githubUrl }),
  });
  return handleResponse(response);
}

export async function getStatus(repoId) {
  const response = await authFetch(`${API_BASE}/api/status/${repoId}`);
  return handleResponse(response);
}

/**
 * Server-Sent Events consumer for ingest progress.
 *
 * The browser EventSource API doesn't allow custom headers, but it does
 * send cookies with `withCredentials: true` -- and the dev Vite proxy /
 * prod edge makes the request same-origin, so the httpOnly access cookie
 * rides automatically. No `?token=` query string needed (which would
 * expose the token in the URL and the access log).
 *
 * `onEvent` is called with each parsed `{ job_id, state, detail }` payload.
 * On stream error (network drop, 401/404 from the server), we surface a
 * final `{ state: "error" }` event and close -- EventSource auto-reconnects
 * by default, which is the wrong behaviour for a terminal stream.
 *
 * Returns a `stop()` function so callers can clean up on unmount.
 */
export function streamIngestStatus(jobId, onEvent, { signal } = {}) {
  const url = `${API_BASE}/api/ingest/stream/${jobId}`;
  const es = new EventSource(url, { withCredentials: true });

  es.onmessage = (e) => {
    try {
      onEvent(JSON.parse(e.data));
    } catch {
      // Malformed payload -- ignore rather than crash the stream.
    }
  };
  es.onerror = () => {
    onEvent({ job_id: jobId, state: "error", detail: "stream disconnected" });
    es.close();
  };
  if (signal) {
    const onAbort = () => es.close();
    signal.addEventListener("abort", onAbort);
  }
  return () => es.close();
}

export async function sendChat(repoId, message) {
  const response = await authFetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_id: repoId, message }),
  });
  return handleResponse(response);
}

export async function streamChat(repoId, message, threadId, onChunk) {
  const response = await authFetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_id: repoId, message, thread_id: threadId }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    let detail = errorBody.detail;
    if (Array.isArray(detail)) {
      detail = detail.map((e) => e.msg).join("; ");
    }
    throw new ApiError(detail || `Request failed: ${response.status}`, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onChunk(decoder.decode(value, { stream: true }));
  }
}

export async function listRepos() {
  const response = await authFetch(`${API_BASE}/api/repos`);
  return handleResponse(response);
}

export async function reingestRepo(repoId) {
  const response = await authFetch(`${API_BASE}/api/repos/reingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_id: repoId }),
  });
  return handleResponse(response);
}


export async function listThreads(repoId) {
  const [owner, name] = repoId.split("/");
  const response = await authFetch(`${API_BASE}/api/repos/${owner}/${name}/threads`);
  return handleResponse(response);
}

export async function createThread(repoId) {
  const response = await authFetch(`${API_BASE}/api/threads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_id: repoId }),
  });
  return handleResponse(response);
}

export async function autoTitleThread(threadId, message) {
  const response = await authFetch(`${API_BASE}/api/threads/${threadId}/auto-title`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  return handleResponse(response);
}

export async function getThreadMessages(threadId) {
  const response = await authFetch(`${API_BASE}/api/threads/${threadId}/messages`);
  return handleResponse(response);
}

export async function renameThread(threadId, title) {
  const response = await authFetch(`${API_BASE}/api/threads/${threadId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  return handleResponse(response);
}

export function getGithubConnectUrl() {
  // Top-level navigation -- the access cookie rides because SameSite=Lax
  // includes top-level navigations in its cookie-attach policy. No
  // `?token=` query string needed.
  return `${API_BASE}/api/auth/github/login`;
}

export async function getGithubStatus() {
  const response = await authFetch(`${API_BASE}/api/auth/github/status`);
  return handleResponse(response);
}