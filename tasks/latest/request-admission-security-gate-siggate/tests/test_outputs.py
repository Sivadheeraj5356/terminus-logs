"""Behavioral tests for the HRM-1 siggate verifier."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from hrm_reference import (
    DIGEST_BARE_STD,
    DIGEST_COLON_STD,
    OWS_HTAB,
    OWS_NBSP,
    OWS_SP,
    canon_query,
    content_digest,
    encode_profile,
    expected_mac,
    expected_ok_line,
    load_envelope,
    load_keyring,
)

APP = Path(os.environ.get("APP_ROOT", "/app"))
BIN = APP / "bin" / "siggate"
KEYRING = APP / "fixtures" / "keyring.json"
ENVELOPES = APP / "fixtures" / "envelopes"
NOW = "1700000100"

BASE_ENV: dict[str, Any] = {
    "method": "POST",
    "path": "/v1/orders",
    "query": [
        {"name": "region", "value": "us"},
        {"name": "tenant", "value": "acme"},
    ],
    "headers": {
        "Host": "api.example.test",
        "Content-Type": "application/json",
        "Authorization": "Bearer tok",
    },
    "body": '{"order_id":"o-1","amount":10}',
    "covered": ["authorization", "content-type", "host"],
    "created": 1700000000,
    "expires": 1700001000,
    "kid": "main",
    "mac": "",
}


def _workdir(tmp_path: Path | None = None) -> Path:
    if tmp_path is not None:
        tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path
    return Path(tempfile.mkdtemp(prefix="siggate-"))


def write_profile(
    dest: Path,
    *,
    order: list[int] | None = None,
    ows_mask: int = OWS_SP | OWS_HTAB,
    digest_mode: int = DIGEST_COLON_STD,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(
        encode_profile(order=order, ows_mask=ows_mask, digest_mode=digest_mode)
    )
    return dest


def run_verify(
    envelope: Path,
    *,
    now: str = NOW,
    seen: Path | None = None,
    profile: Path | None = None,
    profile_bytes: bytes | None = None,
    tmp_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    work = _workdir(tmp_path)
    if profile is None:
        profile = work / "site.profile"
    if profile_bytes is not None:
        Path(profile).parent.mkdir(parents=True, exist_ok=True)
        Path(profile).write_bytes(profile_bytes)
    elif not Path(profile).exists():
        write_profile(Path(profile))
    if seen is None:
        seen = work / f"seen-{envelope.name}.log"
        seen.write_text("", encoding="utf-8")
    cmd = [
        str(BIN),
        "verify",
        "--envelope",
        str(envelope),
        "--keyring",
        str(KEYRING),
        "--now",
        now,
        "--profile",
        str(profile),
        "--seen",
        str(seen),
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def mint(
    tmp_path: Path,
    name: str,
    keys: dict[str, bytes],
    *,
    ows_mask: int = OWS_SP | OWS_HTAB,
    digest_mode: int = DIGEST_COLON_STD,
    order: list[int] | None = None,
    profile_bytes: bytes | None = None,
    **patch: Any,
) -> tuple[Path, dict[str, Any]]:
    env = deepcopy(BASE_ENV)
    for k, v in patch.items():
        env[k] = v
    if profile_bytes is None:
        profile_bytes = encode_profile(
            order=order, ows_mask=ows_mask, digest_mode=digest_mode
        )
    env["mac"] = expected_mac(
        env,
        keys,
        ows_mask=ows_mask,
        digest_mode=digest_mode,
        order=order,
        profile_bytes=profile_bytes,
    )
    path = tmp_path / name
    path.write_text(json.dumps(env, ensure_ascii=False), encoding="utf-8")
    return path, env


@pytest.fixture(scope="module")
def keys() -> dict[str, bytes]:
    return load_keyring(KEYRING)


def test_binary_exists() -> None:
    """The rebuilt siggate binary must be present and executable."""
    assert BIN.is_file()
    assert os.access(BIN, os.X_OK)


def test_happy_path_matches_reference(keys: dict[str, bytes]) -> None:
    """Bundled happy envelope must verify and match the reference stdout line."""
    env_path = ENVELOPES / "happy.json"
    env = load_envelope(env_path)
    assert env["mac"] == expected_mac(env, keys)
    proc = run_verify(env_path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_idempotent_stdout_bytes(keys: dict[str, bytes]) -> None:
    """Repeated successful verifies must emit byte-identical stdout."""
    env_path = ENVELOPES / "happy.json"
    a = run_verify(env_path)
    b = run_verify(env_path)
    assert a.returncode == 0 and b.returncode == 0
    assert a.stdout == b.stdout == expected_ok_line(load_envelope(env_path), keys)


def test_expires_boundary_inclusive(keys: dict[str, bytes]) -> None:
    """now equal to expires must be accepted (inclusive upper bound)."""
    path = ENVELOPES / "expires-boundary.json"
    proc = run_verify(path, now=NOW)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(load_envelope(path), keys)


def test_created_boundary_inclusive(keys: dict[str, bytes]) -> None:
    """now equal to created must be accepted (inclusive lower bound)."""
    path = ENVELOPES / "created-boundary.json"
    proc = run_verify(path, now=NOW)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(load_envelope(path), keys)


def test_expires_one_past_rejected() -> None:
    """now = expires + 1 must fail expired."""
    path = ENVELOPES / "expires-boundary.json"
    env = load_envelope(path)
    proc = run_verify(path, now=str(int(env["expires"]) + 1))
    assert proc.returncode == 2
    assert proc.stderr == "error: expired\n"
    assert proc.stdout == ""


def test_created_one_before_rejected() -> None:
    """now = created - 1 must fail not_yet_valid."""
    path = ENVELOPES / "created-boundary.json"
    env = load_envelope(path)
    proc = run_verify(path, now=str(int(env["created"]) - 1))
    assert proc.returncode == 2
    assert proc.stderr == "error: not_yet_valid\n"


def test_duplicate_query_value_ordering(keys: dict[str, bytes]) -> None:
    """Duplicate-name query fixtures must verify against the HRM-1 reference MAC."""
    path = ENVELOPES / "dup-query.json"
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(load_envelope(path), keys)


def test_query_prefix_name_ordering(keys: dict[str, bytes]) -> None:
    """Prefix-sensitive query fixtures must verify against the HRM-1 reference MAC."""
    path = ENVELOPES / "query-prefix-trap.json"
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(load_envelope(path), keys)


def test_covered_header_order_preserved(keys: dict[str, bytes]) -> None:
    """Covered-order header fixtures must verify against the HRM-1 reference MAC."""
    path = ENVELOPES / "covered-order.json"
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(load_envelope(path), keys)


def test_header_internal_whitespace_preserved(keys: dict[str, bytes]) -> None:
    """Header whitespace fixtures must verify against the HRM-1 reference MAC."""
    path = ENVELOPES / "header-internal-ws.json"
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(load_envelope(path), keys)


def test_empty_body_digest(keys: dict[str, bytes]) -> None:
    """Empty bodies still produce a sha-256 content digest in the success line."""
    path = ENVELOPES / "empty-body.json"
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(load_envelope(path), keys)
    assert "sha-256=:" in proc.stdout


def test_rotate_kid(keys: dict[str, bytes]) -> None:
    """Non-default kid values from the keyring must verify."""
    path = ENVELOPES / "rotate-kid.json"
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(load_envelope(path), keys)


def test_bad_mac_rejected() -> None:
    """Tampered MAC values must fail with bad_mac."""
    proc = run_verify(ENVELOPES / "bad-mac.json")
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr == "error: bad_mac\n"


def test_expired_rejected() -> None:
    """now past expires must fail with expired."""
    proc = run_verify(ENVELOPES / "expired.json")
    assert proc.returncode == 2
    assert proc.stderr == "error: expired\n"


def test_not_yet_valid_rejected() -> None:
    """now before created must fail with not_yet_valid."""
    proc = run_verify(ENVELOPES / "not-yet.json")
    assert proc.returncode == 2
    assert proc.stderr == "error: not_yet_valid\n"


def test_replay_rejected(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """A second successful verify with the same seen-log identity must be replay."""
    seen = tmp_path / "seen.log"
    path = ENVELOPES / "replay-twin.json"
    first = run_verify(path, seen=seen)
    assert first.returncode == 0, first.stderr
    assert first.stdout == expected_ok_line(load_envelope(path), keys)
    second = run_verify(path, seen=seen)
    assert second.returncode == 2
    assert second.stderr == "error: replay\n"


def test_replay_seen_file_written(tmp_path: Path) -> None:
    """Successful verify with --seen must append kid|created|mac."""
    seen = tmp_path / "seen.log"
    path = ENVELOPES / "happy.json"
    env = load_envelope(path)
    proc = run_verify(path, seen=seen)
    assert proc.returncode == 0, proc.stderr
    line = f"{env['kid']}|{env['created']}|{env['mac']}"
    assert line in seen.read_text(encoding="utf-8").splitlines()


def test_path_dot_segments_preserved(keys: dict[str, bytes]) -> None:
    """Path `.` segments must remain literal in the MAC material."""
    path = ENVELOPES / "path-dot.json"
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(load_envelope(path), keys)


def test_path_trailing_slash_preserved(keys: dict[str, bytes]) -> None:
    """Trailing `/` on path must remain literal in the MAC material."""
    path = ENVELOPES / "path-slash.json"
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(load_envelope(path), keys)


def test_invalid_window_rejected() -> None:
    """expires before created must fail with invalid_window."""
    proc = run_verify(ENVELOPES / "invalid-window.json")
    assert proc.returncode == 2
    assert proc.stderr == "error: invalid_window\n"


def test_replay_match_is_exact_line(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Seen-log hits must be exact lines; superstring lines are not replays."""
    seen = tmp_path / "seen.log"
    path = ENVELOPES / "happy.json"
    env = load_envelope(path)
    identity = f"{env['kid']}|{env['created']}|{env['mac']}"
    seen.write_text(f"spam|{identity}|spam\n", encoding="utf-8")
    proc = run_verify(path, seen=seen)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_header_tab_interior_preserved(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Interior HTAB octets in header values must survive OWS edge trim."""
    path, env = mint(
        tmp_path,
        "header-tabs.json",
        keys,
        headers={
            "Host": "api.example.test",
            "Content-Type": "application/json",
            "Authorization": "Bearer\t\ttok",
        },
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_runtime_parent_path_segments(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Parent-directory segments in path must remain literal for the MAC."""
    path, env = mint(
        tmp_path,
        "path-parent.json",
        keys,
        path="/v1/a/../orders",
        covered=["host", "authorization", "content-type"],
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_replay_ignores_kid_mac_only_collision(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Seen entries matching only kid+mac (wrong created) must not count as replay."""
    path = ENVELOPES / "happy.json"
    env = load_envelope(path)
    seen = tmp_path / "seen.log"
    seen.write_text(f"{env['kid']}|999999999|{env['mac']}\n", encoding="utf-8")
    proc = run_verify(path, seen=seen)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_replay_allows_same_kid_different_identity(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Two envelopes sharing kid but differing created+mac must both succeed under --seen."""
    seen = tmp_path / "seen.log"
    first, env1 = mint(tmp_path, "r1.json", keys, created=1700000000, expires=1700001000)
    second, env2 = mint(tmp_path, "r2.json", keys, created=1700000001, expires=1700001000)
    assert env1["mac"] != env2["mac"]
    a = run_verify(first, seen=seen)
    b = run_verify(second, seen=seen)
    assert a.returncode == 0, a.stderr
    assert b.returncode == 0, b.stderr
    lines = seen.read_text(encoding="utf-8").splitlines()
    assert f"{env1['kid']}|{env1['created']}|{env1['mac']}" in lines
    assert f"{env2['kid']}|{env2['created']}|{env2['mac']}" in lines


def test_mac_with_base64_padding_rejected(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """base64url MAC must be unpadded; appending '=' must yield bad_mac."""
    path, env = mint(tmp_path, "pad.json", keys)
    env["mac"] = env["mac"] + "="
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path)
    assert proc.returncode == 2
    assert proc.stderr == "error: bad_mac\n"
    assert proc.stdout == ""


def test_query_space_not_percent_encoded(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Query values with spaces are literal; percent-encoding changes the MAC."""
    path, env = mint(
        tmp_path,
        "qspace.json",
        keys,
        query=[{"name": "q", "value": "a b"}, {"name": "z", "value": "1"}],
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_query_id_compound_prefix_ordering(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """id / id10 / id2 must sort by name bytes, not by 'name=value' string pins."""
    path, env = mint(
        tmp_path,
        "qid.json",
        keys,
        query=[
            {"name": "id10", "value": "a"},
            {"name": "id2", "value": "b"},
            {"name": "id", "value": "c"},
        ],
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_path_double_slash_preserved(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Double slashes in path must remain literal."""
    path, env = mint(tmp_path, "dbl.json", keys, path="//v1//orders")
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_query_empty_value(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Empty query values render as name= with nothing after '='."""
    path, env = mint(
        tmp_path,
        "qempty.json",
        keys,
        query=[{"name": "flag", "value": ""}, {"name": "a", "value": "1"}],
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_header_ows_edges_only(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Leading/trailing SP/HTAB trim; interior spacing of 'Bearer tok' stays."""
    path, env = mint(
        tmp_path,
        "ows.json",
        keys,
        headers={
            "Host": "api.example.test",
            "Content-Type": "application/json",
            "Authorization": "  Bearer tok\t",
        },
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_covered_mixed_case_lowered(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Covered names are matched case-insensitively but emitted lowercased in order."""
    path, env = mint(
        tmp_path,
        "cmix.json",
        keys,
        covered=["HOST", "Authorization", "content-type"],
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_body_unicode_digest(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Non-ASCII UTF-8 bodies affect the content digest and MAC."""
    path, env = mint(tmp_path, "uni.json", keys, body='{"note":"café-中"}')
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_empty_query_array(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Zero query params still contribute an empty canonical-query line."""
    path, env = mint(tmp_path, "noq.json", keys, query=[])
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_missing_covered_header_reason(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Absent covered header must fail with the exact reason token."""
    env = deepcopy(BASE_ENV)
    env["headers"] = {
        "Host": "api.example.test",
        "Content-Type": "application/json",
    }
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    path = tmp_path / "miss.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path)
    assert proc.returncode == 2
    assert proc.stderr == "error: missing_covered_header\n"
    assert proc.stdout == ""


def test_unknown_kid_reason(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Unknown kid must fail before MAC soft-errors."""
    env = deepcopy(BASE_ENV)
    env["kid"] = "no-such-key"
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    path = tmp_path / "kid.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path)
    assert proc.returncode == 2
    assert proc.stderr == "error: unknown_kid\n"


def test_path_must_be_absolute(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Paths without a leading slash are envelope_invalid."""
    env = deepcopy(BASE_ENV)
    env["path"] = "v1/orders"
    env["mac"] = expected_mac({**env, "path": "/v1/orders"}, keys)
    path = tmp_path / "rel.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path)
    assert proc.returncode == 2
    assert proc.stderr == "error: envelope_invalid\n"


def test_stdout_digest_uses_std_b64(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Success digest token uses standard base64 (with padding), not base64url."""
    path, env = mint(tmp_path, "dig.json", keys, body="x")
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)
    digest = proc.stdout.strip().split("digest=", 1)[1]
    assert digest.startswith("sha-256=:")
    assert digest.endswith(":")
    payload = digest[len("sha-256=:") : -1]
    assert "=" in payload


def test_zero_width_window_accepted(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """created == expires == now is valid (closed window), not invalid_window/expired."""
    ts = 1700000100
    path, env = mint(tmp_path, "zw.json", keys, created=ts, expires=ts)
    proc = run_verify(path, now=str(ts))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_seen_whitespace_padded_line_not_replay(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Seen membership is exact line equality; leading/trailing spaces do not match."""
    path, env = mint(tmp_path, "seen-ws.json", keys)
    identity = f"{env['kid']}|{env['created']}|{env['mac']}"
    seen = tmp_path / "seen.log"
    seen.write_text(f"  {identity}  \n", encoding="utf-8")
    proc = run_verify(path, seen=seen)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)
    lines = seen.read_text(encoding="utf-8").splitlines()
    assert identity in lines


def test_header_interior_double_space_preserved(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Multiple interior SP octets must not be collapsed (unlike HTTP field folding)."""
    path, env = mint(
        tmp_path,
        "hds.json",
        keys,
        headers={
            "Host": "api.example.test",
            "Content-Type": "application/json",
            "Authorization": "Bearer  tok",
        },
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_query_ampersand_in_value_literal(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Ampersands inside a value are literal; they must not split into extra pairs."""
    path, env = mint(
        tmp_path,
        "qamp.json",
        keys,
        query=[
            {"name": "filter", "value": "a&b=c"},
            {"name": "x", "value": "1"},
        ],
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_method_case_preserved_verbatim(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Method octets are taken from the envelope as-is; uppercasing changes the MAC."""
    path, env = mint(tmp_path, "meth.json", keys, method="post")
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_path_percent_octets_not_decoded(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Percent-encoded path octets stay literal; URL-decoding before MAC is wrong."""
    path, env = mint(tmp_path, "ppct.json", keys, path="/v1/%2e%2e/orders")
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_query_name_case_bytewise_sort(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Query names sort bytewise; ASCII uppercase precedes lowercase (no case-fold)."""
    path, env = mint(
        tmp_path,
        "qcase.json",
        keys,
        query=[
            {"name": "a", "value": "1"},
            {"name": "Z", "value": "2"},
        ],
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_query_plus_is_not_space(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """'+' in a query value is a literal plus, not an application/x-www-form-urlencoded space."""
    path, env = mint(
        tmp_path,
        "qplus.json",
        keys,
        query=[{"name": "q", "value": "a+b"}, {"name": "z", "value": "1"}],
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_check_order_unknown_kid_before_bad_mac(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Multi-fault: unknown kid wins over a clearly wrong MAC."""
    env = deepcopy(BASE_ENV)
    env["kid"] = "missing-key"
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    path = tmp_path / "ord-kid.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path)
    assert proc.returncode == 2
    assert proc.stderr == "error: unknown_kid\n"


def test_check_order_expired_before_bad_mac(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Multi-fault: well-formed but expired window wins over bad MAC."""
    env = deepcopy(BASE_ENV)
    env["created"] = 1700000000
    env["expires"] = 1700000050
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    path = tmp_path / "ord-exp.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path, now="1700000100")
    assert proc.returncode == 2
    assert proc.stderr == "error: expired\n"


def test_check_order_missing_header_before_bad_mac(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Multi-fault: missing covered header wins over bad MAC (time window ok)."""
    env = deepcopy(BASE_ENV)
    env["headers"] = {
        "Host": "api.example.test",
        "Content-Type": "application/json",
    }
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    path = tmp_path / "ord-hdr.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path)
    assert proc.returncode == 2
    assert proc.stderr == "error: missing_covered_header\n"


def test_check_order_bad_mac_before_replay(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Multi-fault: bad MAC is reported even when the identity is already in --seen."""
    env = deepcopy(BASE_ENV)
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    identity = f"{env['kid']}|{env['created']}|{env['mac']}"
    seen = tmp_path / "seen-ord.log"
    seen.write_text(identity + "\n", encoding="utf-8")
    path = tmp_path / "ord-mac.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path, seen=seen)
    assert proc.returncode == 2
    assert proc.stderr == "error: bad_mac\n"


def test_empty_covered_array(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Empty covered list still contributes an empty canonical-headers line."""
    path, env = mint(tmp_path, "cov0.json", keys, covered=[])
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_duplicate_covered_header_emitted_twice(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Duplicate covered names emit the header line twice in MAC order."""
    path, env = mint(
        tmp_path,
        "covdup.json",
        keys,
        covered=["host", "host", "content-type"],
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_query_equals_in_value_literal(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """'=' inside a value is literal; canonical form is name=value with embedded '='."""
    path, env = mint(
        tmp_path,
        "qeq.json",
        keys,
        query=[
            {"name": "a", "value": "b=c"},
            {"name": "x", "value": "1"},
        ],
    )
    assert "a=b=c" in canon_query(env["query"])
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_seen_crlf_line_not_replay(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Seen lines are compared as-is after split on LF; trailing CR does not match."""
    path, env = mint(tmp_path, "seen-crlf.json", keys)
    identity = f"{env['kid']}|{env['created']}|{env['mac']}"
    seen = tmp_path / "seen-crlf.log"
    seen.write_bytes((identity + "\r\n").encode("utf-8"))
    proc = run_verify(path, seen=seen)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)
    # Successful verify appends a clean LF-terminated identity.
    text = seen.read_text(encoding="utf-8")
    assert identity + "\n" in text.replace("\r\n", "\n") or text.endswith(identity + "\n")


def run_verify_argv(
    argv: list[str], *, auto: bool = True, work: Path | None = None
) -> subprocess.CompletedProcess[str]:
    argv = list(argv)
    if auto:
        work = work or _workdir()
        blob = " ".join(argv)
        if "--profile" not in blob:
            pr = work / "site.profile"
            if not pr.exists():
                write_profile(pr)
            argv.extend(["--profile", str(pr)])
        if "--seen" not in blob:
            sn = work / "seen-auto.log"
            if not sn.exists():
                sn.write_text("", encoding="utf-8")
            argv.extend(["--seen", str(sn)])
    return subprocess.run([str(BIN), *argv], capture_output=True, text=True)


def test_equals_form_flags_ok(keys: dict[str, bytes]) -> None:
    """`--flag=value` must work the same as space-separated flags."""
    env_path = ENVELOPES / "happy.json"
    env = load_envelope(env_path)
    proc = run_verify_argv(
        [
            "verify",
            f"--envelope={env_path}",
            f"--keyring={KEYRING}",
            f"--now={NOW}",
        ]
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_mixed_equals_and_space_flags_ok(keys: dict[str, bytes]) -> None:
    """Mixing equals-attached and space-separated forms must succeed."""
    env_path = ENVELOPES / "happy.json"
    env = load_envelope(env_path)
    proc = run_verify_argv(
        [
            "verify",
            "--envelope",
            str(env_path),
            f"--keyring={KEYRING}",
            "--now",
            NOW,
        ]
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_duplicate_mixed_equals_and_space_is_usage(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Duplicating a flag across space and equals forms is usage."""
    path, _env = mint(tmp_path, "dup-flag.json", keys)
    proc = run_verify_argv(
        [
            "verify",
            "--envelope",
            str(path),
            f"--envelope={path}",
            "--keyring",
            str(KEYRING),
            "--now",
            NOW,
        ]
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: usage\n"


def test_check_order_expired_before_missing_header(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Multi-fault: expired wins over missing covered header."""
    env = deepcopy(BASE_ENV)
    env["created"] = 1700000000
    env["expires"] = 1700000050
    env["headers"] = {
        "Host": "api.example.test",
        "Content-Type": "application/json",
    }
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    path = tmp_path / "ord-exp-hdr.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path, now="1700000100")
    assert proc.returncode == 2
    assert proc.stderr == "error: expired\n"


def test_check_order_invalid_window_before_bad_mac(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Multi-fault: expires < created wins over bad MAC."""
    env = deepcopy(BASE_ENV)
    env["created"] = 1700000100
    env["expires"] = 1700000000
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    path = tmp_path / "ord-inv.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path)
    assert proc.returncode == 2
    assert proc.stderr == "error: invalid_window\n"


def test_check_order_not_yet_before_missing_header(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Multi-fault: not_yet_valid wins over missing covered header."""
    env = deepcopy(BASE_ENV)
    env["created"] = 1700000200
    env["expires"] = 1700001000
    env["headers"] = {
        "Host": "api.example.test",
        "Content-Type": "application/json",
    }
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    path = tmp_path / "ord-nyv-hdr.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path, now="1700000100")
    assert proc.returncode == 2
    assert proc.stderr == "error: not_yet_valid\n"


def test_kid_lookup_is_case_sensitive(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Keyring kid match is exact; Main must not resolve to main."""
    env = deepcopy(BASE_ENV)
    env["kid"] = "Main"
    env["mac"] = expected_mac({**env, "kid": "main"}, keys)
    path = tmp_path / "kid-case.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path)
    assert proc.returncode == 2
    assert proc.stderr == "error: unknown_kid\n"


def test_header_nbsp_edges_not_ows(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """NBSP at value edges is not OWS; must remain in the canonical header line."""
    nbsp = "\u00a0"
    path, env = mint(
        tmp_path,
        "nbsp.json",
        keys,
        headers={
            "Host": "api.example.test",
            "Content-Type": "application/json",
            "Authorization": f"{nbsp}Bearer tok{nbsp}",
        },
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_query_utf8_name_bytewise_sort(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Non-ASCII query names sort by UTF-8 bytes (BMP order matches code points here)."""
    path, env = mint(
        tmp_path,
        "qutf.json",
        keys,
        query=[
            {"name": "ß", "value": "1"},
            {"name": "a", "value": "2"},
            {"name": "ä", "value": "3"},
        ],
    )
    # Byte/code-point order: a (0x61) < ß (U+00DF / c3 9f) < ä (U+00E4 / c3 a4)
    assert canon_query(env["query"]) == "a=2&ß=1&ä=3"
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_seen_htab_padded_line_not_replay(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Leading/trailing HTAB on a seen line does not match a clean identity."""
    path, env = mint(tmp_path, "seen-htab.json", keys)
    identity = f"{env['kid']}|{env['created']}|{env['mac']}"
    seen = tmp_path / "seen-htab.log"
    seen.write_text(f"\t{identity}\t\n", encoding="utf-8")
    proc = run_verify(path, seen=seen)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_all_equals_form_flags_ok(keys: dict[str, bytes], tmp_path: Path) -> None:
    """All five required flags may use equals form, including --profile and --seen."""
    env_path = ENVELOPES / "happy.json"
    env = load_envelope(env_path)
    seen = tmp_path / "seen-equals.log"
    seen.write_text("", encoding="utf-8")
    profile = write_profile(tmp_path / "site.profile")
    proc = run_verify_argv(
        [
            "verify",
            f"--envelope={env_path}",
            f"--keyring={KEYRING}",
            f"--now={NOW}",
            f"--profile={profile}",
            f"--seen={seen}",
        ],
        auto=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_empty_envelope_equals_is_usage() -> None:
    """`--envelope=` with an empty path is usage."""
    proc = run_verify_argv(
        [
            "verify",
            "--envelope=",
            f"--keyring={KEYRING}",
            f"--now={NOW}",
        ]
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: usage\n"


def test_invalid_now_equals_is_usage() -> None:
    """Non-integer --now= value is usage."""
    proc = run_verify_argv(
        [
            "verify",
            f"--envelope={ENVELOPES / 'happy.json'}",
            f"--keyring={KEYRING}",
            "--now=not-a-unix-time",
        ]
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: usage\n"


def test_relative_seen_path_is_usage(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """--seen must be absolute; relative paths are usage."""
    path, _env = mint(tmp_path, "rel-seen.json", keys)
    proc = run_verify_argv(
        [
            "verify",
            f"--envelope={path}",
            f"--keyring={KEYRING}",
            f"--now={NOW}",
            "--seen=seen/relative.log",
        ]
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: usage\n"


def test_keyring_invalid_bad_base64(tmp_path: Path) -> None:
    """Key material must decode as standard base64."""
    kr_path = tmp_path / "bad-kr.json"
    kr_path.write_text(
        json.dumps({"keys": {"main": "!!!not-valid-base64!!!"}}),
        encoding="utf-8",
    )
    env_path = ENVELOPES / "happy.json"
    proc = run_verify_argv(
        [
            "verify",
            f"--envelope={env_path}",
            f"--keyring={kr_path}",
            f"--now={NOW}",
        ]
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: keyring_invalid\n"


def test_seen_identity_substring_line_not_replay(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Seen membership is exact line equality; prefix/suffix padding does not match."""
    path, env = mint(tmp_path, "seen-sub.json", keys)
    identity = f"{env['kid']}|{env['created']}|{env['mac']}"
    seen = tmp_path / "seen-sub.log"
    seen.write_text(f"prefix-{identity}-suffix\n", encoding="utf-8")
    proc = run_verify(path, seen=seen)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_header_cr_edges_not_ows(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """CR at header value edges is not OWS and must remain in the canonical line."""
    cr = "\r"
    path, env = mint(
        tmp_path,
        "cr-hdr.json",
        keys,
        headers={
            "Host": "api.example.test",
            "Content-Type": "application/json",
            "Authorization": f"{cr}Bearer tok{cr}",
        },
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_duplicate_seen_flag_is_usage(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Duplicating --seen across space and equals forms is usage."""
    path, _env = mint(tmp_path, "dup-seen.json", keys)
    seen = tmp_path / "dup-seen.log"
    proc = run_verify_argv(
        [
            "verify",
            f"--envelope={path}",
            f"--keyring={KEYRING}",
            f"--now={NOW}",
            f"--seen={seen}",
            f"--seen={seen}",
        ]
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: usage\n"


def test_duplicate_now_space_form_is_usage() -> None:
    """Repeated space-form --now flags must not silently use the final value."""
    proc = run_verify_argv(
        [
            "verify",
            "--envelope",
            str(ENVELOPES / "happy.json"),
            "--keyring",
            str(KEYRING),
            "--now",
            NOW,
            "--now",
            NOW,
        ]
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: usage\n"


def test_duplicate_keyring_space_form_is_usage() -> None:
    """Repeated space-form --keyring flags must be rejected as usage."""
    proc = run_verify_argv(
        [
            "verify",
            "--envelope",
            str(ENVELOPES / "happy.json"),
            "--keyring",
            str(KEYRING),
            "--keyring",
            str(KEYRING),
            "--now",
            NOW,
        ]
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: usage\n"


def test_duplicate_envelope_space_form_is_usage() -> None:
    """Repeated space-form --envelope flags must be rejected as usage."""
    env_path = ENVELOPES / "happy.json"
    proc = run_verify_argv(
        [
            "verify",
            "--envelope",
            str(env_path),
            "--envelope",
            str(env_path),
            "--keyring",
            str(KEYRING),
            "--now",
            NOW,
        ]
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: usage\n"


def test_header_interior_lf_and_htab_preserved(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Interior LF and HTAB are MAC material, not whitespace to normalize."""
    path, env = mint(
        tmp_path,
        "header-lf.json",
        keys,
        headers={
            "Host": "api.example.test",
            "Content-Type": "application/json",
            "Authorization": "Bearer\n\t tok",
        },
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_header_vt_ff_edges_not_ows(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """VT and FF at value edges must remain in the canonical header line."""
    path, env = mint(
        tmp_path,
        "header-vt-ff.json",
        keys,
        headers={
            "Host": "api.example.test",
            "Content-Type": "application/json",
            "Authorization": "\vBearer tok\f",
        },
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_header_interior_em_space_and_nbsp_preserved(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Interior Unicode spaces are literal header value octets."""
    path, env = mint(
        tmp_path,
        "header-unicode-space.json",
        keys,
        headers={
            "Host": "api.example.test",
            "Content-Type": "application/json",
            "Authorization": "Bearer\u2003tok\u00a0end",
        },
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


# --- wave 7 ---


def test_bad_digest_before_bad_mac(tmp_path: Path) -> None:
    """Covered content-digest mismatch wins over a wrong MAC."""
    env = deepcopy(BASE_ENV)
    wrong = "sha-256=:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=:"
    assert wrong != content_digest(env["body"])
    env["headers"] = {
        "Host": "api.example.test",
        "Content-Type": "application/json",
        "Authorization": "Bearer tok",
        "Content-Digest": wrong,
    }
    env["covered"] = ["authorization", "content-type", "content-digest", "host"]
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    path = tmp_path / "bad-digest.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr == "error: bad_digest\n"


def test_now_signed_or_leading_zeros_is_usage() -> None:
    """--now must be digit-only without sign or leading zeros."""
    env_path = ENVELOPES / "happy.json"
    for bad in ("+1700000100", "01700000100", "-1"):
        proc = run_verify_argv(
            [
                "verify",
                f"--envelope={env_path}",
                f"--keyring={KEYRING}",
                f"--now={bad}",
            ]
        )
        assert proc.returncode == 2, bad
        assert proc.stderr == "error: usage\n", bad


def test_empty_keyring_now_seen_equals_is_usage() -> None:
    """Empty equals forms for --keyring, --now, and --seen are usage."""
    env_path = ENVELOPES / "happy.json"
    cases = [
        [
            "verify",
            f"--envelope={env_path}",
            "--keyring=",
            f"--now={NOW}",
        ],
        [
            "verify",
            f"--envelope={env_path}",
            f"--keyring={KEYRING}",
            "--now=",
        ],
        [
            "verify",
            f"--envelope={env_path}",
            f"--keyring={KEYRING}",
            f"--now={NOW}",
            "--seen=",
        ],
    ]
    for argv in cases:
        proc = run_verify_argv(argv)
        assert proc.returncode == 2, argv
        assert proc.stderr == "error: usage\n", argv


def test_relative_envelope_and_keyring_are_usage() -> None:
    """Relative --envelope and --keyring paths are usage."""
    env_path = ENVELOPES / "happy.json"
    proc = run_verify_argv(
        [
            "verify",
            "--envelope=fixtures/envelopes/happy.json",
            f"--keyring={KEYRING}",
            f"--now={NOW}",
        ]
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: usage\n"
    proc = run_verify_argv(
        [
            "verify",
            f"--envelope={env_path}",
            "--keyring=fixtures/keyring.json",
            f"--now={NOW}",
        ]
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: usage\n"


def test_check_order_unknown_kid_before_invalid_window(tmp_path: Path) -> None:
    """Multi-fault: unknown_kid wins over expires < created."""
    env = deepcopy(BASE_ENV)
    env["kid"] = "missing-key"
    env["created"] = 1700000100
    env["expires"] = 1700000000
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    path = tmp_path / "ord-kid-win.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path)
    assert proc.returncode == 2
    assert proc.stderr == "error: unknown_kid\n"


def test_check_order_invalid_window_before_missing_header(tmp_path: Path) -> None:
    """Multi-fault: invalid_window wins over missing covered header."""
    env = deepcopy(BASE_ENV)
    env["created"] = 1700000100
    env["expires"] = 1700000000
    env["headers"] = {
        "Host": "api.example.test",
        "Content-Type": "application/json",
    }
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    path = tmp_path / "ord-inv-hdr.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path)
    assert proc.returncode == 2
    assert proc.stderr == "error: invalid_window\n"


def test_keyring_urlsafe_base64_is_invalid(tmp_path: Path) -> None:
    """URL-safe (-_) key material is keyring_invalid; only standard base64 is accepted."""
    material = b"\xff" * 32
    url_b64 = base64.urlsafe_b64encode(material).decode("ascii")
    std_b64 = base64.b64encode(material).decode("ascii")
    assert url_b64 != std_b64
    assert "-" in url_b64 or "_" in url_b64
    kr_path = tmp_path / "url-kr.json"
    kr_path.write_text(json.dumps({"keys": {"main": url_b64}}), encoding="utf-8")
    proc = run_verify_argv(
        [
            "verify",
            f"--envelope={ENVELOPES / 'happy.json'}",
            f"--keyring={kr_path}",
            f"--now={NOW}",
        ]
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: keyring_invalid\n"


def test_header_interior_cr_preserved(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Interior CR in a header value is kept as MAC material (not OWS)."""
    path, env = mint(
        tmp_path,
        "header-cr-int.json",
        keys,
        headers={
            "Host": "api.example.test",
            "Content-Type": "application/json",
            "Authorization": "Bearer\rtok",
        },
    )
    proc = run_verify(path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_flag_order_shuffle_ok(keys: dict[str, bytes]) -> None:
    """Flag order does not matter for a well-formed verify."""
    env_path = ENVELOPES / "happy.json"
    env = load_envelope(env_path)
    proc = run_verify_argv(
        [
            "verify",
            "--now",
            NOW,
            "--keyring",
            str(KEYRING),
            "--envelope",
            str(env_path),
        ]
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


# --- wave 8 ---


def test_envelope_path_is_directory_invalid(tmp_path: Path) -> None:
    """A directory passed as --envelope is a non-blocking envelope_invalid, not usage."""
    proc = run_verify_argv(
        ["verify", "--envelope", str(tmp_path), "--keyring", str(KEYRING), "--now", NOW]
    )
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr == "error: envelope_invalid\n"


def test_keyring_path_is_directory_invalid(tmp_path: Path) -> None:
    """A directory passed as --keyring is a non-blocking keyring_invalid, not usage."""
    env_path = ENVELOPES / "happy.json"
    proc = run_verify_argv(
        ["verify", "--envelope", str(env_path), "--keyring", str(tmp_path), "--now", NOW]
    )
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr == "error: keyring_invalid\n"


def test_symlink_envelope_succeeds(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """A symlink whose target is a valid envelope file must verify, not be rejected."""
    env_path = ENVELOPES / "happy.json"
    env = load_envelope(env_path)
    link = tmp_path / "happy-link.json"
    link.symlink_to(env_path)
    proc = run_verify_argv(
        ["verify", "--envelope", str(link), "--keyring", str(KEYRING), "--now", NOW]
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_symlink_keyring_succeeds(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """A symlink whose target is a valid keyring file must verify, not be rejected."""
    env_path = ENVELOPES / "happy.json"
    env = load_envelope(env_path)
    link = tmp_path / "keyring-link.json"
    link.symlink_to(KEYRING)
    proc = run_verify_argv(
        ["verify", "--envelope", str(env_path), "--keyring", str(link), "--now", NOW]
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys)


def test_envelope_utf8_bom_invalid(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """A UTF-8 BOM before an otherwise-valid envelope JSON body is envelope_invalid."""
    env = deepcopy(BASE_ENV)
    env["mac"] = expected_mac(env, keys)
    path = tmp_path / "bom.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(env).encode("utf-8"))
    proc = run_verify(path)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr == "error: envelope_invalid\n"


def test_created_expires_float_invalid(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """created/expires rendered as JSON floats are envelope_invalid, not truncated ints."""
    for field in ("created", "expires"):
        env = deepcopy(BASE_ENV)
        env[field] = float(env[field])
        env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        path = tmp_path / f"float-{field}.json"
        path.write_text(json.dumps(env), encoding="utf-8")
        proc = run_verify(path)
        assert proc.returncode == 2, field
        assert proc.stdout == "", field
        assert proc.stderr == "error: envelope_invalid\n", field


def test_check_order_keyring_invalid_before_unknown_kid(tmp_path: Path) -> None:
    """Multi-fault: an unparseable keyring wins over an unknown kid in the envelope."""
    env = deepcopy(BASE_ENV)
    env["kid"] = "no-such-key"
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    env_path = tmp_path / "ord-kr-kid.json"
    env_path.write_text(json.dumps(env), encoding="utf-8")
    kr_path = tmp_path / "malformed-kr.json"
    kr_path.write_text("not valid json", encoding="utf-8")
    proc = run_verify_argv(
        ["verify", "--envelope", str(env_path), "--keyring", str(kr_path), "--now", NOW]
    )
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr == "error: keyring_invalid\n"

# --- Wave 9: CLI trailing/dangling + keyring/envelope shape ---


def test_trailing_positional_arg_is_usage(keys: dict[str, bytes]) -> None:
    """A bare positional after a complete verify invoke is usage."""
    env_path = ENVELOPES / "happy.json"
    proc = run_verify_argv(
        [
            "verify",
            "--envelope",
            str(env_path),
            "--keyring",
            str(KEYRING),
            "--now",
            NOW,
            "extra",
        ]
    )
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr == "error: usage\n"


def test_dangling_seen_flag_is_usage(keys: dict[str, bytes], tmp_path: Path) -> None:
    """Space-form --seen with no following path token is usage."""
    env_path = ENVELOPES / "happy.json"
    profile = write_profile(tmp_path / "site.profile")
    proc = run_verify_argv(
        [
            "verify",
            "--envelope",
            str(env_path),
            "--keyring",
            str(KEYRING),
            "--now",
            NOW,
            "--profile",
            str(profile),
            "--seen",
        ],
        auto=False,
    )
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr == "error: usage\n"


def test_seen_directory_path_is_io(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """--seen pointed at a directory must be io, not hang or usage."""
    env_path = ENVELOPES / "happy.json"
    env = load_envelope(env_path)
    seen_dir = tmp_path / "seen-dir"
    seen_dir.mkdir()
    proc = run_verify_argv(
        [
            "verify",
            "--envelope",
            str(env_path),
            "--keyring",
            str(KEYRING),
            "--now",
            NOW,
            "--seen",
            str(seen_dir),
        ]
    )
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr == "error: io\n"
    ok = run_verify(env_path)
    assert ok.returncode == 0
    assert ok.stdout == expected_ok_line(env, keys)


def test_keyring_keys_null_is_keyring_invalid(tmp_path: Path) -> None:
    """JSON null for the keys object is keyring_invalid."""
    env_path = ENVELOPES / "happy.json"
    kr = tmp_path / "keys-null.json"
    kr.write_text('{"keys": null}', encoding="utf-8")
    proc = run_verify_argv(
        ["verify", "--envelope", str(env_path), "--keyring", str(kr), "--now", NOW]
    )
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr == "error: keyring_invalid\n"


def test_envelope_trailing_junk_is_envelope_invalid(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Valid envelope JSON followed by trailing junk is envelope_invalid."""
    env = deepcopy(BASE_ENV)
    env["mac"] = expected_mac(env, keys)
    path = tmp_path / "junk-tail.json"
    path.write_text(json.dumps(env) + "\nTRAILING", encoding="utf-8")
    proc = run_verify(path)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr == "error: envelope_invalid\n"


def test_missing_profile_flag_is_usage(keys: dict[str, bytes], tmp_path: Path) -> None:
    """Omitting required --profile is usage."""
    seen = tmp_path / "seen.log"
    seen.write_text("", encoding="utf-8")
    proc = run_verify_argv(
        [
            "verify",
            "--envelope",
            str(ENVELOPES / "happy.json"),
            "--keyring",
            str(KEYRING),
            "--now",
            NOW,
            "--seen",
            str(seen),
        ],
        auto=False,
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: usage\n"


def test_missing_seen_flag_is_usage(keys: dict[str, bytes], tmp_path: Path) -> None:
    """Omitting required --seen is usage."""
    profile = write_profile(tmp_path / "site.profile")
    proc = run_verify_argv(
        [
            "verify",
            "--envelope",
            str(ENVELOPES / "happy.json"),
            "--keyring",
            str(KEYRING),
            "--now",
            NOW,
            "--profile",
            str(profile),
        ],
        auto=False,
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: usage\n"


def test_relative_profile_path_is_usage(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """--profile must be absolute; relative paths are usage."""
    path, _env = mint(tmp_path, "rel-prof.json", keys)
    seen = tmp_path / "seen.log"
    seen.write_text("", encoding="utf-8")
    proc = run_verify_argv(
        [
            "verify",
            f"--envelope={path}",
            f"--keyring={KEYRING}",
            f"--now={NOW}",
            "--profile=data/site.profile",
            f"--seen={seen}",
        ],
        auto=False,
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: usage\n"


def test_bad_profile_magic_is_profile_invalid(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Readable profile with wrong magic is profile_invalid."""
    path, _env = mint(tmp_path, "bad-prof.json", keys)
    bad = tmp_path / "bad.profile"
    bad.write_bytes(b"XXXX" + b"\x00" * 13)
    seen = tmp_path / "seen.log"
    seen.write_text("", encoding="utf-8")
    proc = run_verify(path, seen=seen, profile=bad, tmp_path=tmp_path)
    assert proc.returncode == 2
    assert proc.stderr == "error: profile_invalid\n"


def test_missing_profile_file_is_io(tmp_path: Path, keys: dict[str, bytes]) -> None:
    """Absolute --profile path that does not exist is io."""
    path, _env = mint(tmp_path, "miss-prof.json", keys)
    missing = tmp_path / "no-such.profile"
    seen = tmp_path / "seen.log"
    seen.write_text("", encoding="utf-8")
    proc = run_verify_argv(
        [
            "verify",
            "--envelope",
            str(path),
            "--keyring",
            str(KEYRING),
            "--now",
            NOW,
            "--profile",
            str(missing),
            "--seen",
            str(seen),
        ],
        auto=False,
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: io\n"


def test_profile_reorders_bad_mac_before_bad_digest(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Site profile order — not RFC-ish defaults — selects the first active fault."""
    body = '{"order_id":"o-1","amount":10}'
    cd = content_digest(body, DIGEST_COLON_STD)
    env = deepcopy(BASE_ENV)
    env["body"] = body
    env["covered"] = ["host", "content-digest"]
    env["headers"] = {
        "Host": "api.example.test",
        "content-digest": "sha-256=:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=:",
    }
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    assert env["headers"]["content-digest"] != cd
    path = tmp_path / "ord-mac-digest.json"
    path.write_text(json.dumps(env), encoding="utf-8")
    def_dir = tmp_path / "def"
    def_dir.mkdir()
    # Default sample order: bad_digest (4) before bad_mac (5).
    default = run_verify(
        path,
        profile_bytes=encode_profile(order=[1, 2, 3, 4, 5, 6]),
        tmp_path=def_dir,
    )
    assert default.returncode == 2
    assert default.stderr == "error: bad_digest\n"
    # Reordered profile: bad_mac before bad_digest.
    reord_dir = tmp_path / "reord"
    reord_dir.mkdir()
    reordered = run_verify(
        path,
        profile_bytes=encode_profile(order=[1, 2, 3, 5, 4, 6]),
        tmp_path=reord_dir,
    )
    assert reordered.returncode == 2
    assert reordered.stderr == "error: bad_mac\n"


def test_profile_ows_sp_only_keeps_htab_edges(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """RFC 9110 OWS is SP|HTAB; site ows_mask=1 leaves HTAB edges in the MAC."""
    ows = OWS_SP  # SP only — not RFC default
    path, env = mint(
        tmp_path,
        "ows-sp-only.json",
        keys,
        ows_mask=ows,
        headers={
            "Host": "api.example.test",
            "Content-Type": "application/json",
            "Authorization": "\tBearer tok\t",
        },
    )
    proc = run_verify(
        path,
        profile_bytes=encode_profile(ows_mask=ows),
        tmp_path=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys, ows_mask=ows)
    # Hard-coded RFC SP|HTAB trim yields a different MAC → bad_mac under this profile.
    rfc_mac = expected_mac(env, keys, ows_mask=OWS_SP | OWS_HTAB)
    assert rfc_mac != env["mac"]


def test_profile_ows_nbsp_trim_diverges_from_rfc(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """ows_mask including NBSP trims U+00A0 edges; RFC OWS agents leave them."""
    ows = OWS_SP | OWS_HTAB | OWS_NBSP
    path, env = mint(
        tmp_path,
        "ows-nbsp.json",
        keys,
        ows_mask=ows,
        headers={
            "Host": "api.example.test",
            "Content-Type": "application/json",
            "Authorization": "\u00a0Bearer tok\u00a0",
        },
    )
    proc = run_verify(
        path,
        profile_bytes=encode_profile(ows_mask=ows),
        tmp_path=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys, ows_mask=ows)
    rfc_mac = expected_mac(env, keys, ows_mask=OWS_SP | OWS_HTAB)
    assert rfc_mac != env["mac"]


def test_profile_digest_bare_std_framing(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """digest_mode=1 drops surrounding colons — not the RFC 9530 colon form."""
    mode = DIGEST_BARE_STD
    path, env = mint(
        tmp_path,
        "digest-bare.json",
        keys,
        digest_mode=mode,
    )
    proc = run_verify(
        path,
        profile_bytes=encode_profile(digest_mode=mode),
        tmp_path=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == expected_ok_line(env, keys, digest_mode=mode)
    assert "sha-256=:" not in proc.stdout
    assert "sha-256=" in proc.stdout
    colon_mac = expected_mac(env, keys, digest_mode=DIGEST_COLON_STD)
    assert colon_mac != env["mac"]


def test_profile_bound_mac_rejects_bare_cr_hmac(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """RFC-style HMAC(key, CR) without binding the profile bytes is bad_mac."""
    import hashlib
    import hmac as hm

    from hrm_reference import canonical_request

    path, env = mint(tmp_path, "bound.json", keys)
    cr, _ = canonical_request(env)
    bare = base64.urlsafe_b64encode(
        hm.new(keys[env["kid"]], cr.encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    assert bare != env["mac"]
    env["mac"] = bare
    path.write_text(json.dumps(env), encoding="utf-8")
    proc = run_verify(path, tmp_path=tmp_path)
    assert proc.returncode == 2
    assert proc.stderr == "error: bad_mac\n"


def test_different_profiles_yield_different_macs(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Same CR under two profiles must mint distinct profile-bound MACs."""
    a = encode_profile(ows_mask=OWS_SP | OWS_HTAB)
    b = encode_profile(ows_mask=OWS_SP)
    path_a, env_a = mint(tmp_path, "pa.json", keys, profile_bytes=a, ows_mask=OWS_SP | OWS_HTAB)
    path_b, env_b = mint(
        tmp_path,
        "pb.json",
        keys,
        profile_bytes=b,
        ows_mask=OWS_SP,
        headers=env_a["headers"],
    )
    assert env_a["mac"] != env_b["mac"]
    assert run_verify(path_a, profile_bytes=a, tmp_path=tmp_path / "wa").returncode == 0
    assert run_verify(path_b, profile_bytes=b, tmp_path=tmp_path / "wb").returncode == 0


def test_durable_seen_sequence_across_invocations(
    tmp_path: Path, keys: dict[str, bytes]
) -> None:
    """Shared --seen ledger: admit once, then replay on later invocations."""
    path, env = mint(tmp_path, "seq.json", keys)
    seen = tmp_path / "durable.seen"
    profile = write_profile(tmp_path / "site.profile")
    first = run_verify(path, seen=seen, profile=profile, tmp_path=tmp_path)
    assert first.returncode == 0, first.stderr
    assert first.stdout == expected_ok_line(env, keys)
    second = run_verify(path, seen=seen, profile=profile, tmp_path=tmp_path)
    assert second.returncode == 2
    assert second.stderr == "error: replay\n"
    third = run_verify(path, seen=seen, profile=profile, tmp_path=tmp_path)
    assert third.returncode == 2
    assert third.stderr == "error: replay\n"
    identity = f"{env['kid']}|{env['created']}|{env['mac']}"
    assert seen.read_text(encoding="utf-8").splitlines().count(identity) == 1


def test_empty_profile_equals_is_usage() -> None:
    """`--profile=` with an empty path is usage."""
    proc = run_verify_argv(
        [
            "verify",
            f"--envelope={ENVELOPES / 'happy.json'}",
            f"--keyring={KEYRING}",
            f"--now={NOW}",
            "--profile=",
        ]
    )
    assert proc.returncode == 2
    assert proc.stderr == "error: usage\n"
