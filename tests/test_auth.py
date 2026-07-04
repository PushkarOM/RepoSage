def test_register_creates_user(client):
    response = client.post("/register", json={"username": "alice", "password": "testpass123"})
    assert response.status_code == 201


def test_register_duplicate_username_fails(client):
    client.post("/register", json={"username": "alice", "password": "testpass123"})
    response = client.post("/register", json={"username": "alice", "password": "different"})
    assert response.status_code == 400


def test_login_with_correct_credentials_succeeds(client):
    client.post("/register", json={"username": "bob", "password": "testpass123"})
    response = client.post("/login", data={"username": "bob", "password": "testpass123"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_wrong_password_fails(client):
    client.post("/register", json={"username": "bob", "password": "testpass123"})
    response = client.post("/login", data={"username": "bob", "password": "wrongpassword"})
    assert response.status_code == 401
