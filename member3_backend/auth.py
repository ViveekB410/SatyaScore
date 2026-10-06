"""
User accounts, sessions and per-user analysis history for the web app.

Security design:
- Passwords: scrypt (hashlib; memory-hard) with a per-user random salt. Never
  stored or logged in plain text; compared in constant time.
- Sessions: a 256-bit random token in an HttpOnly, SameSite cookie (never
  readable by page scripts). Only its SHA-256 is stored, so a copied database
  cannot be replayed as a login. Sessions expire after SESSION_DAYS; sign-out
  deletes them server-side; a new session is issued at every sign-in.
- CSRF: a state-changing request that carries the session cookie must come from
  an allowed browser Origin (the CORS list). Bodies are JSON only.
- Brute force: failed sign-ins are throttled per IP+email and per IP; sign-ups
  per IP.
- No account enumeration at sign-in: unknown email and wrong password give the
  same message and cost the same scrypt time.
- Responses carry nosniff / frame-deny / no-referrer headers; auth and history
  responses are never cached.

Storage: SQLite (stdlib). Path from SATYASCORE_DB (default instance/satyascore.db,
git-ignored). Deployment behind HTTPS: set SATYASCORE_COOKIE_SECURE=true.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
SESSION_COOKIE = "satyascore_session"
SESSION_DAYS = 7
MIN_PASSWORD, MAX_PASSWORD = 10, 128
MAX_HISTORY_PER_USER = 200
SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_LEN = 2**14, 8, 1, 32
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")

_state: dict = {
    "db": Path(os.environ.get("SATYASCORE_DB", ROOT / "instance" / "satyascore.db")),
    "origins": set(),
}
COOKIE_SAMESITE = os.environ.get("SATYASCORE_COOKIE_SAMESITE", "lax").lower()  # "none" requires Secure
COOKIE_SECURE = (os.environ.get("SATYASCORE_COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
                 or COOKIE_SAMESITE == "none")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    language TEXT NOT NULL,
    input_text TEXT NOT NULL,
    result_json TEXT NOT NULL,
    total_claims INTEGER NOT NULL,
    flagged_count INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS analyses_user_time ON analyses(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS password_resets (
    code_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at REAL NOT NULL
);
"""
RESET_CODE_MINUTES = 30

_init_lock = threading.Lock()
_initialised: set[str] = set()


def set_db_path(path: Path | str) -> None:
    """Point the store at another SQLite file (tests)."""
    _state["db"] = Path(path)


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    path: Path = _state["db"]
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys = ON")
        with _init_lock:
            if str(path) not in _initialised:
                con.executescript(SCHEMA)
                _initialised.add(str(path))
        yield con
        con.commit()  # only on success; an exception rolls the work back
    finally:
        con.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# --- passwords ---------------------------------------------------------------

def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R,
                        p=SCRYPT_P, dklen=SCRYPT_LEN)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, dk = stored.split("$")
        if algo != "scrypt":
            return False
        expected = base64.b64decode(dk)
        got = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt), n=int(n),
                             r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, expected)


# Verified against when the email is unknown, so both failure paths cost the same.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


# --- throttling --------------------------------------------------------------

class SlidingWindow:
    """At most `limit` events per `seconds` per key (in-memory, per process)."""

    def __init__(self, limit: int, seconds: float):
        self.limit, self.seconds = limit, seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _trim(self, key: str, now: float) -> deque[float]:
        q = self._hits[key]
        while q and q[0] <= now - self.seconds:
            q.popleft()
        return q

    def retry_after(self, key: str) -> int | None:
        """Seconds until `key` may try again, or None if not blocked."""
        with self._lock:
            now = time.time()
            q = self._trim(key, now)
            if len(q) < self.limit:
                return None
            return max(1, int(q[0] + self.seconds - now) + 1)

    def hit(self, key: str) -> None:
        with self._lock:
            self._trim(key, time.time()).append(time.time())

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


_login_fail_account = SlidingWindow(5, 15 * 60)   # per IP + email
_login_fail_ip = SlidingWindow(30, 15 * 60)       # per IP, across emails
_register_ip = SlidingWindow(10, 60 * 60)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _too_many(seconds: int, what: str) -> HTTPException:
    minutes = max(1, round(seconds / 60))
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                         detail=f"Too many {what}. Try again in about {minutes} minute{'s' if minutes > 1 else ''}.",
                         headers={"Retry-After": str(seconds)})


# --- sessions ----------------------------------------------------------------

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii", "ignore")).hexdigest()


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    with _db() as con:
        con.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        con.execute("INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                    (_token_hash(token), user_id, now, now + SESSION_DAYS * 86400))
    return token


def _public(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "email": row["email"], "name": row["name"], "created_at": row["created_at"]}


def current_user(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token or len(token) > 200:
        return None
    th = _token_hash(token)
    with _db() as con:
        row = con.execute(
            "SELECT u.id, u.email, u.name, u.created_at, s.expires_at FROM sessions s "
            "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?", (th,)).fetchone()
        if row is None:
            return None
        if row["expires_at"] < time.time():
            con.execute("DELETE FROM sessions WHERE token_hash = ?", (th,))
            return None
        return _public(row)


def require_user(request: Request) -> dict:
    user = current_user(request)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Sign in to continue.")
    return user


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True,
                        secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, path="/")


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=COOKIE_SECURE,
                           samesite=COOKIE_SAMESITE)


# --- analysis history --------------------------------------------------------

def save_analysis(user_id: str, text: str, language: str, result: dict) -> str:
    claims = result.get("claims", [])
    aid = str(uuid.uuid4())
    with _db() as con:
        con.execute(
            "INSERT INTO analyses (id, user_id, created_at, language, input_text, result_json, "
            "total_claims, flagged_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (aid, user_id, _now_iso(), language, text, json.dumps(result, ensure_ascii=False),
             len(claims), sum(1 for c in claims if c.get("verdict") != "Verified")))
        con.execute(  # keep only the newest MAX_HISTORY_PER_USER
            "DELETE FROM analyses WHERE user_id = ? AND id NOT IN (SELECT id FROM analyses "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?)", (user_id, user_id, MAX_HISTORY_PER_USER))
    return aid


def _preview(text: str, n: int = 160) -> str:
    line = next((l.strip() for l in text.splitlines() if l.strip()), "")
    return line if len(line) <= n else line[: n - 1] + "…"


# --- API ---------------------------------------------------------------------

class RegisterRequest(BaseModel):
    name: str = Field(..., max_length=80)
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=MAX_PASSWORD)


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=MAX_PASSWORD)


router = APIRouter()


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, request: Request, response: Response) -> dict:
    ip = client_ip(request)
    if (wait := _register_ip.retry_after(ip)) is not None:
        raise _too_many(wait, "sign-ups from this network")
    name = " ".join(body.name.split())
    email = body.email.strip().lower()
    if not name:
        raise HTTPException(422, detail="Enter your name.")
    if not _EMAIL.match(email):
        raise HTTPException(422, detail="Enter a valid email address.")
    if len(body.password) < MIN_PASSWORD:
        raise HTTPException(422, detail=f"Use a password of at least {MIN_PASSWORD} characters.")
    if body.password.strip().lower() == email:
        raise HTTPException(422, detail="The password must not be your email address.")
    _register_ip.hit(ip)
    user = {"id": str(uuid.uuid4()), "email": email, "name": name, "created_at": _now_iso()}
    try:
        with _db() as con:
            con.execute("INSERT INTO users (id, email, name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                        (user["id"], email, name, hash_password(body.password), user["created_at"]))
    except sqlite3.IntegrityError:
        raise HTTPException(409, detail="An account with this email already exists. Sign in instead.")
    _set_cookie(response, create_session(user["id"]))
    return {"user": user}


@router.post("/auth/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict:
    ip = client_ip(request)
    email = body.email.strip().lower()
    account_key = f"{ip}|{email}"
    for window, key in ((_login_fail_account, account_key), (_login_fail_ip, ip)):
        if (wait := window.retry_after(key)) is not None:
            raise _too_many(wait, "failed sign-in attempts")
    with _db() as con:
        row = con.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    ok = verify_password(body.password, row["password_hash"] if row else _DUMMY_HASH) and row is not None
    if not ok:
        _login_fail_account.hit(account_key)
        _login_fail_ip.hit(ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")
    _login_fail_account.reset(account_key)
    _set_cookie(response, create_session(row["id"]))
    return {"user": _public(row)}


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with _db() as con:
            con.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_cookie(out)
    return out


def _password_problem(password: str, email: str) -> str | None:
    """The same rules as at sign-up."""
    if len(password) < MIN_PASSWORD:
        return f"Use a password of at least {MIN_PASSWORD} characters."
    if password.strip().lower() == email:
        return "The password must not be your email address."
    return None


def _set_password(con: sqlite3.Connection, user_id: str, password: str) -> None:
    """New hash; every existing session and reset code of the user is revoked."""
    con.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id))
    con.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    con.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., max_length=MAX_PASSWORD)
    new_password: str = Field(..., max_length=MAX_PASSWORD)


@router.post("/auth/change-password")
def change_password(body: ChangePasswordRequest, request: Request, response: Response,
                    user: dict = Depends(require_user)) -> dict:
    """Signed-in: the current password is required. Other devices are signed out; this one
    gets a fresh session."""
    ip = client_ip(request)
    key = f"{ip}|{user['email']}"
    for window, k in ((_login_fail_account, key), (_login_fail_ip, ip)):
        if (wait := window.retry_after(k)) is not None:
            raise _too_many(wait, "failed password attempts")
    with _db() as con:
        row = con.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not row or not verify_password(body.current_password, row["password_hash"]):
            _login_fail_account.hit(key)
            _login_fail_ip.hit(ip)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="The current password is incorrect.")
        if problem := _password_problem(body.new_password, user["email"]):
            raise HTTPException(422, detail=problem)
        _set_password(con, user["id"], body.new_password)
    _set_cookie(response, create_session(user["id"]))
    return {"user": user}


def create_reset_code(email: str) -> str | None:
    """A one-time password-reset code for an account (valid RESET_CODE_MINUTES), for the
    administrator to give to the user (no email server is configured). Only its hash is
    stored. None if no such account."""
    code = "-".join(secrets.token_hex(3).upper() for _ in range(3))  # e.g. 3F9A1C-0B7D22-9E4410
    with _db() as con:
        row = con.execute("SELECT id FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        if not row:
            return None
        con.execute("DELETE FROM password_resets WHERE user_id = ? OR expires_at < ?", (row["id"], time.time()))
        con.execute("INSERT INTO password_resets (code_hash, user_id, expires_at) VALUES (?, ?, ?)",
                    (_token_hash(code), row["id"], time.time() + RESET_CODE_MINUTES * 60))
    return code


class ResetPasswordRequest(BaseModel):
    email: str = Field(..., max_length=254)
    code: str = Field(..., max_length=64)
    new_password: str = Field(..., max_length=MAX_PASSWORD)


@router.post("/auth/reset-password")
def reset_password(body: ResetPasswordRequest, request: Request, response: Response) -> dict:
    """Set a new password with a one-time reset code. Wrong email or code give the same
    answer (no account enumeration) and count as failed attempts (throttled)."""
    ip = client_ip(request)
    email = body.email.strip().lower()
    key = f"{ip}|{email}"
    for window, k in ((_login_fail_account, key), (_login_fail_ip, ip)):
        if (wait := window.retry_after(k)) is not None:
            raise _too_many(wait, "failed reset attempts")
    code = body.code.strip().upper()
    with _db() as con:
        row = con.execute(
            "SELECT u.id, u.email, u.name, u.created_at FROM password_resets r JOIN users u ON u.id = r.user_id "
            "WHERE r.code_hash = ? AND u.email = ? AND r.expires_at >= ?",
            (_token_hash(code), email, time.time())).fetchone()
        if not row:
            _login_fail_account.hit(key)
            _login_fail_ip.hit(ip)
            raise HTTPException(400, detail="This reset code is not valid or has expired.")
        if problem := _password_problem(body.new_password, email):
            raise HTTPException(422, detail=problem)
        _set_password(con, row["id"], body.new_password)
    _login_fail_account.reset(key)
    _set_cookie(response, create_session(row["id"]))
    return {"user": _public(row)}


@router.get("/auth/me")
def me(request: Request) -> dict:
    # 200 with null rather than 401: "not signed in" is a normal state here.
    return {"user": current_user(request)}


@router.get("/history")
def list_history(
    q: str | None = Query(None, max_length=200),
    language: Literal["en", "hi", "mr"] | None = None,
    limit: int = Query(50, ge=1, le=MAX_HISTORY_PER_USER),
    user: dict = Depends(require_user),
) -> dict:
    sql = ("SELECT id, created_at, language, input_text, total_claims, flagged_count "
           "FROM analyses WHERE user_id = ?")
    args: list = [user["id"]]
    if language:
        sql += " AND language = ?"
        args.append(language)
    if q and q.strip():
        sql += " AND instr(lower(input_text), lower(?)) > 0"  # plain substring, no LIKE wildcards
        args.append(q.strip())
    sql += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    with _db() as con:
        rows = con.execute(sql, args).fetchall()
    return {"entries": [{"id": r["id"], "created_at": r["created_at"], "language": r["language"],
                         "preview": _preview(r["input_text"]), "total_claims": r["total_claims"],
                         "flagged_count": r["flagged_count"]} for r in rows]}


def _owned(con: sqlite3.Connection, analysis_id: str, user_id: str) -> sqlite3.Row:
    row = con.execute("SELECT * FROM analyses WHERE id = ? AND user_id = ?", (analysis_id, user_id)).fetchone()
    if row is None:  # also for another user's entry: never reveal that it exists
        raise HTTPException(404, detail="This analysis is not in your history.")
    return row


@router.get("/history/{analysis_id}")
def get_history(analysis_id: str, user: dict = Depends(require_user)) -> dict:
    with _db() as con:
        row = _owned(con, analysis_id[:64], user["id"])
    result = json.loads(row["result_json"])
    return {"id": row["id"], "created_at": row["created_at"], "language": row["language"],
            "input_text": row["input_text"], "claims": result.get("claims", []),
            "document": result.get("document"), "processing_time_ms": result.get("processing_time_ms")}


@router.delete("/history/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(analysis_id: str, user: dict = Depends(require_user)) -> Response:
    with _db() as con:
        _owned(con, analysis_id[:64], user["id"])
        con.execute("DELETE FROM analyses WHERE id = ? AND user_id = ?", (analysis_id[:64], user["id"]))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- wiring ------------------------------------------------------------------

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


def csrf_violation(request: Request) -> str | None:
    """A state-changing browser request must come from an allowed Origin when it
    carries the session cookie, and sign-in/sign-up must never be posted from a
    foreign site. Non-browser clients (no Origin, no cookie) are unaffected."""
    if request.method in SAFE_METHODS:
        return None
    origin = request.headers.get("origin")
    has_cookie = SESSION_COOKIE in request.cookies
    is_auth = request.url.path.startswith("/auth/")
    if (has_cookie or is_auth) and origin is not None and origin not in _state["origins"]:
        return "Request origin not allowed."
    if has_cookie and origin is None:
        return "Request origin missing."
    return None


def install(app: FastAPI, allowed_origins: list[str]) -> None:
    """Add the auth/history routes, the CSRF guard and security headers. Call
    BEFORE adding CORSMiddleware so CORS stays outermost (errors keep CORS headers)."""
    _state["origins"] = set(allowed_origins)
    app.include_router(router)

    @app.middleware("http")
    async def _guard(request: Request, call_next):
        reason = csrf_violation(request)
        response = JSONResponse({"detail": reason}, status_code=403) if reason else await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        if request.url.path.startswith(("/auth/", "/history")):
            response.headers["Cache-Control"] = "no-store"
        return response

if __name__ == "__main__":  # administrator tools
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "reset-code":
        issued = create_reset_code(sys.argv[2])
        if issued is None:
            sys.exit("No account with that email.")
        print(f"One-time reset code for {sys.argv[2].strip().lower()} (valid {RESET_CODE_MINUTES} minutes):")
        print(issued)
        print("Give it to the user; they enter it at Sign in -> Forgot password?")
    else:
        sys.exit("Usage: python -m member3_backend.auth reset-code <email>")
