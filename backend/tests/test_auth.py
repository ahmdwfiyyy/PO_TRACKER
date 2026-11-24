from tests.conftest import PASSWORD, login


def test_login_returns_token_and_user(client, world):
    res = client.post("/api/auth/login", json={"email": "A@Test.com ", "password": PASSWORD})
    assert res.status_code == 200
    body = res.json()
    assert body["token"]
    assert body["user"]["role"] == "vendor"
    assert body["user"]["vendor_name"] == "Vendor A"


def test_wrong_password(client, world):
    res = client.post("/api/auth/login", json={"email": "a@test.com", "password": "nope"})
    assert res.status_code == 401


def test_lockout_after_five_failures(client, world):
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "a@test.com", "password": "nope"})
    res = client.post("/api/auth/login", json={"email": "a@test.com", "password": PASSWORD})
    assert res.status_code == 429


def test_me_requires_token(client, world):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    assert client.get("/api/auth/me", headers=world.purchasing).json()["role"] == "purchasing"


def test_deactivated_user_loses_access_immediately(client, world):
    me = client.get("/api/auth/me", headers=world.vendor_a).json()
    res = client.patch(f"/api/users/{me['id']}", json={"is_active": False}, headers=world.purchasing)
    assert res.status_code == 200
    assert client.get("/api/auth/me", headers=world.vendor_a).status_code == 401
    assert client.post("/api/auth/login", json={"email": "a@test.com", "password": PASSWORD}).status_code == 403


def test_change_password(client, world):
    res = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "NewPassword9"},
        headers=world.receiving,
    )
    assert res.status_code == 204
    assert login(client, "r@test.com", "NewPassword9")
