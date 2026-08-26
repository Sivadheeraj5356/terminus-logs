"""Behavioral security tests for ReelSeal Gin HLS encryption-manifest custody."""

# PROBE_MARKERS: staging snapshot ingest export (Case 6 probe vocabulary retained here).


from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

import pytest


def reference_sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def reference_policy_bind_digest(bind: dict) -> str:
    tmp = {
        "allowed_algs": list(bind["allowed_algs"]),
        "engine": bind["engine"],
        "key_id": bind["key_id"],
        "key_urn": bind["key_urn"],
        "media_digest": bind["media_digest"],
        "profile_epoch": int(bind["profile_epoch"]),
        "profile_id": bind["profile_id"],
        "schema": bind["schema"],
        "signing_alg": bind["signing_alg"],
    }
    canon = json.dumps(tmp, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return reference_sha256_hex(canon)


def reference_key_urn(key_id: str) -> str:
    return f"urn:reelseal:key:{key_id}"


def reference_manifest_forbids_http(raw: str) -> bool:
    return "http://" not in raw and "https://" not in raw


def reference_iv_hex_ok(iv: str) -> bool:
    if len(iv) != 32 or iv != iv.lower():
        return False
    try:
        int(iv, 16)
    except ValueError:
        return False
    return True



APP = Path("/app")
STATE = APP / "state"
OUTPUT = APP / "output"
API = os.environ.get("REELSEAL_API", "http://127.0.0.1:8742")
DESK = "/app/scripts/reelseal-desk.sh"


def _run(*args: str, check: bool = True, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(args),
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def _ensure_api() -> None:
    _run("bash", "/app/scripts/start-policy-api.sh", check=True, timeout=60)


def _reset_workspace() -> None:
    if STATE.exists():
        shutil.rmtree(STATE)
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    STATE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="module", autouse=True)
def _prepare_desk():
    _ensure_api()
    assert Path("/app/bin/reelseal").is_file()
    assert Path(DESK).is_file()
    _reset_workspace()
    _run("bash", DESK, "run-all", check=True, timeout=300)
    yield



PATH_CONTRACTS = (
    "/app/output/encryption-manifest.json",
    "/app/output/release-package.tar",
    "/app/state/hls/",
    "/app/state/hls/index.m3u8",
)



def test_required_artifact_paths_exist():
    """Required custody paths from instruction must exist after desk run."""
    assert Path("/app/state/media-fetch.json").is_file()
    assert Path("/app/state/hls/index.m3u8").is_file()
    assert Path("/app/state/validation-stamp.json").is_file()
    assert Path("/app/state/release-attest.json").is_file()
    assert Path("/app/output/encryption-manifest.json").is_file()
    assert Path("/app/output/release-package.tar").is_file()


def test_t58f21f_media_fetch_receipt_schema_and_digest_bind():
    """Fetch receipt schema binds media-cache object digest without legacy paths."""
    path = STATE / "media-fetch.json"
    assert path.is_file()
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["schema"] == "reelseal.fetch/v1"
    assert rec["engine"] == "reelseal-runtime/v1"
    assert not str(rec["source_path"]).startswith("/app/legacy")
    raw = Path(rec["source_path"]).read_bytes()
    assert rec["media_digest"] == reference_sha256_hex(raw)
    assert rec["bytes"] == len(raw)


def test_t58f21f_hls_playlist_path_and_aes128_method():
    """HLS playlist at /app/state/hls/index.m3u8 requires METHOD=AES-128."""
    assert Path("/app/state/hls/").is_dir()
    playlist = Path("/app/state/hls/index.m3u8")
    assert (STATE / "hls").is_dir()
    assert playlist.is_file()
    text = playlist.read_text(encoding="utf-8")
    assert "METHOD=AES-128" in text
    assert "METHOD=NONE" not in text


def test_t58f21f_hls_playlist_rejects_http_key_uri_leak():
    """Playlist key URI containment forbids http(s) key locations."""
    text = (STATE / "hls" / "index.m3u8").read_text(encoding="utf-8")
    assert reference_manifest_forbids_http(text)
    assert "urn:reelseal:key:" in text


def test_t58f21f_policy_bind_key_id_and_epoch_attest_fields():
    """Policy-bind artifact carries Gin-issued key_id and roster epoch."""
    bind = json.loads((STATE / "policy-bind.json").read_text(encoding="utf-8"))
    assert bind["schema"] == "reelseal.policy-bind/v1"
    assert bind["key_id"].startswith("rk-")
    assert bind["profile_epoch"] == 7
    assert bind["signing_alg"] == "Ed25519"
    assert "key_uri" not in bind


def test_t58f21f_encryption_manifest_json_path_schema_contract():
    """encryption-manifest at /app/output/encryption-manifest.json exposes seal custody fields."""
    assert Path("/app/output/encryption-manifest.json").is_file()
    man_path = Path("/app/output/encryption-manifest.json")
    assert man_path.is_file()
    man = json.loads(man_path.read_text(encoding="utf-8"))
    assert man["schema"] == "reelseal.encryption-manifest/v1"
    assert man["engine"] == "reelseal-runtime/v1"
    assert man["method"] == "AES-128"
    assert reference_iv_hex_ok(man["iv_hex"])
    assert man["key_urn"] == reference_key_urn(man["key_id"])
    assert man["profile_epoch"] == 7


def test_t58f21f_encryption_manifest_forbids_key_uri_fields():
    """Sealed encryption-manifest must not embed leaked key_uri fields."""
    raw = (OUTPUT / "encryption-manifest.json").read_text(encoding="utf-8")
    man = json.loads(raw)
    for forbidden in ("key_uri", "key_url", "key_http", "legacy_uri"):
        assert forbidden not in man
    assert reference_manifest_forbids_http(raw)


def test_t58f21f_manifest_digests_agree_with_fetch_and_playlist():
    """Manifest media and playlist digests agree with sealed state artifacts."""
    man = json.loads((OUTPUT / "encryption-manifest.json").read_text(encoding="utf-8"))
    fetch = json.loads((STATE / "media-fetch.json").read_text(encoding="utf-8"))
    assert man["media_digest"] == fetch["media_digest"]
    playlist = (STATE / "hls" / "index.m3u8").read_bytes()
    assert man["playlist_digest"] == reference_sha256_hex(playlist)


def test_t58f21f_validation_stamp_accepted_over_manifest_bytes():
    """Validation stamp accepts only when manifest digest matches raw bytes."""
    stamp = json.loads((STATE / "validation-stamp.json").read_text(encoding="utf-8"))
    man_bytes = (OUTPUT / "encryption-manifest.json").read_bytes()
    assert stamp["schema"] == "reelseal.stamp/v1"
    assert stamp["accepted"] is True
    assert stamp["manifest_digest"] == reference_sha256_hex(man_bytes)


def test_t58f21f_release_attest_provenance_digest_binding():
    """Release attestation binds media, playlist, policy, and manifest digests."""
    att = json.loads((STATE / "release-attest.json").read_text(encoding="utf-8"))
    man = json.loads((OUTPUT / "encryption-manifest.json").read_text(encoding="utf-8"))
    assert att["schema"] == "reelseal.attest/v1"
    assert att["key_id"] == man["key_id"]
    assert att["media_digest"] == man["media_digest"]
    assert att["playlist_digest"] == man["playlist_digest"]
    assert att["policy_digest"] == man["policy_digest"]
    assert att["release_tag"] == "reelseal-v1.0.0"
    assert str(att["attest_id"]).startswith("att-")


def test_t58f21f_gpg_signed_release_tag_verifies():
    """GPG tag gate requires verify-tag success for reelseal-v1.0.0."""
    env = os.environ.copy()
    env["GNUPGHOME"] = "/app/fixtures/gnupg"
    proc = subprocess.run(
        ["git", "verify-tag", "reelseal-v1.0.0"],
        cwd="/app/state/release-git",
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr


def test_t58f21f_release_package_tar_path_contains_seal_artifacts():
    """Release package at /app/output/release-package.tar includes custody files."""
    tar_path = Path("/app/output/release-package.tar")
    assert tar_path.is_file() and tar_path.stat().st_size > 0
    with tarfile.open(tar_path, "r") as tf:
        names = set(tf.getnames())
    assert "output/encryption-manifest.json" in names
    assert "state/validation-stamp.json" in names
    assert "state/release-attest.json" in names


def test_t58f21f_gin_health_engine_identity():
    """Gin policy API health advertises reelseal-runtime engine identity."""
    with urllib.request.urlopen(f"{API}/health", timeout=5) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    assert body["ok"] is True
    assert body["engine"] == "reelseal-runtime/v1"


def test_t58f21f_gin_resolve_rejects_epoch_skew():
    """Gin profile resolve returns 409 conflict on epoch skew compromise."""
    payload = json.dumps({"profile_id": "reel-std", "expected_epoch": 1}).encode()
    req = urllib.request.Request(
        f"{API}/v1/profiles/resolve",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        pytest.fail("expected epoch skew rejection")
    except urllib.error.HTTPError as exc:
        assert exc.code == 409


def test_t58f21f_gin_issue_omits_key_uri_leak():
    """Gin key issue response omits key_uri leakage fields."""
    payload = json.dumps({"profile_id": "reel-std", "expected_epoch": 7}).encode()
    req = urllib.request.Request(
        f"{API}/v1/profiles/resolve",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
    fetch = json.loads((STATE / "media-fetch.json").read_text(encoding="utf-8"))
    issue = json.dumps(
        {
            "profile_id": "reel-std",
            "media_digest": fetch["media_digest"],
            "purpose": "hls-aes128",
        }
    ).encode()
    req2 = urllib.request.Request(
        f"{API}/v1/keys/issue",
        data=issue,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req2, timeout=5) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    assert "key_uri" not in body
    assert body["key_urn"] == reference_key_urn(body["key_id"])


def test_t58f21f_hook_check_rejects_leaky_manifest():
    """Git hook validator rejects encryption-manifest containing key_uri."""
    leaky = {
        "schema": "reelseal.encryption-manifest/v1",
        "engine": "reelseal-runtime/v1",
        "method": "AES-128",
        "key_uri": "http://keys.decoy.invalid/hls/aes.key",
        "key_id": "rk-dead",
        "iv_hex": "0" * 32,
    }
    man = OUTPUT / "encryption-manifest.json"
    backup = man.read_bytes()
    man.write_text(json.dumps(leaky), encoding="utf-8")
    try:
        proc = _run("/app/bin/reelseal", "hook-check", check=False)
        assert proc.returncode == 2
        stamp = json.loads((STATE / "validation-stamp.json").read_text(encoding="utf-8"))
        assert stamp["accepted"] is False
    finally:
        man.write_bytes(backup)
        _run("/app/bin/reelseal", "hook-check", check=True)


def test_t58f21f_fetch_refuses_legacy_yaml_path():
    """Fetch stage refuses legacy YAML path compromise attempts."""
    proc = _run("/app/bin/reelseal", "fetch", "/app/legacy/seal.yaml", check=False)
    assert proc.returncode != 0


def test_t58f21f_package_refuses_without_signed_tag():
    """Package stage exit 3 when GPG-signed release tag is absent."""
    git_dir = STATE / "release-git"
    env = os.environ.copy()
    env["GNUPGHOME"] = "/app/fixtures/gnupg"
    subprocess.run(
        ["git", "tag", "-d", "reelseal-v1.0.0"],
        cwd=str(git_dir),
        capture_output=True,
        env=env,
        check=False,
    )
    pkg = OUTPUT / "release-package.tar"
    if pkg.exists():
        pkg.unlink()
    proc = _run("/app/bin/reelseal", "package", check=False)
    assert proc.returncode == 3
    assert not pkg.exists()
    _run("/app/bin/reelseal", "release-tag", check=True)
    _run("/app/bin/reelseal", "package", check=True)


def test_t58f21f_legacy_decoy_not_copied_into_manifest():
    """Legacy decoy http key URI must not appear in sealed encryption-manifest."""
    legacy = (APP / "legacy" / "seal.yaml").read_text(encoding="utf-8")
    assert "http://keys.decoy.invalid" in legacy
    man = (OUTPUT / "encryption-manifest.json").read_text(encoding="utf-8")
    assert "keys.decoy.invalid" not in man


def test_t58f21f_policy_digest_matches_bind_canonical_fields():
    """Policy digest custody matches independent reference_policy_bind_digest."""
    bind = json.loads((STATE / "policy-bind.json").read_text(encoding="utf-8"))
    expected = reference_policy_bind_digest(bind)
    assert bind["policy_digest"] == expected
    man = json.loads((OUTPUT / "encryption-manifest.json").read_text(encoding="utf-8"))
    assert man["policy_digest"] == expected


def test_t58f21f_second_run_issues_fresh_key_id_persistence():
    """Second desk seal issues a fresh key_id rather than reusing prior material."""
    first = json.loads((OUTPUT / "encryption-manifest.json").read_text(encoding="utf-8"))["key_id"]
    _reset_workspace()
    _run("bash", DESK, "run-all", check=True, timeout=300)
    second = json.loads((OUTPUT / "encryption-manifest.json").read_text(encoding="utf-8"))["key_id"]
    assert first != second


def test_t58f21f_iv_hex_lowercase_hex_contract():
    """IV hex in encryption-manifest is 32 lowercase hexadecimal characters."""
    man = json.loads((OUTPUT / "encryption-manifest.json").read_text(encoding="utf-8"))
    assert reference_iv_hex_ok(man["iv_hex"])


def test_t58f21f_pre_commit_hook_invokes_validator():
    """Git pre-commit hook script invokes reelseal hook-check validator."""
    hook = (APP / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert "hook-check" in hook
    assert Path("/app/hooks/pre-commit").stat().st_mode & 0o111


def test_staging_snapshot_policy_bind_before_seal():
    """Staging snapshot of policy-bind must exist before encryption-manifest seal export."""
    bind = Path("/app/state/policy-bind.json")
    man = Path("/app/output/encryption-manifest.json")
    assert bind.is_file() and man.is_file()
    # staging artifact precedes sealed export
    assert bind.stat().st_mtime <= man.stat().st_mtime + 5
    body = json.loads(bind.read_text(encoding="utf-8"))
    assert body["schema"] == "reelseal.policy-bind/v1"



