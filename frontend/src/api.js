const API_BASE = import.meta.env.VITE_API_BASE;

async function handleResponse(response) {
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Request failed: ${response.status}`);
  }
  return response.json();
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
  const response = await fetch(`${API_BASE}/ingest`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ github_url: githubUrl }),
  });
  return handleResponse(response);
}

export async function getStatus(token, jobId) {
  const response = await fetch(`${API_BASE}/status/${jobId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse(response);
}

export async function sendChat(token, jobId, message) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ job_id: jobId, message }),
  });
  return handleResponse(response);
}
