"""Signing in with an email address, the way people actually type one."""


def _register(client, username, email, password="LoginPass123!"):
    res = client.post("/api/v1/auth/register", json={
        "username": username, "email": email, "password": password,
        "full_name": "Email Login", "role": "PATIENT",
    })
    assert res.status_code == 200, res.text
    return password


def _login(client, identifier, password):
    return client.post(
        "/api/v1/auth/login",
        data={"username": identifier, "password": password},
    )


def test_email_login_tolerates_the_space_a_phone_keyboard_adds(client):
    """Phone keyboards append a space after an autocompleted word, and
    browser autofill sometimes does too. The login field is a raw form
    string rather than an EmailStr, so it was never trimmed, and a correct
    password came back as "Incorrect username or password"."""
    password = _register(client, "email_space_user", "space.user@example.com")

    for typed in (
        "space.user@example.com",
        "space.user@example.com ",
        " space.user@example.com",
        "  SPACE.USER@EXAMPLE.COM  ",
        "email_space_user ",
    ):
        res = _login(client, typed, password)
        assert res.status_code == 200, f"{typed!r}: {res.text}"
        assert res.json()["access_token"]


def test_email_login_still_rejects_a_wrong_password(client):
    _register(client, "email_wrong_pw", "wrong.pw@example.com")
    assert _login(client, "wrong.pw@example.com ", "NotThePassword1!").status_code == 401


def test_the_same_email_cannot_register_twice_in_different_case(client):
    """Login finds an account by lower(email). If two accounts could share
    an email differing only in case, that lookup would pick one of them
    arbitrarily and reject the other's correct password."""
    _register(client, "email_case_first", "Case.Owner@example.com")
    res = client.post("/api/v1/auth/register", json={
        "username": "email_case_second", "email": "case.owner@example.com",
        "password": "LoginPass123!", "full_name": "Second", "role": "PATIENT",
    })
    assert res.status_code == 400, res.text
    assert "Email already registered" in res.text
