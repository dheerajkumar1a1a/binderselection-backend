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

from sqlalchemy import (JSON, Column, DateTime, Float, Integer, String,
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


def sla_state(case: Case) -> str:
    """Assessment SLA: 3 business days from creation. due|breached|n/a."""
    if case.status not in ("new",):
        return "n/a"
    d = case.created_at
    days, cur = 0, d
    while days < SLA_ASSESSMENT_DAYS:
        cur = cur + __import__("datetime").timedelta(days=1)
        if cur.weekday() < 5:  # Mon-Fri
            days += 1
    return "breached" if datetime.now(timezone.utc).replace(tzinfo=None) > cur else "due"
