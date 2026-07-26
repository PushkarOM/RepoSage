def test_reingest_requires_auth(client):
    response = client.post("/repos/reingest", json={"repo_id": "owner/repo"})
    assert response.status_code == 401


def test_list_threads_requires_auth(client):
    response = client.get("/repos/owner/repo/threads")
    assert response.status_code == 401


def test_create_thread_requires_auth(client):
    response = client.post("/threads", json={"repo_id": "owner/repo"})
    assert response.status_code == 401


def test_thread_messages_requires_auth(client):
    response = client.get("/threads/some-thread-id/messages")
    assert response.status_code == 401


def test_ingest_upserts_not_duplicates(client, monkeypatch):
    """
    Regression test for the job_id/repo_id collision bug found this
    session: re-ingesting the same repo must update the existing
    ingested_repos row, not create a second one. A duplicate would mean
    the dashboard shows the repo twice and/or violates the unique
    constraint on (user_id, repo_id) outright.
    """
    client.post("/register", json={"username": "dana", "password": "testpass123"})
    login_resp = client.post("/login", data={"username": "dana", "password": "testpass123"})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    call_count = {"n": 0}

    class FakeTask:
        def __init__(self):
            call_count["n"] += 1
            self.id = f"fake-job-{call_count['n']}"

    monkeypatch.setattr("app.api.routes.ingest_repo_task.delay", lambda url: FakeTask())

    url = "https://github.com/owner/repo.git"
    r1 = client.post("/ingest", json={"github_url": url}, headers=headers)
    r2 = client.post("/ingest", json={"github_url": url}, headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["repo_id"] == r2.json()["repo_id"]

    repos_resp = client.get("/repos", headers=headers)
    matching = [r for r in repos_resp.json() if r["repo_id"] == r1.json()["repo_id"]]
    assert len(matching) == 1  # exactly one row, not two
