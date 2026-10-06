"""Tests for member3_backend/serve.py (web app + API on one origin), without loading models."""
from pathlib import Path

from fastapi import FastAPI
from starlette.testclient import TestClient

from member3_backend import serve


def _api():
    api = FastAPI()
    state = {"started": False}

    @api.on_event("startup")
    def _start():
        state["started"] = True

    @api.get("/health")
    def health():
        return {"status": "ok", "started": state["started"]}

    return api


def _dist(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app</html>", encoding="utf8")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf8")
    return tmp_path


def test_api_is_served_under_api_and_its_startup_runs(tmp_path):
    with TestClient(serve.build_app(_api(), _dist(tmp_path))) as c:
        r = c.get("/api/health")
        assert r.status_code == 200 and r.json() == {"status": "ok", "started": True}


def test_web_files_and_client_side_routes(tmp_path):
    with TestClient(serve.build_app(_api(), _dist(tmp_path))) as c:
        assert c.get("/").text == "<html>app</html>"
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/account").text == "<html>app</html>"  # client-side route -> index.html
        assert c.get("/reset-password").status_code == 200


def test_without_a_web_build_only_the_api_is_served(tmp_path):
    with TestClient(serve.build_app(_api(), tmp_path / "missing")) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/").status_code == 404


def test_auth_origin_guard_still_applies_under_the_api_prefix(tmp_path, monkeypatch):
    """Regression: under /api, request.url.path is /api/auth/..., which once slipped past the
    '/auth/' check, so sign-in could be posted from a foreign site (login CSRF)."""
    from member3_backend import auth
    monkeypatch.setitem(auth._state, "db", tmp_path / "t.db")
    api = FastAPI()
    auth.install(api, ["https://app.example"])
    monkeypatch.setitem(auth._state, "origins", {"https://app.example"})
    with TestClient(serve.build_app(api, tmp_path / "missing")) as c:
        body = {"email": "a@b.example", "password": "x" * 12}
        evil = c.post("/api/auth/login", json=body, headers={"Origin": "https://evil.example"})
        assert evil.status_code == 403 and evil.json()["detail"] == "Request origin not allowed."
        ok = c.post("/api/auth/login", json=body, headers={"Origin": "https://app.example"})
        assert ok.status_code != 403  # reaches the login handler (401: no such account)
        assert ok.headers["Cache-Control"] == "no-store"


def test_allowed_origin_from_space_host():
    f = serve.allowed_origin_from_space
    assert f({"SPACE_HOST": "vivek-satyascore.hf.space"}) == "https://vivek-satyascore.hf.space"
    assert f({}) is None and f({"SPACE_HOST": "  "}) is None
