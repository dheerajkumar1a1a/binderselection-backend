"""Production web (phase 3): FastAPI + server-rendered HTMX, local-first.

All underwriting logic is reused from the repo (ui.app / nodes); this file is
only transport. Phase 3 adds: role-scoped login (Q5), Request rounds
(issue -> broker drafts -> submit locks + synchronous successor evaluation),
outcome letters, the delta view, and the broker portal that strictly sees
ask-lists, its own documents and letters — never scores, rules or other
binders (Q8, Q10).
"""
import json
import os

from fastapi import (FastAPI, File, Form, HTTPException, Request,
                     UploadFile)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import auth, service, store

app = FastAPI(title="Binder Selection Agent — Production (phase 3)")
TPL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
tpl = Jinja2Templates(directory=TPL_DIR)

from datetime import datetime as _dt, timedelta as _td, timezone as _tz
_IST = _tz(_td(hours=5, minutes=30))
def _readable_date(value):
    if value is None:
        return "—"
    if isinstance(value, str):
        try:
            value = _dt.fromisoformat(value.replace(" ", "T"))
        except ValueError:
            return value
    # Stored values are UTC (naive); convert to IST for display.
    try:
        if value.tzinfo is None:
            value = value.replace(tzinfo=_tz.utc).astimezone(_IST)
        else:
            value = value.astimezone(_IST)
        return value.strftime("%d %b %Y, %I:%M %p IST")
    except (AttributeError, ValueError):
        return str(value)
tpl.env.filters["rd"] = _readable_date
store.init_db()
_seeded = auth.ensure_seeded()
for _u in _seeded:  # first-run provisioning notice (local dev comfort)
    print(f"[auth] seeded account: {_u['username']} (role {_u['role']}, "
          f"password '{_u['password']}' — change it via /admin/users)",
          flush=True)

SAMPLES_DIR = os.path.join(service.ROOT, "docs", "data", "samples")


def sample_list() -> list[tuple[str, str]]:
    """Enumerate pinned sample cases (id = filename stem, e.g. 20-demo-accept-full)."""
    out = []
    d = os.path.join(SAMPLES_DIR, "cases")
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            out.append((fn[:-5], fn[:-5]))
    return out


# --- auth plumbing -----------------------------------------------------------

def _staff(request: Request):
    """Admin/underwriter user, or a redirect to /login."""
    try:
        return auth.require(request, ("admin", "underwriter"))
    except auth.LoginNeeded:
        raise _LoginRedirect()


def _issuer(request: Request) -> str:
    u = auth.session_user(request)
    return ((getattr(u, "display_name", None) or getattr(u, "username", ""))
            if u else "unknown")


class _LoginRedirect(Exception):
    pass


@app.exception_handler(_LoginRedirect)
async def _login_redirect(request: Request, exc: _LoginRedirect):
    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return tpl.TemplateResponse(request, "login.html", {})


@app.post("/login", response_class=HTMLResponse)
def login_post(request: Request, username: str = Form(""), password: str = Form("")):
    u = auth.verify(username, password)
    if u is None:
        return tpl.TemplateResponse(request, "login.html",
                                    {"error": "wrong username or password"},
                                    status_code=400)
    r = RedirectResponse("/" if u.role in ("admin", "underwriter") else "/portal", status_code=303)
    r.set_cookie(auth.cookie_name(), auth.make_cookie(u.username),
                 httponly=True, samesite="lax")
    return r


@app.get("/logout")
def logout():
    r = RedirectResponse("/login", status_code=303)
    r.delete_cookie(auth.cookie_name())
    return r


# --- staff surfaces (admin + underwriter) ------------------------------------

@app.get("/", response_class=HTMLResponse)
def workboard(request: Request):
    u = _staff(request)
    service.check_breach_notices()
    cases = service.list_cases()
    return tpl.TemplateResponse(request, "workboard.html",
                                {"cases": cases, "samples": sample_list(),
                                 "user": u})


@app.post("/case/new")
async def case_new(request: Request, broker_firm: str = Form(""),
                   underwriter: str = Form(""), sample_case_id: str = Form(""),
                   documents_json: str = Form(""),
                   files: list[UploadFile] = File(default=[])):
    _staff(request)
    documents = None
    if files and any(getattr(f, "filename", "") for f in files):
        documents = []
        for f in files:
            fn = getattr(f, "filename", "") or "upload.bin"
            data = await f.read()
            import base64 as _b64
            documents.append({"filename": fn,
                              "content_b64": _b64.b64encode(data).decode("ascii")})
    if documents is None and documents_json:
        try:
            documents = json.loads(documents_json)
        except json.JSONDecodeError:
            documents = None
    try:
        out = service.create_case(broker_firm, underwriter, sample_case_id,
                                  documents)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/case/{out['case_id']}", status_code=303)


@app.get("/case/{case_id}", response_class=HTMLResponse)
def case_page(request: Request, case_id: str):
    u = _staff(request)
    detail = service.case_detail(case_id)
    if detail is None:
        raise HTTPException(404, "case not found")
    case = detail["case"]
    latest = detail["evaluations"][0] if detail["evaluations"] else None
    payload = latest.payload if latest else {}
    rounds = service.rounds_for_case(case_id)
    # Issue form shows engine gaps only when no round is active (Q2).
    has_open = any(r["round"].status == "open" for r in rounds)
    gaps = service.latest_gaps(case_id) if (latest is not None and not has_open) else []
    delta = None
    if len(detail["evaluations"]) >= 2:
        delta = service.delta_view(detail["evaluations"][1].payload,
                                   detail["evaluations"][0].payload)
    return tpl.TemplateResponse(request, "case.html", {
        "case": case, "latest": latest, "evals": detail["evaluations"],
        "decisions": detail["decisions"],
        "payload": payload,
        "binders": payload.get("binder_results") or [],
        "extracted": payload.get("extracted") or {},
        "docs": payload.get("documents") or [],
        "completeness": payload.get("completeness") or {},
        "halt": payload.get("halt"),
        "sla": store.sla_state(case),
        "rounds": rounds, "gaps": gaps, "delta": delta,
        "reference_facts": payload.get("reference_facts") or [],
        "user": u, "has_open": has_open,
    })


@app.get("/case/{case_id}/doc/{doc_id}", response_class=HTMLResponse)
def doc_page(request: Request, case_id: str, doc_id: str):
    _staff(request)
    views = service.all_doc_views(case_id)
    if not views:
        raise HTTPException(404, "case not found")
    active = next((v for v in views if v["doc_id"] == doc_id), views[0])
    if not active["has_text"] and not active["has_structured"]:
        raise HTTPException(404, "no readable text stored for this document "
                                 "(re-run the evaluation to record its parsed text)")
    return tpl.TemplateResponse(request, "doc.html",
                                {"v": active, "views": views, "case_id": case_id})


@app.post("/case/{case_id}/evaluate")
def case_evaluate(request: Request, case_id: str, llm: str = Form("")):
    _staff(request)
    try:
        service.evaluate_case(case_id, llm=llm or None)
    except LookupError:
        raise HTTPException(404, "case not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/case/{case_id}", status_code=303)


@app.post("/case/{case_id}/decide")
def case_decide(request: Request, case_id: str, action: str = Form(...),
                underwriter: str = Form(...),
                selected_binder: str = Form(""),
                reason_code: str = Form("")):
    _staff(request)
    try:
        out = service.decide_case(case_id, action, underwriter,
                                  selected_binder or None, reason_code or None)
    except LookupError:
        raise HTTPException(404, "case not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not out.get("valid"):
        raise HTTPException(400, out.get("error", "decision rejected"))
    return RedirectResponse(f"/case/{case_id}", status_code=303)


@app.post("/case/{case_id}/round/issue")
async def round_issue(request: Request, case_id: str):
    """Issue one Request round from engine-named gaps (Q2/Q4)."""
    _staff(request)
    form = await request.form()
    pairs = form.multi_items()
    fields, notes, order = [], {}, {}
    for k, v in pairs:
        if k.startswith("field_") and v:
            fields.append(v)
            order[k] = v
    for k, v in pairs:
        if k.startswith("note_") and v:
            fld = order.get("field_" + k[len("note_"):])
            if fld:
                notes[fld] = v
    try:
        service.issue_round(case_id, fields, notes, issued_by=_issuer(request))
    except LookupError:
        raise HTTPException(404, "case not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/case/{case_id}", status_code=303)


@app.get("/case/{case_id}/letter/{decision_id}", response_class=HTMLResponse)
def letter_page(request: Request, case_id: str, decision_id: int):
    _staff(request)
    detail = service.case_detail(case_id)
    if detail is None:
        raise HTTPException(404, "case not found")
    for d in detail["decisions"]:
        if d.decision_id == decision_id:
            L = (d.detail or {}).get("letter")
            if L:
                return tpl.TemplateResponse(request, "letter.html",
                                            {"case": detail["case"],
                                             "letter": L, "decision": d,
                                             "staff": True, "v": None})
    raise HTTPException(404, "letter not found")


# --- admin (users) ------------------------------------------------------------

@app.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request):
    u = auth.require(request, ("admin",))
    msg = request.query_params.get("msg", "")
    return tpl.TemplateResponse(request, "admin_users.html",
                                {"users": auth.list_users(), "user": u,
                                 "msg": msg.replace("+", " ")})


@app.post("/admin/users")
def admin_users_post(request: Request, username: str = Form(...),
                     password: str = Form(...), role: str = Form(...),
                     display_name: str = Form(""), email: str = Form(""),
                     broker_firm: str = Form("")):
    auth.require(request, ("admin",))
    try:
        auth.create_user(username, password, role,
                         display=display_name, email=email, firm=broker_firm)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse("/admin/users?msg=user+created", status_code=303)


@app.post("/admin/users/password")
def admin_password(request: Request, username: str = Form(...),
                   password: str = Form(...)):
    auth.require(request, ("admin",))
    try:
        auth.set_password(username, password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse("/admin/users?msg=password+updated", status_code=303)


# --- broker portal (Q8: the same Case in restricted view) ---------------------

def _broker(request: Request):
    try:
        return auth.require(request, ("broker",))
    except auth.LoginNeeded:
        raise _LoginRedirect()


@app.get("/portal", response_class=HTMLResponse)
def portal(request: Request):
    u = _broker(request)
    service.check_breach_notices()
    cases = service.portal_cases(u)
    return tpl.TemplateResponse(request, "portal.html",
                                {"cases": cases, "user": u})


@app.get("/portal/case/{case_id}", response_class=HTMLResponse)
def portal_case(request: Request, case_id: str):
    u = _broker(request)
    view = service.portal_case(u, case_id)
    if view is None:
        raise HTTPException(404, "case not found")  # never leaks existence
    return tpl.TemplateResponse(request, "portal_case.html", {"v": view})


@app.get("/portal/case/{case_id}/round/{round_id}", response_class=HTMLResponse)
def portal_round(request: Request, case_id: str, round_id: int):
    u = _broker(request)
    view = service.portal_case(u, case_id)
    if view is None:
        raise HTTPException(404, "case not found")
    for r in view["rounds"]:
        if r["round"].round_id == round_id:
            if r["round"].status != "open":
                return RedirectResponse(f"/portal/case/{case_id}", 303)
            return tpl.TemplateResponse(request, "portal_round.html",
                                        {"v": view, "r": r, "report": None})
    raise HTTPException(404, "round not found")


def _draft_answers(form) -> dict[int, tuple[str, str]]:
    answers: dict[int, tuple[str, str]] = {}
    for key in form:
        if key.startswith("answer_"):
            try:
                item_id = int(key[len("answer_"):])
            except ValueError:
                continue
            answers[item_id] = (form.get(key, "") or "",
                                form.get(f"doc_{item_id}", "") or "")
    return answers


@app.post("/portal/case/{case_id}/round/{round_id}/draft")
async def portal_round_draft(request: Request, case_id: str, round_id: int,
                             files: list[UploadFile] = File(default=[])):
    """Save the editable draft (Q15): typed answers, doc markings, and any
    newly attached documents (stored under the case before submission)."""
    u = _broker(request)
    if service.portal_case(u, case_id) is None:
        raise HTTPException(404, "case not found")
    form = await request.form()
    uploads = []
    for f in files or []:
        fn = getattr(f, "filename", "")
        data = await f.read() if fn else b""
        if data:
            uploads.append((fn, data))
    doc_ids = service.attach_broker_docs(case_id, uploads)
    try:
        service.save_draft(case_id, round_id, _draft_answers(form))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/portal/case/{case_id}/round/{round_id}", 303)


@app.post("/portal/case/{case_id}/round/{round_id}/submit")
async def portal_round_submit(request: Request, case_id: str, round_id: int,
                              files: list[UploadFile] = File(default=[])):
    """Submit locks the round (Q15) and runs the successor evaluation
    synchronously on the same Case (Q14, ADR 0001)."""
    u = _broker(request)
    if service.portal_case(u, case_id) is None:
        raise HTTPException(404, "case not found")
    form = await request.form()
    try:
        service.save_draft(case_id, round_id, _draft_answers(form))
        uploads = []
        for f in files or []:
            fn = getattr(f, "filename", "")
            data = await f.read() if fn else b""
            if data:
                uploads.append((fn, data))
        out = service.submit_round(case_id, round_id, uploads)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/portal/case/{case_id}", status_code=303)


# --- capacity desk (phase 6) -------------------------------------------------

@app.get("/admin/capacity", response_class=HTMLResponse)
def capacity_page(request: Request):
    _staff(request)
    from prod import capacity_desk as cd
    return tpl.TemplateResponse(request, "capacity.html",
                                {"desk": cd.desk()})


@app.post("/admin/capacity/release")
def capacity_release(request: Request, submission_ref: str = Form(...),
                     binder_id: str = Form(...)):
    _staff(request)
    from capacity import ledger as L
    L.release(submission_ref, binder_id)
    return RedirectResponse("/admin/capacity", 303)


@app.post("/case/{case_id}/correct")
async def case_correct(request: Request, case_id: str):
    _staff(request)
    u = auth.session_user(request)
    form = await request.form()
    corrections = {}
    for key in form:
        if key.startswith("correct_"):
            field = key[len("correct_"):]
            val = form.get(key, "").strip()
            if val:
                corrections[field] = val
    try:
        out = service.correct_case(case_id, corrections,
                                   u.username if u else "unknown")
    except LookupError:
        raise HTTPException(404, "case not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/case/{case_id}", status_code=303)

@app.get("/admin/reference", response_class=HTMLResponse)
def reference_page(request: Request):
    _staff(request)
    from prod import reference as ref_mod
    return tpl.TemplateResponse(request, "reference.html",
                                {"feeds": ref_mod.list_feeds(),
                                 "msg": request.query_params.get("msg", "")})


@app.post("/admin/reference/refresh")
def reference_refresh(request: Request):
    _staff(request)
    from prod import reference as ref_mod
    n = ref_mod.refresh_from_dir()
    return RedirectResponse(f"/admin/reference?msg={n}+feeds+loaded", 303)


# --- rules console (phase 4) -------------------------------------------------

def _rc():
    import prod.rules_console as rc
    return rc


@app.get("/admin/rules", response_class=HTMLResponse)
def rules_console(request: Request):
    _staff(request)
    rc = _rc()
    return tpl.TemplateResponse(request, "rules.html",
                                {"binders": rc.list_binders(),
                                 "proposals": rc.list_proposals()})


@app.get("/admin/rules/binder/{binder_id}", response_class=HTMLResponse)
def rules_binder(request: Request, binder_id: str):
    _staff(request)
    rc = _rc()
    detail = next((b for b in rc.list_binders()
                   if b["binder"]["binder_id"] == binder_id), None)
    if detail is None:
        raise HTTPException(404, "binder not found")
    return tpl.TemplateResponse(request, "rules_binder.html",
                                {"detail": detail, "binder_id": binder_id})


@app.get("/admin/rules/propose/{binder_id}", response_class=HTMLResponse)
def rules_propose_page(request: Request, binder_id: str):
    _staff(request)
    rc = _rc()
    rollback_ver = request.query_params.get("rollback")
    if rollback_ver:
        try:
            cur = rc._current_ruleset(binder_id)
            # Pre-fill with the rollback target version's ruleset
            target = int(rollback_ver)
            import os as _os
            target_path = _os.path.join(rc.ROOT, "rules", f"{binder_id}_v{target}.json")
            if _os.path.exists(target_path):
                cur = json.load(open(target_path, encoding="utf-8"))
        except (ValueError, FileNotFoundError):
            pass
        cur_json = json.dumps(cur, indent=2)
        today = __import__("datetime").date.today().isoformat()
        from rules import store as rs
        fields = sorted(rs.KNOWN_FIELDS)
        ops = sorted(rs.VALID_OPS)
        return tpl.TemplateResponse(request, "rules_propose.html",
                                    {"binder_id": binder_id, "current_json": cur_json,
                                     "today": today, "fields": fields, "ops": ops})
    try:
        cur = rc._current_ruleset(binder_id)
        cur_json = json.dumps(cur, indent=2)
    except Exception:
        cur_json = "{}"
    return tpl.TemplateResponse(request, "rules_propose.html",
                                {"binder_id": binder_id, "current_json": cur_json,
                                 "today": __import__("datetime").date.today().isoformat()})


@app.post("/admin/rules/propose/{binder_id}")
async def rules_propose_post(request: Request, binder_id: str):
    _staff(request)
    u = auth.session_user(request)
    form = await request.form()
    effective_from = form.get("effective_from", "")
    summary = form.get("summary", "")
    raw = form.get("ruleset_json", "")
    try:
        ruleset = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"invalid JSON: {e}")
    rc = _rc()
    try:
        prop = rc.create_proposal(binder_id, ruleset,
                                  u.username if u else "unknown",
                                  effective_from, summary)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/admin/rules/proposal/{prop['proposal_id']}", 303)


@app.post("/admin/rules/dryrun/{binder_id}")
async def rules_dryrun(request: Request, binder_id: str):
    _staff(request)
    form = await request.form()
    raw = form.get("ruleset_json", "")
    try:
        ruleset = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"invalid JSON: {e}")
    case_ids = [c.strip() for c in (form.get("case_ids", "") or "").split(",")
                if c.strip()]
    rc = _rc()
    res = rc.dry_run_proposal(binder_id, ruleset, case_ids)
    return HTMLResponse(f"<pre>{json.dumps(res, indent=2)}</pre>")


@app.get("/admin/rules/proposal/{proposal_id}", response_class=HTMLResponse)
def rules_proposal_page(request: Request, proposal_id: str):
    _staff(request)
    rc = _rc()
    prop = rc.get_proposal(proposal_id)
    if prop is None:
        raise HTTPException(404, "proposal not found")
    return tpl.TemplateResponse(request, "rules_proposal.html",
                                {"proposal": prop, "user": auth.session_user(request)})


@app.post("/admin/rules/proposal/{proposal_id}/approve")
def rules_proposal_approve(request: Request, proposal_id: str):
    _staff(request)
    u = auth.session_user(request)
    rc = _rc()
    try:
        rc.approve_proposal(proposal_id, u.username if u else "unknown")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/admin/rules/proposal/{proposal_id}", 303)


@app.get("/portal/case/{case_id}/letter/{decision_id}", response_class=HTMLResponse)
def portal_letter(request: Request, case_id: str, decision_id: int):
    u = _broker(request)
    view = service.portal_case(u, case_id)
    if view is None:
        raise HTTPException(404, "case not found")
    for L in view["letters"]:
        if L["decision_id"] == decision_id and L.get("body"):
            return tpl.TemplateResponse(request, "letter.html",
                                        {"letter": L, "v": view, "staff": False})
    raise HTTPException(404, "letter not found")

@app.post("/case/{case_id}/tags")
async def case_tags(request: Request, case_id: str):
    _staff(request)
    form = await request.form()
    tags = form.get("tags", "")
    try:
        service.update_case_tags(case_id, tags)
    except LookupError:
        raise HTTPException(404, "case not found")
    return RedirectResponse(f"/case/{case_id}", status_code=303)


@app.post("/case/{case_id}/note")
async def case_note(request: Request, case_id: str):
    _staff(request)
    form = await request.form()
    note = form.get("note", "")
    try:
        service.update_case_note(case_id, note)
    except LookupError:
        raise HTTPException(404, "case not found")
    return RedirectResponse(f"/case/{case_id}", status_code=303)

# --- error pages + health check + polish routes (final pass) -----------------

@app.exception_handler(404)
async def not_found(request: Request, exc):
    return tpl.TemplateResponse(request, "error.html",
                                {"code": 404, "msg": "Page not found"}, status_code=404)

@app.exception_handler(403)
async def forbidden(request: Request, exc):
    return tpl.TemplateResponse(request, "error.html",
                                {"code": 403, "msg": "Not allowed for your role"}, status_code=403)

@app.exception_handler(500)
async def server_error(request: Request, exc):
    return tpl.TemplateResponse(request, "error.html",
                                {"code": 500, "msg": "Something went wrong"}, status_code=500)

@app.get("/health")
def health():
    try:
        with store.new_session() as s:
            s.execute(__import__("sqlalchemy").text("SELECT 1"))
        db = "connected"
    except Exception:
        db = "error"
    return {"status": "ok", "version": "v1.20.0", "db": db}

@app.get("/help", response_class=HTMLResponse)
def help_page(request: Request):
    _staff(request)
    return tpl.TemplateResponse(request, "help.html", {})

@app.get("/admin/audit", response_class=HTMLResponse)
def audit_page(request: Request):
    _staff(request)
    from prod import service as svc
    # Cross-case audit trail: all decisions + evaluations
    with store.new_session() as s:
        decisions = (s.query(store.Decision)
                     .order_by(store.Decision.created_at.desc()).limit(200).all())
        evaluations = (s.query(store.Evaluation)
                       .order_by(store.Evaluation.created_at.desc()).limit(200).all())
    return tpl.TemplateResponse(request, "audit.html",
                                {"decisions": decisions, "evaluations": evaluations})

@app.get("/case/{case_id}/clone")
def case_clone(request: Request, case_id: str):
    _staff(request)
    detail = service.case_detail(case_id)
    if detail is None:
        raise HTTPException(404, "case not found")
    payload = detail["evaluations"][0].payload if detail["evaluations"] else {}
    docs = payload.get("documents") or []
    # Re-create as an upload case with the same documents
    import base64 as _b64
    documents = []
    for d in docs:
        entry = {"filename": d.get("filename", "doc")}
        if d.get("structured_hint") is not None:
            entry["structured_hint"] = d.get("structured_hint")
        if d.get("text"):
            entry["text"] = d.get("text")
        # For byte docs, re-encode from disk
        from prod import docstore
        man = docstore.manifest_text(case_id)
        m = man.get(d.get("doc_id"), {})
        if m.get("stored_file"):
            import os as _os
            path = _os.path.join(docstore.case_dir(case_id), "docs", m["stored_file"])
            if _os.path.exists(path):
                raw = open(path, "rb").read()
                entry["content_b64"] = _b64.b64encode(raw).decode("ascii")
        documents.append(entry)
    out = service.create_case(detail["case"].broker_firm, detail["case"].underwriter,
                             None, documents if documents else None)
    return RedirectResponse(f"/case/{out['case_id']}", status_code=303)

@app.get("/case/{case_id}/export.csv")
def case_export(request: Request, case_id: str):
    _staff(request)
    detail = service.case_detail(case_id)
    if detail is None:
        raise HTTPException(404, "case not found")
    import csv as _csv, io as _io
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["Case", "Broker", "Status", "Outcome", "SLA", "Created"])
    c = detail["case"]
    ev = detail["evaluations"][0] if detail["evaluations"] else None
    w.writerow([c.case_id, c.broker_firm, c.status,
                ev.outcome if ev else "", store.sla_state(c),
                c.created_at.isoformat()])
    w.writerow([])
    w.writerow(["Field", "Value", "Confidence", "Source", "Locator"])
    payload = ev.payload if ev else {}
    for f, v in (payload.get("extracted") or {}).items():
        m = (payload.get("extracted_meta") or {}).get(f, {})
        w.writerow([f, v, m.get("confidence", ""), m.get("source_document_id", ""), m.get("source_locator", "")])
    from fastapi.responses import Response as _R
    return _R(content=buf.getvalue(), media_type="text/csv",
              headers={"Content-Disposition": f"attachment; filename={case_id}.csv"})

@app.get("/workboard/export.csv")
def workboard_export(request: Request):
    _staff(request)
    import csv as _csv, io as _io
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["Case", "Broker", "Status", "Outcome", "Assessor", "Created", "SLA"])
    for c in service.list_cases():
        w.writerow([c["case_id"], c["broker_firm"], c["status"],
                    (c["latest"] or {}).get("outcome", ""), c["underwriter"],
                    c["created_at"], c["sla"]])
    from fastapi.responses import Response as _R
    return _R(content=buf.getvalue(), media_type="text/csv",
              headers={"Content-Disposition": "attachment; filename=workboard.csv"})

@app.get("/admin/rules/binder/{binder_id}/diff", response_class=HTMLResponse)
def rules_diff(request: Request, binder_id: str, v1: int = 0, v2: int = 0):
    _staff(request)
    rc = _rc()
    if v1 == 0 or v2 == 0:
        detail = next((b for b in rc.list_binders() if b["binder"]["binder_id"] == binder_id), None)
        versions = [v["version"] for v in (detail["versions"] if detail else [])]
        v1 = versions[-2] if len(versions) >= 2 else versions[0] if versions else 0
        v2 = versions[-1] if versions else 0
    try:
        diff = rc.diff_versions(binder_id, v1, v2)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return tpl.TemplateResponse(request, "rules_diff.html",
                                {"binder_id": binder_id, "diff": diff,
                                 "v1": v1, "v2": v2})


@app.post("/admin/rules/binder/{binder_id}/rollback")
def rules_rollback(request: Request, binder_id: str):
    _staff(request)
    u = auth.session_user(request)
    form_data = None
    import asyncio
    # sync form read
    async def _read():
        return await request.form()
    # We need sync access; use starlette's sync form parser
    from starlette.datastructures import FormData
    # Fall back to query params for simplicity
    target = request.query_params.get("target_version")
    eff = request.query_params.get("effective_from")
    if not target or not eff:
        raise HTTPException(400, "target_version and effective_from required")
    rc = _rc()
    try:
        prop = rc.rollback_proposal(binder_id, int(target), u.username if u else "unknown",
                                    eff, "Rollback")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/admin/rules/proposal/{prop['proposal_id']}", 303)
