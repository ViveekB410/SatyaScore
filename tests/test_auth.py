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
    for w in (auth._login_fail_account, auth._login_fail_ip, auth._register_ip):
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
