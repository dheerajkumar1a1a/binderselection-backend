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
    r = RedirectResponse("/", status_code=303)
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
def case_new(request: Request, broker_firm: str = Form(""),
             underwriter: str = Form(""), sample_case_id: str = Form(""),
             documents_json: str = Form("")):
    _staff(request)
    documents = json.loads(documents_json) if documents_json else None
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
        "user": u, "has_open": has_open,
    })


@app.get("/case/{case_id}/doc/{doc_id}", response_class=HTMLResponse)
def doc_page(request: Request, case_id: str, doc_id: str):
    _staff(request)
    view = service.doc_view(case_id, doc_id)
    if view is None:
        raise HTTPException(404, "case not found")
    if not view["has_text"] and not view["has_structured"]:
        raise HTTPException(404, "no readable text stored for this document "
                                 "(re-run the evaluation to record its parsed text)")
    return tpl.TemplateResponse(request, "doc.html", {"v": view})


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
