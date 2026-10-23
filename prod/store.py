"""Production storage (phase 1): persistent Cases + append-only evaluations/decisions.

Local-first: SQLite by default (zero install). The DAO layer is plain SQL via
SQLAlchemy so switching to Postgres later is one DATABASE_URL change — the
schema uses only portable types.

Doctrine honoured here:
- Nothing is ever updated destructively: evaluations and decisions are
  append-only; a Case only moves forward (its pointer fields change).
- Every decision is a named human's; the store only records what the engine
  recommended and what the human chose.
"""
import os
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, Integer, String,
                        Text, create_engine)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Storage URL: SQLite file by default, DATABASE_URL to switch (postgres later).
_DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data", "prod.sqlite3")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///" + _DEFAULT_DB)

# SQLite file paths need their directory to exist (one-time, local-first).
if DATABASE_URL.startswith("sqlite:///") and ":memory:" not in DATABASE_URL:
    _db_path = DATABASE_URL[len("sqlite:///"):]
    os.makedirs(os.path.dirname(_db_path), exist_ok=True)

# check_same_thread=False: FastAPI serves from a threadpool; SQLite fine here.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}
                       if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


class Case(Base):
    """The persistent object spanning time (CONTEXT.md vocabulary)."""
    __tablename__ = "cases"
    case_id = Column(String(64), primary_key=True)
    submission_reference = Column(String(64), nullable=False)
    broker_firm = Column(String(120), default="")
    underwriter = Column(String(120), default="")
    # Status: new -> assessed -> decided (or referred/no-eligible between).
    status = Column(String(24), nullable=False, default="new")
    source = Column(String(32), default="sample")  # sample | upload
    created_at = Column(DateTime, nullable=False)
    assessed_at = Column(DateTime, nullable=True)
    decided_at = Column(DateTime, nullable=True)


class Evaluation(Base):
    """Append-only: one engine evaluation of a Case (never edited)."""
    __tablename__ = "evaluations"
    evaluation_id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False)
    llm = Column(String(32), nullable=True)  # nvidia/gemini/openrouter/None(stub)
    model = Column(String(120), default="")
    outcome = Column(String(24), nullable=False)  # recommendation|halt|no-eligible
    recommendation = Column(String(64), nullable=True)
    payload = Column(JSON, nullable=False)  # the full run state


class Decision(Base):
    """Append-only: one human decision on an evaluation."""
    __tablename__ = "decisions"
    decision_id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), nullable=False, index=True)
    evaluation_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)
    underwriter = Column(String(120), nullable=False)
    action = Column(String(24), nullable=False)  # accept/override/refer_back
    selected_binder = Column(String(64), nullable=True)
    reason_code = Column(String(64), nullable=True)
    outcome = Column(String(24), nullable=False)  # reserved/released/failed/none
    detail = Column(JSON, default=dict)


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC


def init_db() -> None:
    Base.metadata.create_all(engine)


def new_session() -> Session:
    return SessionLocal()


SLA_ASSESSMENT_DAYS = 3  # business days (Q16a)
SLA_ROUND_DAYS = 10      # business days for a broker Request round (phase 3)


def sla_state(case: Case) -> str:
    """Assessment SLA: 3 business days from creation. due|breached|n/a."""
    if case.status not in ("new",):
        return "n/a"
    return ("breached" if now() > _bd_deadline(case.created_at, SLA_ASSESSMENT_DAYS)
            else "due")


def _bd_deadline(start: datetime, days: int) -> datetime:
    """Deadline `days` business days after start (Mon-Fri)."""
    cur, left = start, days
    while left > 0:
        cur = cur + __import__("datetime").timedelta(days=1)
        if cur.weekday() < 5:
            left -= 1
    return cur


def round_sla_state(round_: "RequestRound") -> str:
    """Answer SLA for a Request round: n/a | due | breached (visual only)."""
    if round_.status != "open" or round_.due_at is None:
        return "n/a"
    return "breached" if now() > round_.due_at else "due"


class User(Base):
    """One identity model for every role (Q5, phase 3): admin / underwriter /
    broker. Phase 4's maker-checker reuses the same table — a design choice
    made now so nobody re-plumbs identity later."""
    __tablename__ = "users"
    username = Column(String(64), primary_key=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), nullable=False)  # admin | underwriter | broker
    display_name = Column(String(120), default="")
    email = Column(String(160), default="")    # notifications (Q13)
    broker_firm = Column(String(120), default="")  # broker accounts only
    created_at = Column(DateTime, nullable=False)


class RequestRound(Base):
    """A named batch of information requests issued to the broker at once;
    one active round per Case (ADR 0001). Append-only once issued; the
    broker's draft answers are editable until submission locks the round."""
    __tablename__ = "request_rounds"
    round_id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), nullable=False, index=True)
    number = Column(Integer, nullable=False)   # 1-based, per Case
    status = Column(String(16), nullable=False, default="open")  # open|locked
    issued_at = Column(DateTime, nullable=False)
    due_at = Column(DateTime, nullable=True)   # SLA_ROUND_DAYS business days
    issued_by = Column(String(120), default="")
    submitted_at = Column(DateTime, nullable=True)
    answered_evaluation_id = Column(Integer, nullable=True)  # successor run
    breach_notified_at = Column(DateTime, nullable=True)  # email sent once
    items = Column(JSON, nullable=False, default=list)  # frozen issued snapshot


class RequestItem(Base):
    """One named information request: traces to the rule(s) that could not
    assess and the missing field. Engine derives it; the underwriter may
    suppress it or attach a human note (Q4) — never a free-standing ask."""
    __tablename__ = "request_items"
    item_id = Column(Integer, primary_key=True, autoincrement=True)
    round_id = Column(Integer, nullable=False, index=True)
    field = Column(String(160), nullable=False)   # e.g. 'largest_single_claim_amount'
    question = Column(Text, nullable=False)       # deterministic phrasing
    raised_by = Column(JSON, nullable=False, default=list)  # [[binder_id, rule_id]]
    suppressed = Column(Boolean, default=False)
    note = Column(Text, default="")               # underwriter note (marked human)
    # Broker draft (editable until the round locks):
    answer_text = Column(Text, default="")
    answer_doc_id = Column(String(160), nullable=True)  # doc marked as answering
