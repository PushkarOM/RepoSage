const API_BASE = import.meta.env.VITE_API_BASE;

function redirectToLogin() {
  localStorage.removeItem("reposage_token");
  window.location.href = "/login";
}

async function handleResponse(response) {
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

async function authFetch(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 401) {
    redirectToLogin();
    throw new Error("Session expired");
  }
  return response;
}

export async function register(username, password) {
  const response = await fetch(`${API_BASE}/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return handleResponse(response);
}

export async function login(username, password) {
  // FastAPI's OAuth2PasswordRequestForm expects form-encoded data,
  // not JSON -- URLSearchParams produces the right content-type automatically.
  const body = new URLSearchParams({ username, password });
  const response = await fetch(`${API_BASE}/login`, { method: "POST", body });
  return handleResponse(response);
}

export async function startIngest(token, githubUrl) {
  const response = await authFetch(`${API_BASE}/ingest`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ github_url: githubUrl }),
  });
  return handleResponse(response);
}

export async function getStatus(token, repoId) {
  const response = await authFetch(`${API_BASE}/status/${repoId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse(response);
}

export async function sendChat(token, repoId, message) {
  const response = await authFetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ repo_id: repoId, message }),
  });
  return handleResponse(response);
}

export async function streamChat(token, repoId, message, threadId, onChunk) {
  const response = await authFetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ repo_id: repoId, message, thread_id: threadId }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onChunk(decoder.decode(value, { stream: true }));
  }
}

export async function listRepos(token) {
  const response = await authFetch(`${API_BASE}/repos`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse(response);
}

export async function reingestRepo(token, repoId) {
  const response = await authFetch(`${API_BASE}/repos/reingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ repo_id: repoId }),
  });
  return handleResponse(response);
}


export async function listThreads(token, repoId) {
  const [owner, name] = repoId.split("/");
  const response = await authFetch(`${API_BASE}/repos/${owner}/${name}/threads`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse(response);
}

export async function createThread(token, repoId) {
  const response = await authFetch(`${API_BASE}/threads`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ repo_id: repoId }),
  });
  return handleResponse(response);
}

export async function autoTitleThread(token, threadId, message) {
  const response = await authFetch(`${API_BASE}/threads/${threadId}/auto-title`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ message }),
  });
  return handleResponse(response);
}

export async function renameThread(token, threadId, title) {
  const response = await authFetch(`${API_BASE}/threads/${threadId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ title }),
  });
  return handleResponse(response);
}

