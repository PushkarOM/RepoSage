def test_ingest_requires_auth(client):
    """
    Regression test: /ingest previously shipped without its auth
    dependency and silently accepted unauthenticated requests. This
    test exists specifically so that mistake can't reappear unnoticed.
    """
    response = client.post("/ingest", json={"github_url": "https://github.com/example/repo.git"})
    assert response.status_code == 401


def test_status_requires_auth(client):
    response = client.get("/status/some-fake-job-id")
    assert response.status_code == 401


def test_chat_requires_auth(client):
    response = client.post("/chat", json={"job_id": "fake", "message": "hello"})
    assert response.status_code == 401


def test_ingest_succeeds_with_valid_token(client, monkeypatch, clear_rate_limit):
    """
    Mocks the Celery task so this test doesn't actually need Redis
    running or a real repo to clone -- we're testing that auth +
    routing work, not that ingestion itself works (that's covered
    by test_chunker.py and was verified manually end-to-end).

    `clear_rate_limit` zeroes the per-user ingest counter on the test
    Redis so a counter that survived a prior run can't 429 this test.
    """
    clear_rate_limit("ingest", "carol")

    client.post("/register", json={"username": "carol", "password": "testpass123"})
    # Login sets the httpOnly cookies on the TestClient jar; subsequent
    # requests attach them automatically. No Authorization header needed.
    client.post("/login", data={"username": "carol", "password": "testpass123"})

    class FakeTask:
        id = "fake-job-id-123"

    monkeypatch.setattr(
        "app.api.routes.ingest_repo_task.delay",
        lambda *args, **kwargs: FakeTask(),
    )

    response = client.post(
        "/ingest",
        json={"github_url": "https://github.com/example/repo.git"},
    )
    assert response.status_code == 200
    assert response.json()["job_id"] == "fake-job-id-123"
