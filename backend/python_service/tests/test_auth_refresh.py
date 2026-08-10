"""Regression coverage for POST /auth/refresh.

Comparing an aware `now` (datetime.now(timezone.utc)) against
UserSession.expires_at — a naive DateTime column, since it has no
timezone=True — raised "can't compare offset-naive and offset-aware
datetimes", an unhandled Python TypeError that FastAPI turned into a raw
500 on every single refresh attempt. This went unnoticed because no
frontend ever actually called the endpoint: the refresh_token returned by
/auth/login was read off the response and discarded everywhere. Once the
web apps' api-client started using it, every refresh attempt broke.
"""


def test_refresh_issues_new_tokens_and_rotates_old_one(client):
    client.post("/api/v1/auth/register", json={
        "username": "refresh_test_user", "email": "refresh_test@x.in",
        "password": "strongpass123", "full_name": "Refresh Test", "role": "PATIENT",
    })
    login_res = client.post("/api/v1/auth/login", data={
        "username": "refresh_test_user", "password": "strongpass123",
    })
    assert login_res.status_code == 200
    old_refresh = login_res.json()["refresh_token"]

    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_res.status_code == 200, refresh_res.text
    body = refresh_res.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["refresh_token"] != old_refresh

    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "refresh_test_user"

    # The old refresh token was rotated/revoked by the call above — reusing
    # it must fail cleanly with 401, not crash.
    reuse_res = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse_res.status_code == 401


def test_refresh_rejects_garbage_token_cleanly(client):
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert res.status_code == 401
