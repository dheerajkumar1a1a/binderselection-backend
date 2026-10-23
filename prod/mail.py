"""Notifications (phase 3, Q6/Q13): email-only, local-first, no silent spots.

Where mail really goes:
- SMTP_* env configured -> real SMTP (smtplib, start when host is set).
- Otherwise -> the local outbox folder `data/outbox/`, one .eml-shaped text
  file per message — dev-honest: you can read exactly what was sent.

Recipients resolve from User.email (Q13): broker events go to the broker
role users of the case's firm; underwriter events to every underwriter+admin.
If nobody has an address yet, the message still lands in the outbox addressed
to the role placeholder, so the event is never lost or silent.
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
from email.message import EmailMessage

from . import store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTBOX = os.path.join(ROOT, "data", "outbox")
_seq = 0


def _smtp_env() -> dict | None:
    host = os.environ.get("SMTP_HOST")
    if not host:
        return None
    return {"host": host, "port": int(os.environ.get("SMTP_PORT", "587")),
            "user": os.environ.get("SMTP_USER", ""),
            "pass": os.environ.get("SMTP_PASS", ""),
            "from": os.environ.get("SMTP_FROM", "binder-agent@local")}


def send(to: str, subject: str, body: str) -> dict:
    """Send one message; never raises for transport down — the outbox keeps
    the proof either way. Returns {'mode': 'smtp'|'outbox', 'path': ...}."""
    global _seq
    cfg = _smtp_env()
    if cfg and to:
        try:
            m = EmailMessage()
            m["From"], m["To"], m["Subject"] = cfg["from"], to, subject
            m.set_content(body)
            ctx = ssl.create_default_context()
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as srv:
                srv.starttls(context=ctx)
                if cfg["user"]:
                    srv.login(cfg["user"], cfg["pass"])
                srv.send_message(m)
            return {"mode": "smtp", "path": None}
        except Exception as e:  # fall through to the outbox, record why
            _write_outbox(to, subject, body, note=f"smtp failed: {e}")
            return {"mode": "outbox", "path": _last_path}
    return _write_outbox(to, subject, body)


def _write_outbox(to: str, subject: str, body: str, note: str = "") -> dict:
    os.makedirs(OUTBOX, exist_ok=True)
    import time
    global _seq
    _seq += 1
    name = f"{time.strftime('%Y%m%d-%H%M%S')}-{_seq:04d}.txt"
    path = os.path.join(OUTBOX, name)
    head = f"To: {to or '(no broker account with an address)'}\nSubject: {subject}\n"
    if note:
        head += f"X-Note: {note}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n" + body + "\n")
    _last_path = path
    return {"mode": "outbox", "path": path}


_last_path = None


# --- recipient resolution (Q13) ---------------------------------------------

def broker_recipient(broker_firm: str) -> str:
    with store.new_session() as s:
        u = (s.query(store.User)
             .filter(store.User.role == "broker",
                     store.User.broker_firm == broker_firm).first())
        return u.email if u is not None and u.email else f"broker@{slug(broker_firm)}"


def staff_recipients() -> list[str]:
    with store.new_session() as s:
        rows = (s.query(store.User)
                .filter(store.User.role.in_(("underwriter", "admin"))).all())
        out = [u.email for u in rows if u.email]
    return out or ["underwriters@local"]


def slug(broker_firm: str) -> str:
    return "".join(c.lower() if c.isalnum() else "" for c in (broker_firm or "unknown"))
