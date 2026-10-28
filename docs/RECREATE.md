# Recreating this app on another Windows machine

This is the runbook for getting a working copy of the Binder Selection Agent onto a
fresh Windows laptop, and for keeping it healthy afterwards. It assumes a developer
who has not seen this repo before, a normal corporate Windows 10/11 machine, and no
Docker.

Everything here is copy-paste. Where a script exists, the script is shown first and the
manual equivalent second, so the document still works if a script is unavailable.

---

## 0. What you are recreating

This repo ships three distinct surfaces. They have different requirements, and mixing
them up is the most common source of confusion.

| Surface | What it is | Needs | Where it runs |
| --- | --- | --- | --- |
| **Production web app** | FastAPI + server-rendered Jinja templates: login, workboard, case, request rounds, decisions, capacity desk, rules console, broker portal | Python 3.12, a SQLite file, a session key | This machine, `http://127.0.0.1:8123` |
| **Engine + tests** | The LangGraph pipeline and the 215-test suite | Python 3.12 only | Any terminal |
| **Static demo** | A self-contained JS snapshot of the engine in `docs/` (already published to GitHub Pages) | A browser | `docs/index.html`, no server |

**There is no Docker path and no cloud deploy step in this guide.** The app is a
server-side Python application; GitHub Pages can only serve the static `docs/` demo.

---

## 1. Prerequisites

Minimum: **Windows 10/11, PowerShell 5.1, Python 3.12, Git (optional), a browser**.

Install Python 3.12 and Git in one go:

```powershell
winget install --id Python.Python.3.12 -e
winget install --id Git.Git -e
```

Then **open a new PowerShell window** (the PATH is only refreshed for new windows) and
check:

```powershell
python --version     # must print Python 3.12.x
git --version
```

Two Windows-specific rules apply throughout:

- Always use `python -m pip`, never bare `pip`. On locked-down machines `pip.exe` is
  commonly blocked by Application Control while the module form is allowed.
- Never rely on `Activate.ps1`. Execution policy often blocks it. Call
  `.\.venv\Scripts\python.exe` directly instead; every command in this guide does.

If `python` opens the Microsoft Store instead of printing a version, the Store alias
is shadowing a real install. Install 3.12 with the `winget` line above, or disable the
alias in **Settings -> Apps -> Advanced app settings -> App execution aliases**.

---

## 2. Where to put the repo

Use a plain local folder:

```
C:\src\binderselection-backend
```

Do **not** clone into OneDrive, Dropbox or a network share. File sync clients fight
`.git/` writes and SQLite locking and produce intermittent, hard-to-diagnose failures.
If you are forced onto OneDrive, read Appendix A first.

Clone (or download a ZIP from GitHub if `git` is not available):

```powershell
New-Item -ItemType Directory -Force C:\src | Out-Null
cd C:\src
git clone https://github.com/dheerajkumar1a1a/binderselection-backend.git
cd binderselection-backend
```

Without Git: on the GitHub page choose **Code -> Download ZIP**, extract it, and rename
the folder to `C:\src\binderselection-backend`.

---

## 3. Bootstrap

### 3.1 The script (recommended)

```powershell
cd C:\src\binderselection-backend
.\scripts\bootstrap.ps1
```

It verifies Python 3.12, creates `.venv`, installs the pinned dependency set from
`requirements.lock.txt`, and runs the full test suite. Re-running it is safe: it reuses
the existing `.venv`.

Useful flags:

| Flag | Effect |
| --- | --- |
| `-SkipTests` | Install only. Run the tests separately before trusting the machine. |
| `-PythonExe "C:\Python312\python.exe"` | Point at a specific 3.12 interpreter. |

If PowerShell refuses to run the script with an execution-policy error, bypass it for
this one process only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
```

### 3.2 The manual equivalent

```powershell
cd C:\src\binderselection-backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

Expected final line: `215 passed`.

### 3.3 Why a lockfile

`requirements.txt` records the supported ranges (`>=`). `requirements.lock.txt` records
the exact versions that produced the green 215-test run. Install from the lockfile to
get the same behaviour on every machine; touch `requirements.txt` only when you intend
to change the dependency set, then regenerate the lockfile from a working venv:

```powershell
.\.venv\Scripts\python.exe -m pip freeze > requirements.lock.txt
```

---

## 4. Run it

```powershell
.\scripts\run.ps1
```

Then open <http://127.0.0.1:8123> and sign in at `/login`.

| Flag | Effect |
| --- | --- |
| `-Port 9000` | Use another port (default 8123). |
| `-Dev` | Auto-reload Python, templates and static files. Editing only. |
| `-Lan` | Bind `0.0.0.0` so other machines can connect. Prints a password warning. |

Manual equivalent:

```powershell
.\.venv\Scripts\python.exe -m uvicorn prod.web:app --host 127.0.0.1 --port 8123
```

Do not use `-Dev` for a demo. A reload mid-flow drops in-flight work and can look like
a crash to the person watching.

### 4.1 First boot and the seeded accounts

On the first boot the app creates `data/prod.sqlite3`, generates `data/secret.key`, and
prints three accounts to the console:

| Username | Role | Password | Sees |
| --- | --- | --- | --- |
| `admin` | admin | `change-me-admin` | Everything, including Admin group (users, reference data) |
| `uw` | underwriter | `change-me-uw` | Work + Govern groups; no Admin |
| `broker` | broker | `change-me-broker` | Broker portal only; never scores, rules or other binders |

**Change these passwords at `/admin/users` before exposing the app to anyone else.**
If you use `-Lan`, do it first.

### 4.2 Where local state lives

| Path | Holds | Gitignored |
| --- | --- | --- |
| `data/prod.sqlite3` | Cases, evaluations, decisions, users, rounds | yes |
| `data/secret.key` | Session-cookie signing key (auto-created) | yes |
| `data/outbox/` | Mail written when SMTP is not configured | yes |
| `.checkpoints.sqlite` | LangGraph engine checkpoints | yes |
| `audit/decisions.jsonl` | Append-only decision audit trail | yes |
| `capacity/ledger.json` | Capacity ledger state | yes |
| `ui/demo-ledger.json` | Leadership demo UI ledger | yes |

---

## 5. Reset and restore

### 5.1 Clean demo state

```powershell
.\scripts\reset-demo.ps1          # wipes data\ and .checkpoints.sqlite
.\scripts\reset-demo.ps1 -All     # also wipes audit\, capacity ledger, UI ledger
```

Both list what they will delete and ask for confirmation; `-Force` skips the prompt. The
next boot re-seeds the accounts and prints their passwords. Anyone signed in is logged
out, because the session key is recreated.

### 5.2 Moving an existing installation

To carry real work to another machine, copy these together, with the app stopped:

- `data/prod.sqlite3`
- `data/secret.key` (or set `BSA_SESSION_KEY` to the same value on both machines)
- `data/outbox/` if you need the sent-mail history
- `audit/` if you need the audit trail
- `capacity/ledger.json` if capacity reservations matter

If the database travels without the matching session key, everyone is simply logged out
once; data is unaffected. If you copy the database but **not** `capacity/ledger.json`,
reserved capacity can disagree with the ledger - copy both or neither.

---

## 6. Update an existing install

Do **not** re-clone; that loses `data/`. From the existing checkout:

```powershell
cd C:\src\binderselection-backend
git pull
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt   # only if it changed
.\scripts\run.ps1
```

`git pull` refuses if local files were edited. Commit or stash them first; never delete
`data/` to resolve a merge problem.

---

## 7. The static demo (GitHub Pages)

`docs/index.html` is a self-contained snapshot of the engine and needs no server:

- Locally: open `docs\index.html` in a browser. It works offline.
- Published: <https://dheerajkumar1a1a.github.io/binderselection-backend/>

Extraction has two optional modes. **BYOK**: paste your own Gemini key; it stays in page
memory and goes only to Google. **Repo-secret CI**: the page dispatches
`.github/workflows/extract-request.yml`, which runs `scripts/extract_request.py` with the
key injected from repository secrets. Sample cases run keyless either way.

Redeploying Pages is maintenance, not recreation: pushing to `main` republishes `docs/`.

---

## 8. Acceptance checklist

A machine is ready when all five pass.

1. **Tests** - `.\.venv\Scripts\python.exe -m pytest tests -q` ends with `215 passed`.
2. **Boot** - `.\scripts\run.ps1` prints `Uvicorn running on http://127.0.0.1:8123`; on a
   first boot it also prints three `[auth] seeded account:` lines.
3. **Logins** - `admin`, `uw` and `broker` all reach their landing page; `uw` has no
   Admin group in the rail; `broker` sees only the portal.
4. **One case end to end** - as `uw`, open or create a case, run the assessment, record a
   decision; as `broker`, open the round, answer an item, submit. The case status and the
   outcome letter move.
5. **Static demo** - `docs\index.html` opens offline with no console errors.

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Activate.ps1 cannot be loaded because running scripts is disabled` | PowerShell execution policy | Skip activation entirely: call `.\.venv\Scripts\python.exe`. Or `Set-ExecutionPolicy -Scope Process Bypass`. |
| `pip.exe is blocked by Application Control` | Corporate application control | Always use `python -m pip ...`; never `pip` or `pip.exe`. |
| `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8123)` | Port already in use | `Get-NetTCPConnection -LocalPort 8123` then stop that PID, or `.\scripts\run.ps1 -Port 8124`. |
| Signed out of everything after a reset | `data\secret.key` was deleted and regenerated | Expected. Sign in again; nothing was lost. |
| `python` opens the Microsoft Store | Store alias shadows the real interpreter | Install Python 3.12 via `winget`, or disable the alias in Settings -> App execution aliases. |

---

## 10. Configuration reference

The app reads plain process environment variables. It does **not** auto-load `.env`
(`python-dotenv` is present but unused), so set them in the shell before starting, or use
`data/secret.key` for the session key.

```powershell
$env:BSA_SESSION_KEY = 'a-long-random-string'
.\scripts\run.ps1
```

| Variable | Purpose | Default when unset |
| --- | --- | --- |
| `BSA_SESSION_KEY` | Session-cookie signing key | `data/secret.key`, auto-created |
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///data/prod.sqlite3` |
| `BINDER_PG_CONN` | LangGraph Postgres checkpointer | `.checkpoints.sqlite` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `SMTP_FROM` | Real email delivery | File outbox in `data/outbox/` |
| `APP_DEFAULT_LLM` | Default extractor provider | Deterministic stub (keyless) |
| `NVIDIA_API_KEY` / `NVIDIA_MODEL` | NVIDIA extraction | Not used |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | OpenRouter extraction | Not used |
| `GEMINI_API_KEY` or `GEMINI_API_KEY_FILE` / `GEMINI_MODEL` | Gemini extraction | Not used |

Copy `.env.example` for the annotated version. Only `BSA_SESSION_KEY` has a real
mandatory-or-auto-generated decision; everything else degrades to a working local
fallback.

---

## Appendix A - If you must use OneDrive

The original checkout lived under OneDrive and the sync client caused repeated friction.
If policy forces it:

1. Set the folder to **Always keep on this device**.
2. Pause OneDrive sync before any `git commit`, `git pull` or database-heavy work, then
   resume.
3. Expect occasional `.git/index.lock` or SQLite lock errors; retry after sync settles.

A non-synced folder is always the better answer.

## Appendix B - Offline and restricted machines

- Dependency install needs internet to reach PyPI. For an air-gapped machine, build a
  wheelhouse on a connected one and copy it:
  `python -m pip download -r requirements.lock.txt -d wheelhouse`, then
  `python -m pip install --no-index --find-links wheelhouse -r requirements.lock.txt`.
- The web UI is fully offline-capable at runtime: Inter, Alpine and htmx are vendored in
  `prod/static/`; no CDN is contacted.
- No Docker is required or supported by this guide.
