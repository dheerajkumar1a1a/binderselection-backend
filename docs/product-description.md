# Binder Selection Agent — Production UI

**Product description · v1.16.0 · 6 phases shipped · 188 tests green**

> AI never decides. A named human always does — with full provenance.

---

## 1. Problem

The leadership demo proved the engine: it could parse a submission, extract facts, evaluate binders, and recommend a placement. But it was a one-shot — it ran once, printed JSON, and forgot everything. There was no persistence, no audit trail, no way for an underwriter to ask a broker for missing data and re-evaluate, no broker-facing surface, and no capacity accounting beyond a static JSON file. Provenance existed in the engine's output but never reached a viewer.

The production build turns that demo into a **system of record**: persistent cases, append-only evaluations and decisions, a broker portal, maker-checker rulesets, live capacity, and full provenance on every fact.

---

## 2. Business context

**Marine cargo / stock throughput placement.** A broker submits a risk (total insured value, locations, commodities, loss history, coverage terms) to an underwriter. The underwriter must place it with one of several **binders** — each binder has its own appetite rules, capacity line, and strategic classification. The system evaluates the risk against every binder's ruleset and recommends a placement; the underwriter accepts, overrides, or refers back for information.

**Why it's hard today:**
- Submissions arrive as PDFs, emails, and spreadsheets — facts must be extracted and traced to their source.
- Binder appetite rules are complex and change over time (versioned, effective-dated).
- Capacity is finite and shared — a placement reserves capacity that must expire if the policy doesn't incept.
- Brokers need to know what's being asked of them without seeing internal scoring.
- Regulators and auditors need a 7-year trail of who decided what and why.

---

## 3. Solution

A **local-first web application** (FastAPI + server-rendered HTMX) that wraps the existing engine (`ui.app` / `nodes`) without duplicating any underwriting logic. It adds persistence, provenance, a broker portal, maker-checker rulesets, and a capacity desk around the engine's deterministic core.

**Core doctrine (never broken):**
1. **AI never decides.** The LLM extracts facts; a named human always decides.
2. **Missing data → named information request**, never a silent Pass.
3. **Every fact carries provenance** — source document + quote, or feed + licence + timestamp.
4. **Everything is append-only.** Evaluations, decisions, rounds — never rewritten. A Case never forks.

---

## 4. Capabilities

### 4.1 Persistent Cases
A Case is the persistent object spanning time: a submission, the evaluations run against it, the recorded decisions, and every successor. Status lifecycle: `new` → `assessed` → `decided` (bound, terminal) or `awaiting-broker` (round open). The assessment SLA clock (3 business days) ticks from creation.

### 4.2 Append-only evaluations
Every engine run appends an `Evaluation` row with the full state payload (extracted facts, meta, binder results, scores, narrative). Re-running appends a second evaluation; the first is never touched. A decided case that gains fresh info stays decided until re-decided.

### 4.3 Human decisions with capacity reservation
The underwriter records **accept** (reserve capacity for the selected binder), **override** (place with a different binder + reason code), or **refer back** (open a Request round). Accept/override calls `nodes.settle` which reserves capacity in the ledger. Every decision is append-only with underwriter name, timestamp, and audit ID.

### 4.4 Full provenance on every fact
Every extracted fact carries `source_document_id` and `source_locator` (a quote). The provenance viewer opens the document and highlights the cited text in place — no bounding boxes, nothing edited. For structured submissions, a machine-readable record view marks each fact. Multi-document uploads show all contributing sources per fact in a tabbed viewer.

### 4.5 Documents on disk
Uploaded and sample documents are stored under `data/cases/<case_id>/` (manifest + raw bytes). Evaluations reload from disk — the case survives server restarts. The viewer opens the very bytes that were received.

### 4.6 Information requests & broker portal
The engine's `Cannot assess` rules become first-class **Information request** items, each tracing to a rule and a field. The underwriter issues a **Request round** (one active per Case). The broker portal shows only their own cases — ask-lists, their documents, outcome letters. Never scores, rules, or other binders. Brokers answer via typed portal answers (provenance-marked) and/or document uploads. Submitting locks the round and runs a synchronous successor evaluation.

### 4.7 Successor evaluations & delta view
A Case never forks. Every re-evaluation appends a successor. The delta view shows what changed: facts (added/changed/removed), per-binder outcome flips, rule-level changes, and recommendation/score vs the previous evaluation. Only changes are listed.

### 4.8 Outcome letters
The only engine view that crosses the broker boundary. A bound letter names the selected binder; a referred letter carries the ask-list; a no-eligible letter states the outcome plainly.

### 4.9 Maker-checker rulesets
Ruleset changes travel through a proposal workflow: any underwriter proposes, a different underwriter/admin approves (four-eyes). Approved proposals write the next versioned ruleset file (`binder_<id>_v<N>.json`) with an effective date. The engine picks the right version by date at run time. Dry-run compares proposed vs current on sample cases.

### 4.10 Reference data
Third-party facts (wildfire score, flood zone, territory) are attached to every evaluation from feed files under `data/reference/`. Each fact carries feed name, licence, and fetched_at timestamp. Data, never a decision.

### 4.11 Live capacity desk
Reservations from accepted decisions are tracked in a ledger. The desk shows per-binder: authorised line, written, reserved (active), available, utilisation %, and alert level (ok/warn/bad at 80%/90%). Alerts fire by email when a reservation crosses a threshold. Reservations expire after 30 days (configurable). Manual release available.

### 4.12 Notifications
Email-only (Q13). Round issued → broker; broker answered → staff; round breached → staff (once, idempotent). SMTP when configured, otherwise a local outbox (`data/outbox/`) — dev-honest, no external dependency.

---

## 5. User journeys

### 5.1 Underwriter
1. **Sign in** → workboard shows all cases with status, latest outcome, open rounds, SLA.
2. **Create a case** from a sample or uploaded documents (real file picker).
3. **Run evaluation** (stub or live extractor) → review verdict, facts, per-binder results.
4. **Click any fact's source** → provenance viewer highlights the cited text.
5. **Record a decision**: accept (reserve capacity), override (different binder + reason), or refer back (opens a round).
6. **Issue a Request round** from engine-named gaps (suppress items, add notes).
7. **Review successor evaluations** after the broker answers — delta view shows what changed.
8. **Manage rulesets** via the rules console (propose, dry-run, approve).
9. **Monitor capacity** on the desk; release stale reservations.
10. **Provision accounts** and manage reference feeds (admin).

### 5.2 Broker (portal only)
1. **Sign in** → portal shows only their firm's cases.
2. **View ask-lists** (named gaps, underwriter notes, due dates).
3. **Answer** via typed text and/or document uploads; mark which doc answers which item.
4. **Save draft** (editable) → **Submit round** (locks, triggers re-evaluation).
5. **Read outcome letters** (bound names the binder; referred carries the ask-list).

### 5.3 Admin
1. **Provision accounts** (username, role, display name, email, broker firm).
2. **Manage rulesets** (propose, approve, version history).
3. **Monitor capacity** and release reservations.
4. **Manage reference feeds** (drop JSON into `data/reference/`, refresh).
5. **Reset passwords**.

---

## 6. Architecture

```
Browser (HTMX + Alpine.js)
    │
    ▼
FastAPI (prod/web.py) ── transport only
    │
    ├── prod/service.py ── persistence + provenance + rounds + letters + delta
    ├── prod/store.py ── SQLAlchemy (SQLite default, Postgres via DATABASE_URL)
    ├── prod/docstore.py ── documents on disk (data/cases/<id>/)
    ├── prod/auth.py ── PBKDF2 + HMAC cookie sessions
    ├── prod/mail.py ── SMTP or local outbox
    ├── prod/gaps.py ── engine gaps → named ask items
    ├── prod/reference.py ── third-party feeds
    ├── prod/rules_console.py ── maker-checker proposals
    ├── prod/capacity_desk.py ── ledger-aware screening + alerts
    │
    └── ui.app / nodes ── THE ENGINE (imported, never duplicated)
        ├── parse, extract (nvidia/gemini/openrouter/stub), derive, completeness
        ├── multibind (evaluate/rank), narrative, review (validate), settle
        └── capacity ledger (reserve, release, bind, cancel)
```

**Key design decisions:**
- **Local-first**: SQLite by default, zero install. Swap to Postgres with one env var.
- **Single-tenant**: one org, many users with roles.
- **Server-rendered**: Jinja2 + HTMX. No JS build step, no SPA complexity.
- **Append-only**: evaluations and decisions are never edited; a Case only moves forward.
- **No duplicated engine logic**: production wraps `ui.app.run_pipeline` / `decide` / `nodes.settle`.

---

## 7. Data model

| Table | Purpose | Append-only? |
|---|---|---|
| `Case` | Persistent submission object (status, broker, underwriter, timestamps) | Pointer fields move forward |
| `Evaluation` | One engine run (payload = full state) | Yes — never edited |
| `Decision` | One human decision (action, binder, reason, outcome, letter) | Yes — never edited |
| `User` | Identity for all roles (admin/underwriter/broker) | No (admin-managed) |
| `RequestRound` | One batch of info requests (status, due date, items) | Yes — once issued |
| `RequestItem` | One named ask (field, question, raised_by, answer draft) | Draft editable until lock |

**Documents** live on disk under `data/cases/<id>/` (manifest + raw bytes), not in the DB.

---

## 8. Glossary (condensed)

| Term | Meaning |
|---|---|
| **Case** | Persistent object spanning time: submission, evaluations, decisions, successors. |
| **Evaluation** | One engine run on a Case (append-only). |
| **Decision** | One human decision on an evaluation (accept/override/refer_back). |
| **Information request** | A named fact a binder could not assess, tracing to a rule + field. |
| **Request round** | A batch of info requests issued at once; one active per Case; the SLA unit. |
| **Answer** | Broker-supplied data (typed or document) resolving a round. Data, never a decision. |
| **Successor evaluation** | Re-run on the same Case after new info. A Case never forks. |
| **Broker portal** | Broker-facing surface: their own cases, ask-lists, docs, letters only. |
| **Reference-data fact** | Third-party fact (wildfire, flood, territory) with source/licence/timestamp. |
| **Ruleset proposal** | Draft appetite change through maker-checker + effective-dating. |
| **Capacity reservation** | Created by an accepted decision; 30-day expiry; manual release. |
| **Outcome letter** | The only engine view crossing the broker boundary. |
| **Cannot assess** | Engine term for "Needs information" — held, never silently passed. |

Full glossary: `CONTEXT.md`.

---

## 9. Doctrine (the four rules)

1. **AI never decides.** The LLM extracts facts; a named human always decides.
2. **Missing data → named information request**, never a silent Pass.
3. **Every fact carries provenance** — source document + quote, or feed + licence + timestamp.
4. **Everything is append-only.** Evaluations, decisions, rounds — never rewritten. A Case never forks.

---

## 10. Version history

| Tag | Date | What shipped |
|---|---|---|
| v1.9.3 | 2026-10 | Demo (one-shot, no persistence) |
| v1.10.0 | 2026-10 | Phase 1: workboard + persistent Cases |
| v1.10.1 | 2026-10 | Phase 2: provenance viewer + docs on disk |
| v1.11.0 | 2026-10 | Phase 3: info-requests + broker portal + successors |
| v1.12.0 | 2026-10 | Phase 4: rules console + file picker |
| v1.13.0 | 2026-10 | Phase 5: reference-data facts layer |
| v1.14.0 | 2026-10 | Phase 6: live capacity desk + MI + retention doc |
| v1.15.0 | 2026-10 | UI redesign (HTMX/Alpine, toasts, responsive) |
| v1.16.0 | 2026-10 | Multi-document provenance (tabbed viewer) |

---

## 11. Deployment

### Local run
```powershell
$env:GEMINI_API_KEY_FILE = "path\to\gemini_api.txt"
.\.venv\Scripts\python -m uvicorn prod.web:app --port 8105
```
Open `http://127.0.0.1:8105` (use 127.0.0.1, not localhost).

### Environment variables
| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLite or Postgres connection string | `sqlite:///data/prod.sqlite3` |
| `GEMINI_API_KEY` / `GEMINI_API_KEY_FILE` | Gemini extractor credentials | — |
| `NVIDIA_API_KEY` / `NVIDIA_API_KEY_FILE` | NVIDIA extractor credentials | — |
| `OPENROUTER_API_KEY` | OpenRouter extractor credentials | — |
| `APP_DEFAULT_LLM` | Extractor used by broker portal on submit | stub (keyless) |
| `SMTP_HOST/PORT/USER/PASS/FROM` | Real email; else local outbox | outbox mode |
| `BINDER_LEDGER` | Capacity ledger path | `capacity/ledger.json` |
| `BINDER_RES_TTL_HOURS` | Reservation expiry | 24 (30 days intended) |

### Production checklist
- [ ] Rotate seeded passwords (admin/uw/broker) via `/admin/users`.
- [ ] Set `DATABASE_URL` to Postgres for production.
- [ ] Configure SMTP for real email (or accept outbox mode for dev).
- [ ] Rotate API keys (NVIDIA key is currently stale).
- [ ] Set up `data/` backup (7-year retention — see `docs/retention.md`).
- [ ] Review `data/outbox/` for any missed notifications.

---

## 12. Deferred (later milestones)

- **SLA escalation on breach** — signage only in v1; needs an owner/roster concept.
- **External broker firms** — portal is local same-host, role-scoped; external access is a business milestone.
- **7-year retention automation** — documented policy, manual archive v1.
- **NVIDIA key rotation** — optional; Gemini works as the live extractor.
- **Real file picker** — shipped in v1.12.0 (base64 paste remains as fallback).
- **HTMX partial-refresh upgrade** — optional polish; plain-form redirects work fine.

---

## 13. Metrics

- **188 tests** passing (pytest, isolated SQLite per test).
- **6 phases** shipped in ~2 days (v1.10.0 → v1.16.0).
- **0 secrets** committed (grep-verified before every push).
- **0 duplicated engine logic** — production wraps `ui.app` / `nodes` throughout.

---

*Built with: FastAPI · Jinja2 · HTMX · Alpine.js · SQLAlchemy · SQLite/Postgres · Python 3.12*
*Repo: https://github.com/dheerajkumar1a1a/binderselection-backend*
