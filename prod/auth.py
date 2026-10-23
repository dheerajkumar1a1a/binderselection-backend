"""Identity (phase 3, Q5): one User model, role-scoped pages, local-first auth.

- Passwords: PBKDF2 (stdlib, no dependency).
- Sessions: HMAC-signed cookie over `username:expiry`, key on disk
  (data/secret.key, auto-created; gitignored with data/).
- Seeding: on first run (users table empty) three accounts are provisioned
  and their existence printed — the admin is expected to change the
  passwords via /admin/users before anything leaves the machine.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

from fastapi import HTTPException, Request

from . import store

_COOKIE = "bsa_session"
_DAYS = 30 * 86400

KEY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "secret.key")

SEED_USERS = [
    {"username": "admin", "role": "admin", "display": "Local Admin",
     "password": "change-me-admin"},
    {"username": "uw", "role": "underwriter", "display": "Demo Underwriter",
     "password": "change-me-uw"},
    {"username": "broker", "role": "broker", "display": "Harbourline Logistics",
     "firm": "Harbourline Logistics", "password": "change-me-broker"},
]


def _key() -> bytes:
    k = os.environ.get("BSA_SESSION_KEY")
    if k:
        return k.encode()
    os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
    if not os.path.exists(KEY_PATH):
        with open(KEY_PATH, "wb") as f:
            f.write(os.urandom(32))
    with open(KEY_PATH, "rb") as f:
        return f.read()


def _hash(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + "$" + dk.hex()


def _verify(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$")
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(),
                             bytes.fromhex(salt_hex), 100_000)
    return hmac.compare_digest(dk.hex(), dk_hex)


def _sign(payload: str) -> str:
    return hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()


def ensure_seeded() -> list[dict]:
    """Create the seeded accounts iff the users table is empty; return them
    (for the startup log). Never resets existing users."""
    with store.new_session() as s:
        if s.query(store.User).count() > 0:
            return []
        out = []
        for u in SEED_USERS:
            s.add(store.User(username=u["username"],
                             password_hash=_hash(u["password"]),
                             role=u["role"], display_name=u["display"],
                             broker_firm=u.get("firm", ""),
                             created_at=store.now()))
            out.append(u)
        s.commit()
        return out


def verify(username: str, password: str) -> store.User | None:
    with store.new_session() as s:
        u = s.get(store.User, username or "")
        if u is not None and _verify(password, u.password_hash):
            return u
    return None


def create_user(username: str, password: str, role: str,
                display: str = "", email: str = "", firm: str = "") -> None:
    if role not in ("admin", "underwriter", "broker"):
        raise ValueError("role must be admin, underwriter or broker")
    with store.new_session() as s:
        if s.get(store.User, username) is not None:
            raise ValueError(f"user {username} already exists")
        s.add(store.User(username=username, password_hash=_hash(password),
                         role=role, display_name=display, email=email,
                         broker_firm=firm, created_at=store.now()))
        s.commit()


def list_users() -> list[store.User]:
    with store.new_session() as s:
        return s.query(store.User).order_by(store.User.username).all()


def set_password(username: str, password: str) -> None:
    with store.new_session() as s:
        u = s.get(store.User, username)
        if u is None:
            raise ValueError("no such user")
        u.password_hash = _hash(password)
        s.commit()


# --- cookie session ---------------------------------------------------------

def make_cookie(username: str) -> str:
    payload = f"{username}|{int(time.time()) + _DAYS}"
    return payload + "|" + _sign(payload)


def session_user(request: Request) -> store.User | None:
    tok = request.cookies.get(_COOKIE, "")
    parts = tok.split("|")
    if len(parts) != 3:
        return None
    username, expiry, sig = parts
    if not hmac.compare_digest(_sign(f"{username}|{expiry}"), sig):
        return None
    if float(expiry) < time.time():
        return None
    with store.new_session() as s:
        return s.get(store.User, username)


def require(request: Request, roles: tuple[str, ...]) -> store.User:
    """Authorised user or a 303 to /login (staff surfaces) — callers convert
    portal mis-authorisations to 404s that never leak other firms' files."""
    u = session_user(request)
    if u is None:
        raise LoginNeeded()
    if roles and u.role not in roles:
        raise HTTPException(403, "not allowed for your role")
    return u


class LoginNeeded(Exception):
    pass


def cookie_name() -> str:
    return _COOKIE
