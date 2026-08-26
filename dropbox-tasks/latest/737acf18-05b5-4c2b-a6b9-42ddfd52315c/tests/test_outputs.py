"""Verifier for cargo-sparse-index-mirror-skew.

Test inventory: 10 tests. Graded path is real `cargo build --offline --locked`
against a filesystem local-registry mirror (not a custom JSON emitter).
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
MIRROR = APP / "mirror"
STALE = APP / "data" / "mirror-stale"
CONFIG = APP / ".cargo" / "config.toml"
LOCK = APP / "Cargo.lock"
REMOTE_NEEDLE = 'local-registry = "/app/mirror"'


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(APP),
        text=True,
        capture_output=True,
        check=False,
        **kwargs,
    )


def _offline_build() -> subprocess.CompletedProcess[str]:
    return _run(["cargo", "build", "--offline", "--locked"])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _lock_checksums() -> dict[str, str]:
    text = LOCK.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    name = ck = ""
    for line in text.splitlines():
        line = line.strip()
        if line == "[[package]]":
            if name and ck:
                out[name] = ck
            name = ck = ""
            continue
        if line.startswith("name = "):
            name = line.split("=", 1)[1].strip().strip('"')
        if line.startswith("checksum = "):
            ck = line.split("=", 1)[1].strip().strip('"')
    if name and ck:
        out[name] = ck
    return out


def _required_ids() -> list[str]:
    return [x.strip() for x in (APP / "docs" / "tgt_notes.txt").read_text().split(",") if x.strip()]


def _crate_path(name: str, version: str) -> Path:
    return MIRROR / f"{name}-{version}.crate"


def _versions_from_lock() -> dict[str, str]:
    text = LOCK.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    name = ver = ""
    for line in text.splitlines():
        line = line.strip()
        if line == "[[package]]":
            if name and ver and name != "h9_fixture":
                out[name] = ver
            name = ver = ""
            continue
        if line.startswith("name = "):
            name = line.split("=", 1)[1].strip().strip('"')
        if line.startswith("version = "):
            ver = line.split("=", 1)[1].strip().strip('"')
    if name and ver and name != "h9_fixture":
        out[name] = ver
    return out


@pytest.fixture(scope="module", autouse=True)
def _clean_target():
    # Ensure each module starts without a leftover successful build tree.
    _run(["rm", "-rf", "target"])
    yield


def test_u1_offline_build():
    """Documented offline locked build must succeed via Cargo."""
    result = _offline_build()
    assert result.returncode == 0, result.stderr + "\n" + result.stdout


def test_u2_config_active_mirror():
    """Source replacement must point local-registry at /app/mirror."""
    text = CONFIG.read_text(encoding="utf-8")
    assert REMOTE_NEEDLE in text
    assert "/app/data/mirror-stale" not in text.replace(" ", "")


def test_u3_lock_matches_crates():
    """Cargo.lock checksums must equal sha256 of active mirror .crate files."""
    locks = _lock_checksums()
    versions = _versions_from_lock()
    for rid in _required_ids():
        assert rid in locks
        crate = _crate_path(rid, versions[rid])
        assert crate.is_file(), f"missing {crate}"
        assert locks[rid] == _sha256(crate)


def test_u4_idempotent_rebuild():
    """A second offline locked build still succeeds."""
    first = _offline_build()
    assert first.returncode == 0, first.stderr
    second = _offline_build()
    assert second.returncode == 0, second.stderr


def test_u5_hyphen_index_path():
    """Hyphenated crate index path uses crates.io layout under the active mirror."""
    idx = MIRROR / "index" / "cf" / "g-" / "cfg-if"
    assert idx.is_file(), f"expected index at {idx}"
    wrong = MIRROR / "index" / "cf" / "gi" / "cfg-if"
    assert not wrong.exists()


def test_u6_stale_not_selected():
    """Active config must not select the discarded mirror-stale snapshot."""
    text = CONFIG.read_text(encoding="utf-8")
    assert "mirror-stale" not in text
    # Stale tree may still exist on disk as a trap; cargo must not use it.
    assert STALE.is_dir()


def test_u7_required_packages_compile():
    """Primary package ids from tgt_notes.txt are in the lock and built offline."""
    result = _offline_build()
    assert result.returncode == 0, result.stderr
    locks = _lock_checksums()
    for rid in _required_ids():
        assert rid in locks
    # Workspace package artifact present after a successful build.
    arts = list((APP / "target").rglob("libh9_fixture*.rlib"))
    assert arts, "expected h9_fixture rlib under target/"


def test_u8_metadata_offline():
    """cargo metadata --offline --locked resolves against the repaired registry."""
    result = _run(["cargo", "metadata", "--offline", "--locked", "--format-version", "1"])
    assert result.returncode == 0, result.stderr
    for rid in _required_ids():
        assert f'"name":"{rid}"' in result.stdout.replace(" ", "") or f'"name": "{rid}"' in result.stdout


def test_u9_bitflags_digest():
    """bitflags lock checksum matches the active mirror crate body."""
    locks = _lock_checksums()
    versions = _versions_from_lock()
    assert locks["bitflags"] == _sha256(_crate_path("bitflags", versions["bitflags"]))


def test_u10_cfg_if_digest():
    """cfg-if lock checksum matches the active mirror crate body (not the stale overlay)."""
    locks = _lock_checksums()
    versions = _versions_from_lock()
    active = _sha256(_crate_path("cfg-if", versions["cfg-if"]))
    stale = _sha256(STALE / f"cfg-if-{versions['cfg-if']}.crate")
    assert locks["cfg-if"] == active
    assert active != stale
