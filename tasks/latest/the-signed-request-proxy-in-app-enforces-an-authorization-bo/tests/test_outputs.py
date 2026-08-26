"""Behavioral verifier for request-signature proxy canonicalization."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from backend_server import (  # noqa: E402
    assert_capture_matches_expected,
    capture_body_bytes,
    capture_body_digest,
    capture_headers_lower,
    load_capture,
)
from harness import (  # noqa: E402
    APP,
    CaseContext,
    response_json,
    response_status,
)
from request_factory import (  # noqa: E402
    BODY_LIMIT,
    CACHE_PROFILE_B,
    CURRENT_PROFILE,
    LEGACY_PROFILE,
    build_raw_request,
    build_semantic_from_wire,
    derive_hex,
    expected_backend_capture,
    normalize_target,
    seeded_bytes,
    seeded_nonce,
    seeded_request_id,
    write_keyring,
    write_profile,
    write_proxy_config,
)
from signature_factory import derive_secret, expected_canonical_digest  # noqa: E402

FIXTURE_MANIFEST = TESTS_DIR / "fixture_manifest.json"
TRACE_SCHEMA = TESTS_DIR / "schemas" / "request-trace.schema.json"


def _assert_trace_envelope(
    trace: dict[str, object],
    *,
    expected_run_mode: str,
) -> None:
    """Verify required top-level request-trace metadata."""
    schema = json.loads(TRACE_SCHEMA.read_text(encoding="utf-8"))
    required = set(schema["required"])

    missing = sorted(required - set(trace))
    assert not missing, f"request trace missing top-level fields: {missing}"

    schema_version = trace["schema_version"]
    run_mode = trace["run_mode"]
    catalog_digest = trace["catalog_digest"]
    entries = trace["entries"]

    assert isinstance(schema_version, str) and schema_version
    assert run_mode == expected_run_mode
    assert isinstance(catalog_digest, str) and len(catalog_digest) == 64
    assert all(char in "0123456789abcdef" for char in catalog_digest)
    assert isinstance(entries, list)


def _load_single_spool_record(
    ctx: CaseContext,
) -> tuple[Path, dict[str, object]]:
    """Load the only spool metadata record for this verifier case."""
    paths = ctx.spool_records()
    assert len(paths) == 1, (
        f"expected one spool record, found {[str(path) for path in paths]}"
    )
    path = paths[0]
    return path, json.loads(path.read_text(encoding="utf-8"))


def _queue_valid_pending_spool_record(
    ctx: CaseContext,
    test_name: str,
) -> tuple[object, Path]:
    """Queue one valid chunked request offline and return its semantic request and spool path."""
    secret = _bootstrap_case(ctx, test_name, profiles=[CURRENT_PROFILE], replay_on_start=False)
    headers = {
        "Host": ["api.local"],
        "Content-Type": ["application/json"],
    }
    header_order = ["Host", "Content-Type"]
    body = seeded_bytes(test_name, "pending-spool-body", size=32)
    sem = build_semantic_from_wire(
        test_name=test_name,
        profile=CURRENT_PROFILE,
        tenant="vtenant",
        key_id="vkey-1",
        key_epoch=1,
        method="POST",
        authority="api.local",
        wire_target="/v1/pending-spool",
        headers=headers,
        header_order=header_order,
        body=body,
        request_nonce=seeded_nonce(test_name, "pending-spool"),
        request_id=seeded_request_id(test_name, "pending-spool"),
    )
    ctx.start_proxy(backend_online=False)
    raw = build_raw_request(
        sem,
        secret,
        extra_headers=[("Content-Type", "application/json")],
        chunked=True,
        chunk_size=11,
    )
    resp = ctx.send_raw(raw)
    assert response_status(resp) == 202
    ctx.stop_proxy()
    spool_path, record = _load_single_spool_record(ctx)
    assert record["state"] == "pending"
    assert record["replay_count"] == 0
    return sem, spool_path


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _default_keyring_entry(test_name: str, *, profile_ids: list[str], versions: list[int]) -> dict:
    secret = derive_secret(test_name)
    return {
        "tenant": "vtenant",
        "key_id": "vkey-1",
        "key_epoch": 1,
        "secret_hex": secret.hex(),
        "allowed_profiles": profile_ids,
        "allowed_versions": versions,
        "revoked": False,
    }


def _bootstrap_case(
    ctx: CaseContext,
    test_name: str,
    *,
    profiles: list,
    replay_on_start: bool = False,
) -> bytes:
    ctx.prepare_dirs()
    for profile in profiles:
        write_profile(ctx.profiles_dir / f"{profile.profile_id}.json", profile)
    write_keyring(ctx.keyring_path, [_default_keyring_entry(test_name, profile_ids=[p.profile_id for p in profiles], versions=[1, 2])])
    write_proxy_config(
        ctx.config_path,
        listen_unix=str(ctx.proxy_sock),
        backend_unix=str(ctx.backend_sock),
        state_dir=str(ctx.state_dir),
        audit_log=str(ctx.audit_log),
        profiles_dir=str(ctx.profiles_dir),
        keyring_path=str(ctx.keyring_path),
        ready_file=str(ctx.ready_file),
        spool_seal_key_hex=derive_hex(test_name, "spool-seal", 32),
        replay_on_start=replay_on_start,
    )
    return derive_secret(test_name)


@pytest.fixture
def case(request: pytest.FixtureRequest) -> CaseContext:
    ctx = CaseContext(request.node.name)
    yield ctx
    ctx.cleanup()


def test_current_simple_signature_forwards_documented_semantics(case: CaseContext) -> None:
    """Valid current-profile HMAC requests forward the documented semantic backend request."""
    name = case.test_name
    secret = _bootstrap_case(case, name, profiles=[CURRENT_PROFILE])
    body = b'{"item":42}'
    headers = {
        "Host": ["api.local"],
        "Content-Type": ["application/json"],
    }
    header_order = ["Host", "Content-Type"]
    sem = build_semantic_from_wire(
        test_name=name,
        profile=CURRENT_PROFILE,
        tenant="vtenant",
        key_id="vkey-1",
        key_epoch=1,
        method="POST",
        authority="api.local",
        wire_target="/v1/items",
        headers=headers,
        header_order=header_order,
        body=body,
    )
    case.start_backend()
    case.start_proxy()
    raw = build_raw_request(sem, secret, extra_headers=[("Content-Type", "application/json")])
    resp = case.send_raw(raw)
    assert response_status(resp) == 200
    capture = load_capture(case.capture_path)
    assert_capture_matches_expected(capture, expected_backend_capture(sem))
    trace = case.read_trace()
    _assert_trace_envelope(trace, expected_run_mode="serve")
    entry = trace["entries"][-1]
    assert entry["decision"] == "allow"
    assert entry["canonical_target"] == sem.canonical_target
    assert entry["body_sha256"] == sem.entity_body_sha256
    assert entry["canonical_digest"] == expected_canonical_digest(sem)


def test_legacy_signature_remains_supported_without_fallback(case: CaseContext) -> None:
    """Legacy v1 signatures forward under legacy rules; malformed v2 attempts are rejected without fallback."""
    name = case.test_name
    secret = _bootstrap_case(case, name, profiles=[LEGACY_PROFILE, CURRENT_PROFILE])
    headers = {"Host": ["legacy.local"]}
    header_order = ["Host"]
    legacy_sem = build_semantic_from_wire(
        test_name=name,
        profile=LEGACY_PROFILE,
        tenant="vtenant",
        key_id="vkey-1",
        key_epoch=1,
        method="GET",
        authority="legacy.local",
        wire_target="/health",
        headers=headers,
        header_order=header_order,
        body=b"",
        request_nonce=seeded_nonce(name, "legacy"),
        request_id=seeded_request_id(name, "legacy"),
    )
    case.start_backend()
    case.start_proxy()
    ok_raw = build_raw_request(legacy_sem, secret)
    ok_resp = case.send_raw(ok_raw)
    assert response_status(ok_resp) == 200
    capture = load_capture(case.capture_path)
    assert capture["method"] == "GET"
    assert capture["target"] == "/health"

    bad_sem = build_semantic_from_wire(
        test_name=name,
        profile=LEGACY_PROFILE,
        tenant="vtenant",
        key_id="vkey-1",
        key_epoch=1,
        method="GET",
        authority="legacy.local",
        wire_target="/health",
        headers=headers,
        header_order=header_order,
        body=b"",
        request_nonce=seeded_nonce(name, "bad"),
        request_id=seeded_request_id(name, "bad"),
    )
    bad_raw = bytearray(build_raw_request(bad_sem, secret))
    bad_raw = bad_raw.replace(b"X-Signature: v1 ", b"X-Signature: v2 ", 1)
    bad_resp = case.send_raw(bytes(bad_raw))
    assert response_status(bad_resp) == 401
    assert response_json(bad_resp).get("reason") in {
        "signature_version_mismatch",
        "signature_mismatch",
        "malformed_signature_header",
    }


def test_connection_nominated_header_is_neither_signed_nor_forwarded(case: CaseContext) -> None:
    """Connection-nominated headers are excluded from signed semantics and backend capture."""
    name = case.test_name
    secret = _bootstrap_case(case, name, profiles=[CURRENT_PROFILE])
    headers = {
        "Host": ["api.local"],
        "Content-Type": ["application/json"],
        "Accept": ["text/plain", " application/json"],
        "Connection": ["x-shadow"],
        "X-Shadow": ["injected"],
    }
    header_order = ["Host", "Connection", "X-Shadow", "Accept", "Accept", "Content-Type"]
    sem = build_semantic_from_wire(
        test_name=name,
        profile=CURRENT_PROFILE,
        tenant="vtenant",
        key_id="vkey-1",
        key_epoch=1,
        method="GET",
        authority="api.local",
        wire_target="/v1/shadow",
        headers=headers,
        header_order=header_order,
        body=b"",
    )
    case.start_backend()
    case.start_proxy()
    raw = build_raw_request(
        sem,
        secret,
        extra_headers=[
            ("Connection", "x-shadow"),
            ("X-Shadow", "injected"),
            ("Accept", "text/plain"),
            ("Accept", " application/json"),
            ("Content-Type", "application/json"),
        ],
    )
    resp = case.send_raw(raw)
    assert response_status(resp) == 200
    capture = load_capture(case.capture_path)
    assert "X-Shadow" not in capture["headers"]
    assert "Connection" not in capture["headers"]
    lowered = capture_headers_lower(capture)
    assert lowered.get("accept") == "text/plain, application/json"
    trace = case.read_trace()["entries"][-1]
    assert "x-shadow" not in {k.lower() for k in trace["canonical_headers"]}


def test_valid_repeated_list_headers_preserve_profile_order(case: CaseContext) -> None:
    """Joinable list headers keep wire occurrence order after normalization."""
    name = case.test_name
    secret = _bootstrap_case(case, name, profiles=[CURRENT_PROFILE])
    headers = {
        "Host": ["api.local"],
        "Accept": ["text/plain", " application/json"],
        "X-Test-List": ["alpha", " beta", "gamma "],
    }
    header_order = ["Host", "Accept", "Accept", "X-Test-List", "X-Test-List", "X-Test-List"]
    sem = build_semantic_from_wire(
        test_name=name,
        profile=CURRENT_PROFILE,
        tenant="vtenant",
        key_id="vkey-1",
        key_epoch=1,
        method="GET",
        authority="api.local",
        wire_target="/v1/lists",
        headers=headers,
        header_order=header_order,
        body=b"",
    )
    joined = {h.name: h.value for h in sem.canonical_headers}
    assert joined["accept"] == "text/plain, application/json"
    assert joined["x-test-list"] == "alpha, beta, gamma"
    case.start_backend()
    case.start_proxy()
    raw = build_raw_request(
        sem,
        secret,
        extra_headers=[
            ("Accept", "text/plain"),
            ("Accept", " application/json"),
            ("X-Test-List", "alpha"),
            ("X-Test-List", " beta"),
            ("X-Test-List", "gamma "),
        ],
    )
    resp = case.send_raw(raw)
    assert response_status(resp) == 200
    capture = load_capture(case.capture_path)
    assert capture_headers_lower(capture)["accept"] == "text/plain, application/json"
    assert capture_headers_lower(capture)["x-test-list"] == "alpha, beta, gamma"


def test_duplicate_singleton_is_rejected_before_backend_contact(case: CaseContext) -> None:
    """Duplicate singleton metadata is rejected before backend contact or spool writes."""
    name = case.test_name
    secret = _bootstrap_case(case, name, profiles=[CURRENT_PROFILE])
    sign_headers = {"Host": ["api.local"], "Content-Type": ["application/json"]}
    sem = build_semantic_from_wire(
        test_name=name,
        profile=CURRENT_PROFILE,
        tenant="vtenant",
        key_id="vkey-1",
        key_epoch=1,
        method="POST",
        authority="api.local",
        wire_target="/v1/dup",
        headers=sign_headers,
        header_order=["Host", "Content-Type"],
        body=b"{}",
    )
    case.start_backend()
    case.start_proxy()
    raw = build_raw_request(
        sem,
        secret,
        extra_headers=[("Host", "api.local"), ("Host", "other.local"), ("Content-Type", "application/json")],
    )
    resp = case.send_raw(raw)
    assert response_status(resp) == 401
    assert response_json(resp).get("reason") == "header_policy_violation"
    assert not case.capture_path.exists()
    assert case.spool_records() == []


def test_encoded_path_and_repeated_query_match_current_profile(case: CaseContext) -> None:
    """Percent-encoded paths and repeated query keys normalize to the current profile target."""
    name = case.test_name
    secret = _bootstrap_case(case, name, profiles=[CURRENT_PROFILE])
    wire_target = "/v1/%66oo/bar%2Finish?q=1&q="
    expected = normalize_target(CURRENT_PROFILE, wire_target)
    headers = {"Host": ["api.local"]}
    sem = build_semantic_from_wire(
        test_name=name,
        profile=CURRENT_PROFILE,
        tenant="vtenant",
        key_id="vkey-1",
        key_epoch=1,
        method="GET",
        authority="api.local",
        wire_target=wire_target,
        headers=headers,
        header_order=["Host"],
        body=b"",
    )
    case.start_backend()
    case.start_proxy()
    resp = case.send_raw(build_raw_request(sem, secret))
    assert response_status(resp) == 200
    capture = load_capture(case.capture_path)
    assert capture["target"] == expected


def test_chunked_and_content_length_forms_bind_same_entity_body(case: CaseContext) -> None:
    """Chunked and Content-Length encodings with the same entity body produce identical backend bytes."""
    name = case.test_name
    secret = _bootstrap_case(case, name, profiles=[CURRENT_PROFILE])
    body = seeded_bytes(name, "chunk-body", size=64)
    headers = {"Host": ["api.local"], "Content-Type": ["application/octet-stream"]}
    header_order = ["Host", "Content-Type"]
    sem = build_semantic_from_wire(
        test_name=name,
        profile=CURRENT_PROFILE,
        tenant="vtenant",
        key_id="vkey-1",
        key_epoch=1,
        method="PUT",
        authority="api.local",
        wire_target="/v1/blob",
        headers=headers,
        header_order=header_order,
        body=body,
        request_nonce=seeded_nonce(name, "chunk"),
        request_id=seeded_request_id(name, "chunk"),
    )
    expected_digest = sem.entity_body_sha256
    forms: list[bytes] = [
        build_raw_request(sem, secret, extra_headers=[("Content-Type", "application/octet-stream")]),
        build_raw_request(
            sem,
            secret,
            extra_headers=[("Content-Type", "application/octet-stream")],
            chunked=True,
            chunk_size=17,
        ),
        build_raw_request(
            sem,
            secret,
            extra_headers=[("Content-Type", "application/octet-stream")],
            chunked=True,
            chunk_size=5,
        ),
    ]
    captures: list[dict] = []
    for idx, raw in enumerate(forms):
        case.stop_proxy()
        case.stop_backend()
        case.prepare_dirs()
        _bootstrap_case(case, name, profiles=[CURRENT_PROFILE])
        case.start_backend()
        case.start_proxy()
        resp = case.send_raw(raw)
        assert response_status(resp) == 200, f"form {idx} failed"
        capture = load_capture(case.capture_path)
        captures.append(capture)
    for capture in captures:
        assert capture_body_digest(capture) == expected_digest
        assert capture["headers"]["Content-Length"] == str(len(body))
    assert capture_body_bytes(captures[0]) == capture_body_bytes(captures[1]) == capture_body_bytes(captures[2])


def test_body_limit_rejects_before_forward_or_spool(case: CaseContext) -> None:
    """Bodies above the 1048576-byte entity limit are rejected without forward or spool."""
    name = case.test_name
    secret = _bootstrap_case(case, name, profiles=[CURRENT_PROFILE])
    headers = {"Host": ["api.local"], "Content-Type": ["application/octet-stream"]}
    at_limit = seeded_bytes(name, "at-limit", size=BODY_LIMIT)
    over_limit = at_limit + b"x"
    for label, body, expect_ok in (
        ("at-limit", at_limit, True),
        ("over-limit", over_limit, False),
    ):
        case.stop_proxy()
        case.stop_backend()
        case.prepare_dirs()
        _bootstrap_case(case, name, profiles=[CURRENT_PROFILE])
        sem = build_semantic_from_wire(
            test_name=name,
            profile=CURRENT_PROFILE,
            tenant="vtenant",
            key_id="vkey-1",
            key_epoch=1,
            method="POST",
            authority="api.local",
            wire_target=f"/v1/limit-{label}",
            headers=headers,
            header_order=["Host", "Content-Type"],
            body=body,
            request_nonce=seeded_nonce(name, label),
            request_id=seeded_request_id(name, label),
        )
        case.start_backend()
        case.start_proxy(backend_online=False)
        raw = build_raw_request(sem, secret, extra_headers=[("Content-Type", "application/octet-stream")])
        resp = case.send_raw(raw)
        if expect_ok:
            assert response_status(resp) == 202
            assert case.spool_records(), f"{label} should spool when backend offline"
        else:
            assert response_status(resp) == 413
            assert response_json(resp).get("reason") == "body_limit_exceeded"
            assert case.spool_records() == []
        case.stop_proxy()
        case.stop_backend()


def test_offline_spool_restart_replays_exact_semantic_request(case: CaseContext) -> None:
    """Queued requests recovered after restart forward the original sealed semantic request."""
    name = case.test_name
    secret = _bootstrap_case(case, name, profiles=[CURRENT_PROFILE], replay_on_start=False)
    wire_target = "/v1/%66oo/replay?q=a&q="
    headers = {
        "Host": ["api.local"],
        "Accept": ["one", " two"],
        "Content-Type": ["text/plain"],
    }
    header_order = ["Host", "Accept", "Accept", "Content-Type"]
    body = seeded_bytes(name, "replay-body", size=24)
    sem = build_semantic_from_wire(
        test_name=name,
        profile=CURRENT_PROFILE,
        tenant="vtenant",
        key_id="vkey-1",
        key_epoch=1,
        method="POST",
        authority="api.local",
        wire_target=wire_target,
        headers=headers,
        header_order=header_order,
        body=body,
    )
    case.start_proxy(backend_online=False)
    raw = build_raw_request(
        sem,
        secret,
        extra_headers=[
            ("Accept", "one"),
            ("Accept", " two"),
            ("Content-Type", "text/plain"),
        ],
        chunked=True,
        chunk_size=7,
    )
    queued = case.send_raw(raw)
    assert response_status(queued) == 202
    assert case.spool_records(), "expected one spool record"
    case.stop_proxy()

    case.start_backend()
    recover = case.run_recover()
    assert recover.returncode == 0, (
        f"recover failed\nstdout:\n{recover.stdout}\n"
        f"stderr:\n{recover.stderr}"
    )
    capture = load_capture(case.capture_path)
    assert_capture_matches_expected(capture, expected_backend_capture(sem))
    trace = case.read_trace()
    _assert_trace_envelope(trace, expected_run_mode="recover")
    spool_entries = [e for e in trace["entries"] if e.get("source") == "spool"]
    assert spool_entries, "trace must include spool-sourced entry"
    assert spool_entries[-1]["canonical_target"] == sem.canonical_target
    assert spool_entries[-1]["body_sha256"] == sem.entity_body_sha256


def test_authority_cache_reuses_same_scope_and_misses_new_profile_epoch(case: CaseContext) -> None:
    """Authority cache hits reuse scope and miss when profile epoch/catalog authority changes."""
    name = case.test_name
    secret = _bootstrap_case(case, name, profiles=[CURRENT_PROFILE, CACHE_PROFILE_B])
    headers = {"Host": ["api.local"], "Content-Type": ["application/json"]}
    header_order = ["Host", "Content-Type"]

    def make_sem(profile) -> object:
        return build_semantic_from_wire(
            test_name=name,
            profile=profile,
            tenant="vtenant",
            key_id="vkey-1",
            key_epoch=1,
            method="GET",
            authority="api.local",
            wire_target="/v1/cache",
            headers=headers,
            header_order=header_order,
            body=b"",
            request_nonce=seeded_nonce(name, profile.profile_id),
            request_id=seeded_request_id(name, profile.profile_id),
        )

    case.start_backend()
    case.start_proxy()
    hits: list[bool] = []
    for profile in (CURRENT_PROFILE, CURRENT_PROFILE, CACHE_PROFILE_B):
        sem = make_sem(profile)
        resp = case.send_raw(
            build_raw_request(sem, secret, extra_headers=[("Content-Type", "application/json")])
        )
        assert response_status(resp) == 200
        entry = case.read_trace()["entries"][-1]
        hits.append(entry["cache_hit"])
    assert hits[0] is False
    assert hits[1] is True
    assert hits[2] is False
    _assert_trace_envelope(case.read_trace(), expected_run_mode="serve")


def test_trace_and_audit_freeze_decision_time_evidence(case: CaseContext) -> None:
    """Trace and audit records preserve authorization evidence from decision time."""
    name = case.test_name
    secret = _bootstrap_case(case, name, profiles=[CURRENT_PROFILE])
    body = b"audit-freeze"
    headers = {
        "Host": ["api.local"],
        "Content-Type": ["text/plain"],
        "X-Order-Field": ["first", "second"],
    }
    header_order = ["Host", "Content-Type", "X-Order-Field", "X-Order-Field"]
    sem = build_semantic_from_wire(
        test_name=name,
        profile=CURRENT_PROFILE,
        tenant="vtenant",
        key_id="vkey-1",
        key_epoch=1,
        method="POST",
        authority="api.local",
        wire_target="/v1/audit",
        headers=headers,
        header_order=header_order,
        body=body,
    )
    expected_digest = expected_canonical_digest(sem)
    case.start_backend()
    case.start_proxy()
    raw = build_raw_request(
        sem,
        secret,
        extra_headers=[
            ("Content-Type", "text/plain"),
            ("X-Order-Field", "first"),
            ("X-Order-Field", "second"),
        ],
    )
    assert response_status(case.send_raw(raw)) == 200
    trace = case.read_trace()
    _assert_trace_envelope(trace, expected_run_mode="serve")
    trace_entry = trace["entries"][-1]
    assert trace_entry["canonical_digest"] == expected_digest
    assert trace_entry["canonical_target"] == sem.canonical_target
    assert trace_entry["body_sha256"] == sem.entity_body_sha256
    assert trace_entry.get("forward", {}).get("forwarded") is True
    audit_lines = case.read_audit_lines()
    assert audit_lines, "audit log must contain decision snapshot"
    audit = audit_lines[-1]
    assert audit["canonical_digest"] == expected_digest
    assert audit["canonical_target"] == sem.canonical_target
    assert audit["entity_body_sha256"] == sem.entity_body_sha256
    assert trace_entry.get("audit_record_digest") == audit["record_digest"]


def test_invalid_signature_never_reaches_backend_or_spool(case: CaseContext) -> None:
    """Cryptographically invalid or tampered requests never reach backend capture or spool."""
    name = case.test_name
    secret = _bootstrap_case(case, name, profiles=[CURRENT_PROFILE])
    headers = {"Host": ["api.local"], "Content-Type": ["application/json"]}
    sem = build_semantic_from_wire(
        test_name=name,
        profile=CURRENT_PROFILE,
        tenant="vtenant",
        key_id="vkey-1",
        key_epoch=1,
        method="POST",
        authority="api.local",
        wire_target="/v1/tamper",
        headers=headers,
        header_order=["Host", "Content-Type"],
        body=b"{}",
    )
    case.start_backend()
    case.start_proxy(backend_online=False)

    base_raw = build_raw_request(sem, secret, extra_headers=[("Content-Type", "application/json")])
    mutations = [
        lambda raw: raw.replace(b"POST ", b"PUT ", 1),
        lambda raw: raw.replace(b"/v1/tamper", b"/v1/other", 1),
        lambda raw: raw.replace(b"{}", b"[]", 1),
        lambda raw: raw.replace(b"X-Signature: v2 ", b"X-Signature: v2 deadbeef", 1),
    ]
    for mutate in mutations:
        case.stop_proxy()
        case.stop_backend()
        case.prepare_dirs()
        _bootstrap_case(case, name, profiles=[CURRENT_PROFILE])
        case.start_backend()
        case.start_proxy(backend_online=False)
        raw = mutate(base_raw)
        resp = case.send_raw(raw)
        assert response_status(resp) == 401
        assert not case.capture_path.exists()
        assert case.spool_records() == []
        case.stop_proxy()
        case.stop_backend()


def test_revoked_decision_time_key_epoch_quarantines_pending_spool(
    case: CaseContext,
) -> None:
    """A pending record under a revoked decision-time epoch is quarantined without forwarding."""
    name = case.test_name
    _sem, _spool_path = _queue_valid_pending_spool_record(case, name)
    _, record = _load_single_spool_record(case)
    record_id = record["record_id"]
    assert record["state"] == "pending"
    assert record["replay_count"] == 0
    assert record["semantic_request"]["key_epoch"] == 1

    revoked_epoch = _default_keyring_entry(
        name,
        profile_ids=[CURRENT_PROFILE.profile_id],
        versions=[1, 2],
    )
    revoked_epoch["revoked"] = True

    active_epoch = dict(revoked_epoch)
    active_epoch["key_epoch"] = 2
    active_epoch["secret_hex"] = derive_hex(name, "epoch-2-secret", 32)
    active_epoch["revoked"] = False

    write_keyring(case.keyring_path, [revoked_epoch, active_epoch])

    case.start_backend()
    if case.capture_path.exists():
        case.capture_path.unlink()

    recover = case.run_recover()
    assert recover.returncode == 0, (
        f"recover failed\nstdout:\n{recover.stdout}\n"
        f"stderr:\n{recover.stderr}"
    )
    assert not case.capture_path.exists()

    _, record = _load_single_spool_record(case)
    assert record["state"] == "quarantine"
    assert record["replay_count"] == 0
    assert record["semantic_request"]["key_epoch"] == 1
    assert record["record_id"] == record_id

    trace = case.read_trace()
    _assert_trace_envelope(trace, expected_run_mode="recover")
    for entry in trace["entries"]:
        forward = entry.get("forward") or {}
        assert forward.get("forwarded") is not True


def test_completed_spool_record_is_not_forwarded_on_later_recover(
    case: CaseContext,
) -> None:
    """A completed spool record remains completed and is not forwarded again."""
    name = case.test_name
    sem, spool_path = _queue_valid_pending_spool_record(case, name)

    case.start_backend()
    recover = case.run_recover()
    assert recover.returncode == 0, (
        f"recover failed\nstdout:\n{recover.stdout}\n"
        f"stderr:\n{recover.stderr}"
    )
    capture = load_capture(case.capture_path)
    assert_capture_matches_expected(capture, expected_backend_capture(sem))

    _, record = _load_single_spool_record(case)
    assert record["state"] == "completed"
    assert record["replay_count"] == 1

    first_trace = case.read_trace()
    _assert_trace_envelope(first_trace, expected_run_mode="recover")
    forwarded_entries = [
        e
        for e in first_trace["entries"]
        if e.get("source") == "spool" and (e.get("forward") or {}).get("forwarded") is True
    ]
    assert len(forwarded_entries) == 1

    completed_record = json.loads(spool_path.read_text(encoding="utf-8"))
    audit_count = len(case.read_audit_lines())

    case.capture_path.unlink()
    assert not case.capture_path.exists()

    second_recover = case.run_recover()
    assert second_recover.returncode == 0, (
        f"recover failed\nstdout:\n{second_recover.stdout}\n"
        f"stderr:\n{second_recover.stderr}"
    )
    assert not case.capture_path.exists()

    _, record = _load_single_spool_record(case)
    assert record["state"] == "completed"
    assert record["replay_count"] == 1
    assert record["record_id"] == completed_record["record_id"]
    assert record["decision_digest"] == completed_record["decision_digest"]
    assert record["semantic_request"] == completed_record["semantic_request"]
    assert record["seal"] == completed_record["seal"]
    assert len(case.read_audit_lines()) == audit_count

    second_trace = case.read_trace()
    _assert_trace_envelope(second_trace, expected_run_mode="recover")
    assert second_trace["entries"] == []


def test_public_contract_and_fixture_assets_are_unmodified() -> None:
    """Public contract files and demo fixtures remain unchanged from the verifier manifest."""
    manifest = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
    for rel_path, expected in manifest["files"].items():
        actual = _sha256_file(APP / rel_path)
        assert actual == expected, f"hash mismatch for {rel_path}: {actual} != {expected}"
