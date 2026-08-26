"""Verifies /app's departure page against LINKOUT_POLICY.md.

Serves /app with a plain static file server and drives it with Playwright.
Each test isolates one requirement from the policy: destination-origin
validation (including two classic allow-list bypass tricks), safe rendering
of the untrusted partner label, the noopener/noreferrer tabnabbing defense
on a real popup, the Content-Security-Policy meta tag, and the baseline
functional flow for a legitimate partner destination.
"""

import http.server
import re
import socket
import threading
from contextlib import closing
from urllib.parse import urlencode

import pytest
from playwright.sync_api import sync_playwright

APP_DIR = "/app"

ALLOWED_1 = "https://apply.riverton-partners.example/start"
ALLOWED_2 = "https://docs.riverton-partners.example/guide"


def _free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_handler(*a, **kw):
    return http.server.SimpleHTTPRequestHandler(*a, directory=APP_DIR, **kw)


@pytest.fixture(scope="session")
def base_url():
    port = _free_port()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _make_handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def open_page(browser, base_url):
    contexts = []

    def _open(to=None, label=None):
        context = browser.new_context()
        contexts.append(context)
        context.add_init_script(
            "window.__cspViolations = []; "
            "document.addEventListener('securitypolicyviolation', "
            "(e) => window.__cspViolations.push(e.violatedDirective));"
        )
        page = context.new_page()
        params = {}
        if to is not None:
            params["to"] = to
        if label is not None:
            params["label"] = label
        qs = urlencode(params)
        url = base_url + "/" + ("?" + qs if qs else "")
        page.goto(url, wait_until="load")
        return page

    yield _open
    for c in contexts:
        c.close()


# --- baseline functional contract -------------------------------------------


def test_baseline_functional_flow_with_allowed_destination(open_page):
    """A legitimate partner destination renders a working, correctly-labeled link."""
    page = open_page(to=ALLOWED_1, label="Riverton Apply")
    assert page.locator("#destination-label").inner_text() == "Continue to Riverton Apply"
    link = page.locator("#continue-link")
    assert link.count() == 1
    assert link.get_attribute("href") == ALLOWED_1
    assert link.get_attribute("target") == "_blank"
    assert page.locator("#blocked-notice").count() == 0


def test_second_allowed_origin_also_works(open_page):
    """Both named partner origins must be honored, not just the first one."""
    page = open_page(to=ALLOWED_2, label="Docs")
    link = page.locator("#continue-link")
    assert link.count() == 1
    assert link.get_attribute("href") == ALLOWED_2


def test_blank_label_renders_plain_continue(open_page):
    """No (or blank) label falls back to plain 'Continue', not 'Continue to '."""
    page = open_page(to=ALLOWED_1)
    assert page.locator("#destination-label").inner_text() == "Continue"


# --- destination-origin validation ------------------------------------------


def test_missing_to_shows_blocked_notice(open_page):
    """No destination at all must show the blocked notice, not a dead link."""
    page = open_page(label="Nobody")
    assert page.locator("#continue-link").count() == 0
    assert page.locator("#blocked-notice").count() == 1


def test_malformed_to_shows_blocked_notice(open_page):
    """An unparseable destination must show the blocked notice."""
    page = open_page(to="not a url", label="X")
    assert page.locator("#continue-link").count() == 0
    assert page.locator("#blocked-notice").count() == 1


def test_non_partner_origin_rejected(open_page):
    """A well-formed https URL that just isn't one of the two named partners must be rejected."""
    page = open_page(to="https://evil.test/phish")
    assert page.locator("#continue-link").count() == 0
    assert page.locator("#blocked-notice").count() == 1


def test_javascript_scheme_rejected(open_page):
    """A non-http(s) scheme must never become the link's destination."""
    page = open_page(to="javascript:window.__xss=true")
    assert page.locator("#continue-link").count() == 0


def test_subdomain_suffix_bypass_rejected(open_page):
    """A host that merely ENDS with an allowed origin's hostname (a classic allow-list
    bypass - the real host is 'evil.test', not the partner) must still be rejected."""
    bypass = "https://apply.riverton-partners.example.evil.test/phish"
    page = open_page(to=bypass)
    assert page.locator("#continue-link").count() == 0
    assert page.locator("#blocked-notice").count() == 1


def test_userinfo_bypass_rejected(open_page):
    """A URL that merely CONTAINS an allowed origin's text before an '@' (userinfo)
    must still be rejected - the real host is whatever comes after the '@'."""
    bypass = "https://apply.riverton-partners.example@evil.test/phish"
    page = open_page(to=bypass)
    assert page.locator("#continue-link").count() == 0
    assert page.locator("#blocked-notice").count() == 1


# --- untrusted label rendering (DOM XSS) -------------------------------------


def test_label_event_handler_payload_rendered_as_inert_text(open_page):
    """An event-handler payload in label must render as literal text, not run."""
    payload = '<img src=x onerror="window.__xss=true">'
    page = open_page(to=ALLOWED_1, label=payload)
    assert page.locator("#destination-label").inner_text() == "Continue to " + payload
    assert page.evaluate("window.__xss") in (None, False)


def test_no_inline_event_handler_attributes_in_source(open_page):
    """The shipped markup itself must not rely on inline on*= handler attributes."""
    page = open_page(to=ALLOWED_1, label="ok")
    html = page.content()
    assert re.search(r"<[^>]+\son\w+\s*=", html, flags=re.IGNORECASE) is None


# --- tabnabbing defense -------------------------------------------------------


def test_continue_link_has_noopener_and_noreferrer(open_page):
    """The link out to a partner must carry both noopener and noreferrer."""
    page = open_page(to=ALLOWED_1, label="ok")
    rel = (page.locator("#continue-link").get_attribute("rel") or "").lower().split()
    assert "noopener" in rel
    assert "noreferrer" in rel


# --- Content-Security-Policy --------------------------------------------------


def test_csp_meta_present_and_strict(open_page):
    """The CSP meta tag must restrict default-src/script-src/object-src/base-uri
    and forbid framing by another site."""
    page = open_page(to=ALLOWED_1, label="ok")
    content = page.get_attribute(
        'head meta[http-equiv="Content-Security-Policy" i]', "content"
    )
    assert content is not None, "no Content-Security-Policy meta tag found"
    directives = {}
    for part in content.split(";"):
        part = part.strip()
        if not part:
            continue
        name, _, value = part.partition(" ")
        directives[name.strip().lower()] = value.strip().lower()

    assert "default-src" in directives and "'self'" in directives["default-src"]
    assert "object-src" in directives and "'none'" in directives["object-src"]
    assert "base-uri" in directives and "'self'" in directives["base-uri"]
    assert "frame-ancestors" in directives and "'none'" in directives["frame-ancestors"]
    script_src = directives.get("script-src", directives.get("default-src", ""))
    assert "'unsafe-inline'" not in script_src
    assert "'unsafe-eval'" not in script_src


def test_no_csp_violations_during_normal_use(open_page):
    """A legitimate partner destination must not trip the page's own CSP."""
    page = open_page(to=ALLOWED_1, label="Riverton Apply")
    violations = page.evaluate("window.__cspViolations")
    assert violations == []
