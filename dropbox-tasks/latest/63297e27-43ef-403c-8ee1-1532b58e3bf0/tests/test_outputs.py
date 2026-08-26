from __future__ import annotations

import os
import random
import re
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
PROTO = ENV / "internal" / "proto"
BIN = "/tmp/framewire-bin"

MAX_FRAME = 0x3FFFFFFE
PROTO_LIMIT_CEIL = 0x3FFFFFFF

GO_CRASH_SIGNATURES = (
    "panic:",
    "goroutine ",
    "runtime error",
    "fatal error",
    "signal sigsegv",
    "stack overflow",
    "out of memory",
)

RESOURCE_WORDS = (
    "exceeds",
    "maximum",
    "too large",
    "overflow",
    "limit",
    "body",
    "count",
)

ORDINARY_VALIDS = (1, 2, 3, 4, 5, 12, 13, 14)
BOUNDARY_VALIDS = (6, 7, 8, 9, 10, 11)


def _strip_go_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def _read_src(name: str) -> str:
    return _strip_go_comments((PROTO / name).read_text())


def _read_pkg_concat() -> str:
    parts = [_strip_go_comments(p.read_text()) for p in sorted(PROTO.glob("*.go"))]
    return "\n".join(parts)


def _extract_func_body(src: str, signature_regex: str) -> str | None:
    m = re.search(signature_regex, src)
    if not m:
        return None
    open_brace = src.find("{", m.end())
    if open_brace < 0:
        return None
    depth = 0
    for i in range(open_brace, len(src)):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[open_brace + 1 : i]
    return None


def _eval_expr(expr: str, pkg: str, seen: set[str]) -> int | None:
    """Evaluate a simple Go integer constant expression: literals and resolvable
    identifiers joined by + - * << >> (surrounding parens tolerated). This lets a
    derived cap such as maxFrameLen - 4 or maxMessageBodyLen - 4 count as a real
    bound. Parsing stops at the first token outside a plain arithmetic chain (a
    boolean connective, a call, a second comparison); it returns None when the
    leading operand cannot be resolved.
    """
    parts = re.findall(r"0x[0-9a-fA-F]+|\d+|[A-Za-z_][\w.]*|<<|>>|[-+*]", expr)
    seq: list[int | str] = []
    expect_val = True
    for p in parts:
        is_op = p in ("+", "-", "*", "<<", ">>")
        if expect_val:
            if is_op:
                break
            v = _resolve_int_token(p, pkg, seen)
            if v is None:
                break
            seq.append(v)
            expect_val = False
        else:
            if not is_op:
                break
            seq.append(p)
            expect_val = True
    if seq and isinstance(seq[-1], str):
        seq.pop()
    if not seq:
        return None
    hi: list[int | str] = [seq[0]]
    i = 1
    while i < len(seq):
        op, rhs = seq[i], seq[i + 1]
        if op == "*":
            hi.append(hi.pop() * rhs)
        elif op == "<<":
            hi.append(hi.pop() << rhs)
        elif op == ">>":
            hi.append(hi.pop() >> rhs)
        else:
            hi += [op, rhs]
        i += 2
    res = hi[0]
    i = 1
    while i < len(hi):
        op, rhs = hi[i], hi[i + 1]
        res = res + rhs if op == "+" else res - rhs
        i += 2
    return res


def _resolve_int_token(
    token: str, pkg: str, seen: set[str] | None = None
) -> int | None:
    token = token.strip()
    if re.fullmatch(r"0x[0-9a-fA-F]+", token):
        return int(token, 16)
    if re.fullmatch(r"\d+", token):
        return int(token)
    if not re.fullmatch(r"[A-Za-z_]\w*", token):
        return None
    seen = set() if seen is None else seen
    if token in seen or len(seen) > 8:
        return None
    seen = seen | {token}
    pat = (
        r"\b"
        + re.escape(token)
        + r"\b\s*(?::=|(?:[A-Za-z_][\w.]*\s*)?=(?!=))\s*([^\n;{}]+)"
    )
    m = re.search(pat, pkg)
    return _eval_expr(m.group(1), pkg, seen) if m else None


# Delegation-aware structural check. A frame-length bound is legitimate whether
# it lives inline in the inspected encoder, in a call to
# finishHeader/writeHeader/frameHeader, or in any custom helper the fix routes
# through. We build a name->bodies map over the whole encode package and walk the
# call graph (depth <= 2) accepting a numeric cap literal or a protocol-limit
# comparison found anywhere along the way. Generic ([type-arg]) helpers count.
_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)?\(")
_FUNC_DEF_RE = re.compile(
    r"func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)?\("
)
_CMP_RE = re.compile(r"(?:>=?|<=?)\s*([A-Za-z_][\w.]*|0x[0-9a-fA-F]+|\d+)")


def _brace_body(src: str, start: int) -> str | None:
    open_brace = src.find("{", start)
    if open_brace < 0:
        return None
    depth = 0
    for i in range(open_brace, len(src)):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[open_brace + 1 : i]
    return None


def _func_body_map(pkg: str) -> dict[str, list[str]]:
    bodies: dict[str, list[str]] = {}
    for m in _FUNC_DEF_RE.finditer(pkg):
        body = _brace_body(pkg, m.end())
        if body is not None:
            bodies.setdefault(m.group(1), []).append(body)
    return bodies


def _body_bounds_len(body: str, pkg: str) -> bool:
    for m in _CMP_RE.finditer(body):
        tok = m.group(1)
        if tok.endswith("MaxInt32"):
            continue
        val = _resolve_int_token(tok, pkg)
        if val is not None and 0x10000 <= val <= PROTO_LIMIT_CEIL:
            return True
    return False


def _bounds_or_delegates(body: str, pkg: str, funcs, depth: int) -> bool:
    if _body_bounds_len(body, pkg):
        return True
    if depth <= 0:
        return False
    for callee in {mm.group(1) for mm in _CALL_RE.finditer(body)}:
        for cbody in funcs.get(callee, ()):
            if _bounds_or_delegates(cbody, pkg, funcs, depth - 1):
                return True
    return False


def _caps_or_delegates(body: str, pkg: str) -> bool:
    return _bounds_or_delegates(body, pkg, _func_body_map(pkg), 2)


def _uses_protocol_limit(body: str, pkg: str) -> bool:
    return _bounds_or_delegates(body, pkg, _func_body_map(pkg), 2)


def _send_captures_encode_error(body: str) -> bool:
    m = re.search(r",\s*([A-Za-z_]\w*)\s*:?=\s*[^\n]*?Encode\s*\(", body)
    if not m or m.group(1) == "_":
        return False
    return re.search(r"\b" + re.escape(m.group(1)) + r"\b\s*!=\s*nil", body) is not None


def _parse_kv(text: str, key: str) -> int | None:
    m = re.search(rf"\b{re.escape(key)}=(-?\d+)", text)
    return int(m.group(1)) if m else None


@pytest.fixture(scope="session")
def binary():
    build = subprocess.run(
        ["go", "build", "-o", BIN, "./cmd/framewire"],
        cwd=str(ENV),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
    )
    assert build.returncode == 0, f"go build failed:\n{build.stdout}"
    assert os.path.exists(BIN), "framewire binary not produced"
    return BIN


def _run(binary, sub, path, timeout=60):
    return subprocess.run(
        [binary, sub, str(path)],
        cwd=str(ENV),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def frame(binary, relpath):
    return _run(binary, "frame", ENV / relpath)


def send(binary, relpath):
    return _run(binary, "send", ENV / relpath)


def _write_spec(tmp_path, name, lines):
    p = tmp_path / name
    p.write_text("".join(f"{ln}\n" for ln in lines))
    return p


def _assert_no_crash(r, label):
    err = r.stderr.lower()
    for sig in GO_CRASH_SIGNATURES:
        assert sig not in err, (
            f"{label}: rejected via a Go crash ({sig!r}), not the clean returned "
            f"error path.\nstderr:\n{r.stderr}"
        )


def _assert_clean_reject(r, label, subsystem):
    _assert_no_crash(r, label)
    assert r.returncode != 0, (
        f"{label}: the oversize message was accepted (exit 0); it must be refused."
        f"\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    )
    err = r.stderr.lower()
    # A single label or any of several acceptable subsystem names. When a check
    # legitimately lives in more than one place (e.g. instruction.md paragraph 3
    # lets the per-message parse path own the protocol-maximum check that the
    # shared header helper also owns), any of the allowed labels is accepted.
    subsystems = (subsystem,) if isinstance(subsystem, str) else tuple(subsystem)
    assert any(s in err for s in subsystems), (
        f"{label}: rejection must lead with the subsystem name "
        f"{' or '.join(repr(s) for s in subsystems)}.\n"
        f"stderr:\n{r.stderr}"
    )
    assert any(w in err for w in RESOURCE_WORDS), (
        f"{label}: rejection must name the exceeded resource.\nstderr:\n{r.stderr}"
    )


def _assert_send_refused(r, label):
    # The send path must surface the encoder's refusal rather than swallow it.
    # The spec leaves the surfaced prefix ambiguous (the refusal "came from" the
    # encoder, e.g. "framing:", and the send path propagates it), so we do not
    # require a literal "send" prefix. Proof of non-swallow: the command exits
    # non-zero (it did not transmit) and stderr carries the propagated encode
    # refusal that names the exceeded resource.
    _assert_no_crash(r, label)
    assert r.returncode != 0, (
        f"{label}: the send path transmitted the unframeable message (exit 0); "
        f"the encode refusal was swallowed instead of surfaced.\n"
        f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    )
    err = r.stderr.lower()
    assert any(w in err for w in RESOURCE_WORDS), (
        f"{label}: the send path must surface the propagated encode refusal "
        f"naming the exceeded resource, not swallow it.\nstderr:\n{r.stderr}"
    )


def test_binary_builds_and_reports_usage(binary):
    """Starter plus the agent edits must build a runnable framewire binary."""
    r = subprocess.run([binary], text=True, capture_output=True, timeout=10)
    assert r.returncode == 2, (
        f"bare binary should exit 2 with usage; got {r.returncode}"
    )
    assert "usage" in r.stderr.lower(), r.stderr


def test_valid_corpus_accepts(binary):
    """Every ordinary small message must still encode cleanly."""
    for i in ORDINARY_VALIDS:
        r = frame(binary, f"testdata/valid/valid_{i:03d}.frame")
        assert r.returncode == 0, (
            f"valid_{i:03d} rejected by the patched encoder.\nstderr:\n{r.stderr}"
        )


def test_boundary_at_limit_accepts(binary):
    """Messages whose body sits exactly at the protocol maximum must still pass."""
    for i in BOUNDARY_VALIDS:
        r = frame(binary, f"testdata/valid/valid_{i:03d}.frame")
        assert r.returncode == 0, (
            f"boundary valid_{i:03d} (at the edge, must still encode) was rejected; "
            f"a size or count guard is too aggressive.\nstderr:\n{r.stderr}"
        )


def test_valid_send_path(binary):
    """The frontend send path must transmit a well-formed message cleanly."""
    r = send(binary, "testdata/valid/valid_001.frame")
    assert r.returncode == 0, f"send of a valid message failed.\nstderr:\n{r.stderr}"


def test_query_oversize_rejected(binary):
    """An over-limit query body must be refused, not narrowed into the prefix."""
    r = frame(binary, "testdata/exploits/case_02.frame")
    _assert_clean_reject(r, "query oversize", "query")


def test_query_framing_prefix_matches_body(binary):
    """If a query is emitted, its four byte length prefix must equal the true body."""
    r = frame(binary, "testdata/exploits/case_02.frame")
    _assert_no_crash(r, "query framing")
    if r.returncode == 0:
        declared = _parse_kv(r.stdout, "declared")
        intended = _parse_kv(r.stdout, "intended")
        assert declared == intended, (
            f"query.go emitted a frame whose length prefix ({declared}) disagrees "
            f"with the real body length ({intended}); the prefix was narrowed past "
            "the protocol maximum and the stream can be re-split by a peer."
        )


def test_bind_aggregate_oversize_rejected(binary):
    """A bind whose parameters overflow the body in aggregate must be refused."""
    r = frame(binary, "testdata/exploits/case_08.frame")
    _assert_clean_reject(r, "bind aggregate", "bind")


def test_copydata_bulk_oversize_rejected(binary):
    """An over-limit bulk copy body must be refused."""
    r = frame(binary, "testdata/exploits/case_04.frame")
    _assert_clean_reject(r, "copydata bulk", "copydata")


def test_framing_wrong_ceiling_rejected(binary):
    """A body above the protocol maximum but below two gigabytes must be refused.

    case_06 drives a parse spec, so the check may live in the shared header
    helper (leading with 'framing') or in the per-message parse path (leading
    with 'parse'); instruction.md paragraph 3 allows the message kind to own a
    per-message check. Either clean refusal is accepted."""
    r = frame(binary, "testdata/exploits/case_06.frame")
    _assert_clean_reject(r, "framing between", ("framing", "parse"))


def test_funcall_narrow_oversize_rejected(binary):
    """A body whose length wraps a narrowed size check must still be refused."""
    r = frame(binary, "testdata/exploits/case_07.frame")
    _assert_clean_reject(r, "funcall narrow", "funcall")


def test_batch_multiply_oversize_rejected(binary):
    """A count times element size that overflows the check must be refused."""
    r = frame(binary, "testdata/exploits/case_01.frame")
    _assert_clean_reject(r, "batch multiply", "batch")


def test_formats_count_oversize_rejected(binary):
    """An element count too large for its on-wire field must be refused."""
    r = frame(binary, "testdata/exploits/case_05.frame")
    _assert_clean_reject(r, "formats count", "formats")


def test_send_propagates_encode_error(binary):
    """The send path must surface an encode refusal instead of swallowing it."""
    r = send(binary, "testdata/exploits/case_03.frame")
    _assert_send_refused(r, "send swallow")


def test_query_encode_caps_body(binary):
    """query.go Encode must bound its body or route through the capped helper."""
    body = _extract_func_body(
        _read_src("query.go"), r"func\s*\(\s*m\s*\*QueryMessage\s*\)\s*Encode\s*\("
    )
    assert body, "query.go: could not find QueryMessage.Encode body"
    assert _caps_or_delegates(body, _read_pkg_concat()), (
        "query.go Encode narrows the body length to int32 with no protocol-maximum "
        "check and no delegation to the capped framing helper."
    )


def test_bind_encode_caps_body(binary):
    """bind.go Encode must bound its aggregate body or route through the helper."""
    body = _extract_func_body(
        _read_src("bind.go"), r"func\s*\(\s*m\s*\*BindMessage\s*\)\s*Encode\s*\("
    )
    assert body, "bind.go: could not find BindMessage.Encode body"
    assert _caps_or_delegates(body, _read_pkg_concat()), (
        "bind.go Encode narrows the aggregate body length with no protocol-maximum "
        "check and no delegation to the capped framing helper."
    )


def test_copydata_encode_caps_body(binary):
    """copy_data.go Encode must bound its bulk body or route through the helper."""
    body = _extract_func_body(
        _read_src("copy_data.go"),
        r"func\s*\(\s*m\s*\*CopyDataMessage\s*\)\s*Encode\s*\(",
    )
    assert body, "copy_data.go: could not find CopyDataMessage.Encode body"
    assert _caps_or_delegates(body, _read_pkg_concat()), (
        "copy_data.go Encode narrows the bulk body length with no protocol-maximum "
        "check and no delegation to the capped framing helper."
    )


def test_framing_uses_protocol_limit(binary):
    """The frame must be bounded at the protocol maximum, not two gigabytes.

    The bound may live in the shared header helper (finishHeader in framing.go)
    or in the per-message parse path (ParseMessage.Encode in parse.go), since
    instruction.md paragraph 3 lets the message kind own a per-message check.
    Either location satisfies the contract; the starter, which bounds against
    the signed 32 bit maximum in neither, does not."""
    pkg = _read_pkg_concat()
    header = _extract_func_body(_read_src("framing.go"), r"func\s+finishHeader\s*\(")
    assert header, "framing.go: could not find finishHeader body"
    parse = _extract_func_body(
        _read_src("parse.go"), r"func\s*\(\s*m\s*\*ParseMessage\s*\)\s*Encode\s*\("
    )
    assert parse, "parse.go: could not find ParseMessage.Encode body"
    assert _uses_protocol_limit(header, pkg) or _uses_protocol_limit(parse, pkg), (
        "neither finishHeader (framing.go) nor the parse path (parse.go) bounds the "
        "frame length at the PostgreSQL protocol maximum; both leave bodies between "
        "the protocol maximum and two gigabytes able to pass, so bodies between the "
        "protocol maximum and two gigabytes still encode."
    )


def test_send_captures_encode_error(binary):
    """Frontend.Send must capture and check the error returned by Encode."""
    body = _extract_func_body(
        _read_src("frontend.go"), r"func\s*\(\s*f\s*\*Frontend\s*\)\s*Send\s*\("
    )
    assert body, "frontend.go: could not find Frontend.Send body"
    assert _send_captures_encode_error(body), (
        "frontend.go Send discards the error returned by Encode (assigns it to _ or "
        "never checks it), so an encode refusal never reaches the caller."
    )


def test_generated_query_oversize_rejected(binary, tmp_path):
    """A freshly sized over-limit query must be refused, not just the shipped one."""
    fill = random.randint(MAX_FRAME, MAX_FRAME + 5_000_000)
    spec = _write_spec(
        tmp_path, "gen_query.frame", ["kind=query", "content=", f"fill={fill}"]
    )
    r = _run(binary, "frame", spec)
    _assert_clean_reject(r, "generated query", "query")


def test_generated_bind_aggregate_rejected(binary, tmp_path):
    """A freshly split over-limit bind aggregate must be refused."""
    parts = [random.randint(150_000_000, 200_000_000) for _ in range(7)]
    spec = _write_spec(
        tmp_path,
        "gen_bind.frame",
        ["kind=bind", "portal=", "stmt=g", "params=" + ",".join(str(p) for p in parts)],
    )
    r = _run(binary, "frame", spec)
    _assert_clean_reject(r, "generated bind", "bind")


def test_generated_bind_param_count_rejected(binary, tmp_path):
    """A bind whose parameter count overruns its on-wire field must be refused
    even when the aggregate body stays under the protocol maximum."""
    n = random.randint(65_600, 66_100)
    parts = ["1"] * n
    spec = _write_spec(
        tmp_path,
        "gen_bind_count.frame",
        ["kind=bind", "portal=", "stmt=g", "params=" + ",".join(parts)],
    )
    r = _run(binary, "frame", spec)
    _assert_clean_reject(r, "generated bind param count", "bind")


def test_generated_bind_param_count_boundary_accepts(binary, tmp_path):
    """A bind carrying exactly the largest representable parameter count must
    still encode; a guard that also rejects the boundary is too aggressive."""
    parts = ["1"] * 0xFFFF
    spec = _write_spec(
        tmp_path,
        "gen_bind_count_edge.frame",
        ["kind=bind", "portal=", "stmt=g", "params=" + ",".join(parts)],
    )
    r = _run(binary, "frame", spec)
    _assert_no_crash(r, "bind param count boundary")
    assert r.returncode == 0, (
        f"a bind at the largest legal parameter count was rejected; the count "
        f"guard is too aggressive.\nstderr:\n{r.stderr}"
    )


def test_generated_copydata_rejected(binary, tmp_path):
    """A freshly sized over-limit bulk copy must be refused."""
    fill = random.randint(MAX_FRAME, MAX_FRAME + 5_000_000)
    spec = _write_spec(
        tmp_path, "gen_copy.frame", ["kind=copydata", "content=", f"fill={fill}"]
    )
    r = _run(binary, "frame", spec)
    _assert_clean_reject(r, "generated copydata", "copydata")


def test_generated_framing_between_rejected(binary, tmp_path):
    """A freshly sized between-limit body must be refused, whether the check
    lives in the shared header helper ('framing') or in the per-message parse
    path ('parse'); instruction.md paragraph 3 allows the message kind to own a
    per-message check. Either clean refusal is accepted."""
    fill = random.randint(1_200_000_000, 2_000_000_000)
    spec = _write_spec(
        tmp_path, "gen_parse.frame", ["kind=parse", "stmt=", "content=", f"fill={fill}"]
    )
    r = _run(binary, "frame", spec)
    _assert_clean_reject(r, "generated framing", ("framing", "parse"))


def test_generated_send_swallow_rejected(binary, tmp_path):
    """A freshly sized unframeable message must be refused by the send path."""
    fill = random.randint(2_200_000_000, 3_000_000_000)
    spec = _write_spec(
        tmp_path, "gen_send.frame", ["kind=parse", "stmt=", "content=", f"fill={fill}"]
    )
    r = _run(binary, "send", spec)
    _assert_send_refused(r, "generated send")


def test_generated_funcall_narrow_rejected(binary, tmp_path):
    """A freshly sized body past the signed 32 bit edge must be refused."""
    fill = random.randint(2_147_483_648, 2_900_000_000)
    spec = _write_spec(
        tmp_path, "gen_funcall.frame", ["kind=funcall", "content=", f"fill={fill}"]
    )
    r = _run(binary, "frame", spec)
    _assert_clean_reject(r, "generated funcall", "funcall")


def test_generated_batch_multiply_rejected(binary, tmp_path):
    """A freshly sized count times element size overflow must be refused."""
    count = random.randint(1_000_000, 1_050_000)
    spec = _write_spec(
        tmp_path,
        "gen_batch.frame",
        ["kind=batch", f"count={count}", "elemsize=5000"],
    )
    r = _run(binary, "frame", spec)
    _assert_clean_reject(r, "generated batch", "batch")


def test_generated_formats_count_rejected(binary, tmp_path):
    """A freshly sized over-cap element count must be refused."""
    count = random.randint(70_000, 120_000)
    spec = _write_spec(
        tmp_path, "gen_formats.frame", ["kind=formats", f"count={count}"]
    )
    r = _run(binary, "frame", spec)
    _assert_clean_reject(r, "generated formats", "formats")


def test_no_go_crash_on_any_exploit(binary):
    """No exploit spec may drive the encoder into a Go panic or runtime crash."""
    for f in sorted((ENV / "testdata" / "exploits").glob("*.frame")):
        r = frame(binary, f"testdata/exploits/{f.name}")
        _assert_no_crash(r, f.name)


def test_security_notes_covers_all_themes():
    """security_notes.md must name every subsystem, both CWE ids, and attribution."""
    notes = ENV / "security_notes.md"
    assert notes.exists(), (
        "security_notes.md was not written to /app/environment; instruction.md asks "
        "for it as a deliverable."
    )
    body = notes.read_text().lower()
    themes = (
        "query",
        "bind",
        "copydata",
        "framing",
        "send",
        "funcall",
        "batch",
        "formats",
    )
    for theme in themes:
        assert theme in body, f"security_notes.md missing subsystem theme '{theme}'"
    for kw in ("cwe-190", "cwe-89", "mit"):
        assert kw in body, f"security_notes.md missing keyword '{kw}'"
    assert "pgx" in body or "postgres" in body, (
        "security_notes.md missing the upstream attribution (pgx or postgres)"
    )
