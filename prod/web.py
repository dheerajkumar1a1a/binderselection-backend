"""Production web (phase 1): FastAPI + server-rendered HTMX, local-first.

All underwriting logic is reused from the repo (ui.app / nodes); this file is
only transport. Doctrine surfaced in the templates: the human decides,
missing data becomes named information, provenance on every fact.
"""
import json
import os

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import service, store

app = FastAPI(title="Binder Selection Agent — Production (phase 1)")
TPL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
tpl = Jinja2Templates(directory=TPL_DIR)
store.init_db()

SAMPLES_DIR = os.path.join(service.ROOT, "docs", "data", "samples")


def sample_list() -> list[tuple[str, str]]:
    """Enumerate pinned sample cases (id = filename stem, e.g. 20-demo-accept-full)."""
    out = []
    d = os.path.join(SAMPLES_DIR, "cases")
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            out.append((fn[:-5], fn[:-5]))
    return out


@app.get("/", response_class=HTMLResponse)
def workboard(request: Request):
    cases = service.list_cases()
    return tpl.TemplateResponse(request, "workboard.html",
                                {"cases": cases, "samples": sample_list()})


@app.post("/case/new")
def case_new(broker_firm: str = Form(""), underwriter: str = Form(""),
             sample_case_id: str = Form(""),
             documents_json: str = Form("")):
    documents = json.loads(documents_json) if documents_json else None
    try:
        out = service.create_case(broker_firm, underwriter, sample_case_id,
                                  documents)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/case/{out['case_id']}", status_code=303)


@app.get("/case/{case_id}", response_class=HTMLResponse)
def case_page(request: Request, case_id: str):
    detail = service.case_detail(case_id)
    if detail is None:
        raise HTTPException(404, "case not found")
    case = detail["case"]
    latest = detail["evaluations"][0] if detail["evaluations"] else None
    payload = latest.payload if latest else {}
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
    })


@app.post("/case/{case_id}/evaluate")
def case_evaluate(case_id: str, llm: str = Form("")):
    try:
        service.evaluate_case(case_id, llm=llm or None)
    except LookupError:
        raise HTTPException(404, "case not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/case/{case_id}", status_code=303)


@app.post("/case/{case_id}/decide")
def case_decide(case_id: str, action: str = Form(...),
                underwriter: str = Form(...),
                selected_binder: str = Form(""),
                reason_code: str = Form("")):
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
