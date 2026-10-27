"""Shell contract tests: every link in the rail must resolve, the shell must
never depend on a CDN, and the theme must resolve before first paint.

The audit-link bug is the reason this file exists: the nav was written from the
label ("Audit") and the route is /admin/audit, so the rail shipped a 404 that
only a click would reveal. A nav item is a promise; test the promise.
"""
import os
import re
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="ui_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_TMP, "prod.sqlite3")).replace("\\", "/")

import pytest
from fastapi.testclient import TestClient

from prod import store
from prod.web import app

_NAV = re.compile(r'class="nav-item[^"]*"\s+href="([^"]+)"')


@pytest.fixture()
def admin():
    store.init_db()
    c = TestClient(app, follow_redirects=True)
    r = c.post("/login", data={"username": "admin", "password": "change-me-admin"})
    assert r.status_code == 200
    return c


@pytest.fixture()
def uw():
    store.init_db()
    c = TestClient(app, follow_redirects=True)
    c.post("/login", data={"username": "uw", "password": "change-me-uw"})
    return c


def _nav_hrefs(html: str) -> list[str]:
    return sorted(set(_NAV.findall(html)))


def test_every_rail_link_resolves(admin):
    hrefs = _nav_hrefs(admin.get("/").text)
    assert hrefs, "rail rendered no nav items"
    broken = []
    for href in hrefs:
        code = admin.get(href).status_code
        if code != 200:
            broken.append(f"{href} -> {code}")
    assert not broken, "rail links that do not resolve: " + ", ".join(broken)


def test_every_rail_link_renders_the_shell(admin):
    """A nav link that resolves but drops the rail is the same broken product."""
    for href in _nav_hrefs(admin.get("/").text):
        html = admin.get(href).text
        assert 'class="rail"' in html, f"{href} rendered without the rail"
        assert 'class="nav-item' in html, f"{href} rendered an empty rail"


def test_rail_covers_every_admin_surface(admin):
    hrefs = _nav_hrefs(admin.get("/").text)
    for expected in ("/", "/admin/rules", "/admin/capacity", "/admin/reference",
                     "/admin/users", "/admin/audit", "/help"):
        assert expected in hrefs, f"missing from rail: {expected}"


def test_deep_pages_keep_the_shell(admin):
    """Crawl what a user can actually click. Detail pages are reached by link,
    not by the rail — and that is exactly how the rail went missing before."""
    admin.post("/case/new", data={
        "broker_firm": "Harbourline Logistics", "underwriter": "t-uw",
        "sample_case_id": "20-demo-accept-full", "documents_json": ""})

    queue, seen, bad = ["/"], set(), []
    while queue and len(seen) < 40:
        href = queue.pop(0)
        if href in seen:
            continue
        seen.add(href)
        page = admin.get(href)
        if page.status_code != 200:
            bad.append(f"{href} -> {page.status_code}")
            continue
        # A printed letter is an artefact, not a screen: it has no shell by design.
        # Rules-proposal detail is a standalone document until its rebuild in
        # cut 2; it is listed in docs/ui/README as a known bypass.
        exempt = ("/letter/", "/admin/rules/proposal/")
        if not href.startswith(exempt) and 'class="rail"' not in page.text:
            bad.append(f"{href} dropped the rail")
        for sub in re.findall(r'href="(/[^"#]*)"', page.text):
            if sub.startswith(("/static", "/logout")):
                continue
            queue.append(sub)
    assert len(seen) > 3, "crawl never left the workboard"
    assert not bad, "; ".join(bad)


def test_no_template_silently_bypasses_the_shell():
    """Seven templates were standalone documents: they rendered a different
    product on click. Anything outside the allow-list must extend base.html."""
    allow = {
        "base.html", "components.html",          # the shell itself
        "login.html",                            # pre-auth, deliberately bare
        "letter.html",                           # print artefact
        "portal.html", "portal_case.html", "portal_round.html",  # broker register
        "rules_proposal.html",                   # full rebuild in cut 2
    }
    root = Path(__file__).resolve().parents[1] / "prod" / "templates"
    orphans = []
    for path in sorted(root.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        if path.name in allow or text.lstrip().startswith('{% extends "base.html" %}'):
            continue
        orphans.append(path.name)
    assert not orphans, "templates bypassing the shell: " + ", ".join(orphans)


def test_admin_group_is_hidden_from_underwriter(uw):
    html = uw.get("/").text
    assert "/admin/audit" not in html and "/admin/users" not in html
    # ...but the underwriter may still author rules and capacity.
    assert "/admin/rules" in html and "/admin/capacity" in html


def test_shell_is_offline_capable(admin):
    html = admin.get("/").text
    assert "/static/app.css" in html
    assert "cdn.jsdelivr.net" not in html and "unpkg.com" not in html
    assert "fonts.googleapis.com" not in html
    assert admin.get("/static/app.css").status_code == 200
    assert admin.get("/static/vendor/alpine.min.js").status_code == 200
    assert admin.get("/static/vendor/htmx.min.js").status_code == 200
    assert admin.get("/static/fonts/inter-latin-var.woff2").status_code == 200


def test_theme_resolves_before_first_paint(admin):
    html = admin.get("/").text
    # The inline script must run before the stylesheet is painted, so dark mode
    # never flashes white. Ordering matters more than the implementation.
    head = html.split("</head>")[0]
    assert "prefers-color-scheme" in head
    assert head.index("localStorage.getItem('theme')") < head.index("app.css")


def test_page_titles_are_specific(admin):
    assert "<title>Workboard · Binder Selection Agent</title>" in admin.get("/").text
    assert "<title>Capacity console · Binder Selection Agent</title>" in \
        admin.get("/admin/capacity").text
