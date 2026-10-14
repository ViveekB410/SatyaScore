"""Accounts, sessions, CSRF guard and per-user history (member3_backend/auth.py).
A minimal app is built around the auth module, so no model or corpus loads."""
import sqlite3
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from member3_backend import auth

ORIGIN = "http://localhost:5173"
GOOD = {"Origin": ORIGIN}
PASSWORD = "correct horse battery"


@pytest.fixture
def client(tmp_path):
    auth.set_db_path(tmp_path / "test.db")
    for w in (auth._login_fail_account, auth._login_fail_ip, auth._register_ip,
              auth._forgot_ip, auth._forgot_email, auth._reset_fail_email):
        w._hits.clear()
    app = FastAPI()
    auth.install(app, [ORIGIN])
    return TestClient(app)


def register(client, email="asha@example.com", password=PASSWORD, name="Asha"):
    return client.post("/auth/register", json={"name": name, "email": email, "password": password}, headers=GOOD)


def test_register_signs_in_with_an_httponly_cookie_and_stores_no_plain_password(client, tmp_path):
    r = register(client)
    assert r.status_code == 201
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/auth/me").json()["user"]["email"] == "asha@example.com"
    con = sqlite3.connect(tmp_path / "test.db")
    stored = con.execute("SELECT password_hash FROM users").fetchone()[0]
    tokens = [row[0] for row in con.execute("SELECT token_hash FROM sessions")]
    assert stored.startswith("scrypt$") and PASSWORD not in stored
    assert client.cookies.get(auth.SESSION_COOKIE) not in tokens  # only the hash is stored


def test_registration_validates_input(client):
    assert register(client, password="short").status_code == 422
    assert register(client, email="not-an-email").status_code == 422
    assert register(client, name="   ").status_code == 422
    assert register(client).status_code == 201
    assert register(client, email="ASHA@example.com ").status_code == 409  # emails are case-insensitive


def test_login_does_not_reveal_whether_an_account_exists(client):
    register(client)
    client.post("/auth/logout", headers=GOOD)
    wrong = client.post("/auth/login", json={"email": "asha@example.com", "password": "x" * 12}, headers=GOOD)
    unknown = client.post("/auth/login", json={"email": "nobody@example.com", "password": "x" * 12}, headers=GOOD)
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    ok = client.post("/auth/login", json={"email": "Asha@Example.com", "password": PASSWORD}, headers=GOOD)
    assert ok.status_code == 200 and ok.json()["user"]["name"] == "Asha"


def test_repeated_failed_logins_are_throttled(client):
    register(client)
    body = {"email": "asha@example.com", "password": "wrong password!"}
    codes = [client.post("/auth/login", json=body, headers=GOOD).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429
    # even the right password is refused while throttled
    right = client.post("/auth/login", json={**body, "password": PASSWORD}, headers=GOOD)
    assert right.status_code == 429 and "Retry-After" in right.headers


def test_logout_kills_the_session_server_side(client):
    register(client)
    token = client.cookies.get(auth.SESSION_COOKIE)
    assert client.post("/auth/logout", headers=GOOD).status_code == 204
    client.cookies.set(auth.SESSION_COOKIE, token)  # replay the old cookie
    assert client.get("/auth/me").json()["user"] is None


def test_expired_session_is_rejected(client, tmp_path):
    register(client)
    con = sqlite3.connect(tmp_path / "test.db")
    con.execute("UPDATE sessions SET expires_at = ?", (time.time() - 1,))
    con.commit()
    assert client.get("/auth/me").json()["user"] is None


def test_cross_site_requests_with_the_session_cookie_are_refused(client):
    register(client)
    evil = {"Origin": "https://evil.example"}
    assert client.post("/auth/logout", headers=evil).status_code == 403
    assert client.post("/auth/logout").status_code == 403  # cookie but no Origin
    assert client.post("/auth/login", json={"email": "a@b.co", "password": "x"}, headers=evil).status_code == 403
    assert client.get("/auth/me").json()["user"] is not None  # still signed in


def test_history_is_private_to_its_owner(client):
    register(client)
    me = client.get("/auth/me").json()["user"]
    result = {"claims": [{"verdict": "Verified"}, {"verdict": "Hallucinated"}], "document": {"verdict": "Hallucinated"},
              "processing_time_ms": 12.0}
    aid = auth.save_analysis(me["id"], "पेरिस फ्रांस की राजधानी है।\nMore.", "hi", result)

    listed = client.get("/history").json()["entries"]
    assert [(e["id"], e["total_claims"], e["flagged_count"], e["preview"]) for e in listed] == [
        (aid, 2, 1, "पेरिस फ्रांस की राजधानी है।")]
    assert client.get("/history", params={"language": "en"}).json()["entries"] == []
    assert len(client.get("/history", params={"q": "फ्रांस"}).json()["entries"]) == 1
    assert client.get(f"/history/{aid}").json()["document"]["verdict"] == "Hallucinated"

    # another user can neither see nor delete it
    client.post("/auth/logout", headers=GOOD)
    register(client, email="ravi@example.com", name="Ravi")
    assert client.get("/history").json()["entries"] == []
    assert client.get(f"/history/{aid}").status_code == 404
    assert client.delete(f"/history/{aid}", headers=GOOD).status_code == 404

    client.post("/auth/logout", headers=GOOD)
    assert client.get("/history").status_code == 401  # signed out


def test_owner_can_delete_and_responses_are_not_cached(client):
    register(client)
    me = client.get("/auth/me").json()["user"]
    aid = auth.save_analysis(me["id"], "Text.", "en", {"claims": []})
    r = client.delete(f"/history/{aid}", headers=GOOD)
    assert r.status_code == 204
    assert client.get("/history").json()["entries"] == []
    h = client.get("/history").headers
    assert h["Cache-Control"] == "no-store" and h["X-Content-Type-Options"] == "nosniff"


def test_password_hash_round_trip():
    stored = auth.hash_password("a long enough password")
    assert auth.verify_password("a long enough password", stored)
    assert not auth.verify_password("a long enough passworD", stored)
    assert not auth.verify_password("x", "garbage")

# --- changing and resetting the password -----------------------------------------------

NEW = "a brand new passphrase"


def login(client, password, email="asha@example.com"):
    return client.post("/auth/login", json={"email": email, "password": password}, headers=GOOD)


def test_change_password_needs_the_current_one_and_signs_out_other_devices(client):
    register(client)
    other = client.cookies.get(auth.SESSION_COOKIE)  # a second device holding the old session
    bad = client.post("/auth/change-password", json={"current_password": "wrong password!", "new_password": NEW},
                      headers=GOOD)
    assert bad.status_code == 401
    short = client.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": "short"},
                        headers=GOOD)
    assert short.status_code == 422
    ok = client.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": NEW}, headers=GOOD)
    assert ok.status_code == 200 and client.get("/auth/me").json()["user"]["email"] == "asha@example.com"
    client.cookies.set(auth.SESSION_COOKIE, other)
    assert client.get("/auth/me").json()["user"] is None  # the old session no longer works
    assert login(client, PASSWORD).status_code == 401 and login(client, NEW).status_code == 200


def test_change_password_requires_sign_in_and_a_same_site_request(client):
    assert client.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": NEW},
                       headers=GOOD).status_code == 401
    register(client)
    cross = client.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": NEW},
                        headers={"Origin": "https://evil.example"})
    assert cross.status_code == 403


def test_reset_code_is_one_time_expires_and_is_stored_only_as_a_hash(client, tmp_path):
    register(client)
    client.post("/auth/logout", headers=GOOD)
    assert auth.create_reset_code("nobody@example.com") is None
    code = auth.create_reset_code("ASHA@example.com")
    stored = sqlite3.connect(tmp_path / "test.db").execute("SELECT code_hash FROM password_resets").fetchone()[0]
    assert code not in stored
    body = {"email": "asha@example.com", "code": code.lower(), "new_password": NEW}  # case-insensitive code
    assert client.post("/auth/reset-password", json=body, headers=GOOD).status_code == 200
    assert client.get("/auth/me").json()["user"]["email"] == "asha@example.com"
    assert client.post("/auth/reset-password", json=body, headers=GOOD).status_code == 400  # used once only
    assert login(client, NEW).status_code == 200
    late = auth.create_reset_code("asha@example.com")
    con = sqlite3.connect(tmp_path / "test.db")
    con.execute("UPDATE password_resets SET expires_at = ?", (time.time() - 1,))
    con.commit()
    expired = client.post("/auth/reset-password", json={**body, "code": late}, headers=GOOD)
    assert expired.status_code == 400


def test_wrong_reset_codes_reveal_nothing_and_are_throttled(client):
    register(client)
    a = client.post("/auth/reset-password", json={"email": "asha@example.com", "code": "AAAAAA-BBBBBB-CCCCCC",
                                                 "new_password": NEW}, headers=GOOD)
    b = client.post("/auth/reset-password", json={"email": "nobody@example.com", "code": "AAAAAA-BBBBBB-CCCCCC",
                                                 "new_password": NEW}, headers=GOOD)
    assert a.status_code == b.status_code == 400 and a.json() == b.json()
    codes = [client.post("/auth/reset-password", json={"email": "asha@example.com", "code": "WRONG",
                                                       "new_password": NEW}, headers=GOOD).status_code
             for _ in range(5)]
    assert codes[-1] == 429


# --- reset by email (member3_backend/mailer.py) -----------------------------------------

@pytest.fixture
def outbox(monkeypatch):
    """Reset emails sent, captured synchronously (no thread, no mail server)."""
    sent = []

    class Now:  # runs the background sender at once
        def __init__(self, target, args=(), daemon=None):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    from member3_backend import mailer
    monkeypatch.setattr(auth.threading, "Thread", Now)
    monkeypatch.setattr(mailer, "send_reset_code", lambda to, code, minutes: sent.append((to, code)))
    return sent


def test_forgot_password_answers_the_same_and_emails_a_six_digit_code_only_to_real_accounts(client, outbox):
    register(client)
    client.post("/auth/logout", headers=GOOD)
    known = client.post("/auth/forgot-password", json={"email": "Asha@Example.com"}, headers=GOOD)
    unknown = client.post("/auth/forgot-password", json={"email": "nobody@example.com"}, headers=GOOD)
    assert known.status_code == unknown.status_code == 200 and known.json() == unknown.json()
    assert len(outbox) == 1 and outbox[0][0] == "asha@example.com"
    code = outbox[0][1]
    assert len(code) == 6 and code.isdigit()
    body = {"email": "asha@example.com", "code": f" {code[:3]} {code[3:]} ", "new_password": NEW}  # spaces are fine
    assert client.post("/auth/reset-password", json=body, headers=GOOD).status_code == 200
    assert login(client, NEW).status_code == 200


def test_a_new_code_replaces_the_old_one_and_requests_are_limited(client, outbox):
    register(client)
    for _ in range(2):
        client.post("/auth/forgot-password", json={"email": "asha@example.com"}, headers=GOOD)
    first, second = outbox[0][1], outbox[1][1]
    if first != second:
        old = client.post("/auth/reset-password", json={"email": "asha@example.com", "code": first, "new_password": NEW},
                          headers=GOOD)
        assert old.status_code == 400  # only the newest code works
    client.post("/auth/forgot-password", json={"email": "asha@example.com"}, headers=GOOD)
    assert client.post("/auth/forgot-password", json={"email": "asha@example.com"}, headers=GOOD).status_code == 429
    assert client.post("/auth/forgot-password", json={"email": "not-an-email"}, headers=GOOD).status_code == 422


def test_five_wrong_codes_cancel_the_emailed_code_even_from_other_networks(client, outbox):
    register(client)
    client.post("/auth/forgot-password", json={"email": "asha@example.com"}, headers=GOOD)
    code = outbox[0][1]
    wrong = f"{(int(code) + 1) % 10**6:06d}"
    for i in range(5):
        auth._login_fail_account._hits.clear()  # as if each guess came from a different network
        r = client.post("/auth/reset-password", json={"email": "asha@example.com", "code": wrong, "new_password": NEW},
                        headers=GOOD)
        assert r.status_code == 400
    assert "Too many wrong codes" in r.json()["detail"]
    auth._login_fail_account._hits.clear()
    right = client.post("/auth/reset-password", json={"email": "asha@example.com", "code": code, "new_password": NEW},
                        headers=GOOD)
    assert right.status_code == 400  # the code was cancelled; a new one must be requested
    auth._forgot_email._hits.clear()
    client.post("/auth/forgot-password", json={"email": "asha@example.com"}, headers=GOOD)
    fresh = client.post("/auth/reset-password", json={"email": "asha@example.com", "code": outbox[-1][1],
                                                      "new_password": NEW}, headers=GOOD)
    assert fresh.status_code == 200


def test_mailer_prints_the_code_when_no_mail_server_is_set_and_builds_a_plain_message(monkeypatch, capsys):
    from member3_backend import mailer
    for k in ("SATYASCORE_SMTP_HOST", "SATYASCORE_SMTP_USER", "SATYASCORE_SMTP_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    assert not mailer.configured()
    mailer.send_reset_code("asha@example.com", "123456", 30)
    assert "123456" in capsys.readouterr().out
    msg = mailer.reset_message("asha@example.com", "123456", 30, "app@example.com")
    assert "123456" in msg["Subject"] and "123456" in msg.get_content() and msg["To"] == "asha@example.com"
