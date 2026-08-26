#!/usr/bin/env python3
"""Generate /app/data job trees, endpoints, and fixture pins for CDC vault v3."""
from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / "environment"
DATA = ENV / "data"
TESTS = ROOT / "tests"
sys.path.insert(0, str(TESTS))
from _reference import derive_policy, sha256_hex  # noqa: E402

# Stable public fixture: first 256 bytes of a known URL body pinned at generate time.
# Prefer raw.githubusercontentusercontent small file; fallback to local synthetic policy.
POLICY_CANDIDATES = [
    "https://www.ietf.org/rfc/rfc6234.txt",
]


def write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def build_trees() -> None:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)

    jobs = []

    # baseline: mixed small files + duplicate content
    base = DATA / "jobs" / "baseline" / "src"
    write_file(base / "a.txt", b"hello-baseline-" + b"A" * 4000)
    write_file(base / "b.txt", b"hello-baseline-" + b"A" * 4000)  # duplicate of a
    write_file(base / "c/bin.dat", bytes(range(256)) * 20)
    write_file(DATA / "jobs" / "baseline" / "backup_config.json", json.dumps({"exclude": ["*.tmp"], "gzip_level": 6}, indent=2).encode() + b"\n")
    jobs.append({"id": "baseline", "src": "jobs/baseline/src", "config": "jobs/baseline/backup_config.json"})

    # sparse-primary: long zero run
    sp = DATA / "jobs" / "sparse-primary" / "src"
    write_file(sp / "hole.bin", b"HEAD" + b"\x00" * 5000 + b"TAIL" + b"X" * 3500)
    write_file(DATA / "jobs" / "sparse-primary" / "backup_config.json", json.dumps({"exclude": [], "gzip_level": 1}, indent=2).encode() + b"\n")
    jobs.append({"id": "sparse-primary", "src": "jobs/sparse-primary/src", "config": "jobs/sparse-primary/backup_config.json"})

    # cross-job-alpha / beta share file content
    ca = DATA / "jobs" / "cross-job-alpha" / "src"
    shared = b"CROSS-SHARE-PAYLOAD-" + os.urandom(0) + (b"Z" * 8000)
    write_file(ca / "shared.bin", shared)
    write_file(ca / "only-a.txt", b"alpha-only-" + b"1" * 3200)
    write_file(DATA / "jobs" / "cross-job-alpha" / "backup_config.json", json.dumps({"exclude": [], "gzip_level": 9}, indent=2).encode() + b"\n")
    jobs.append({"id": "cross-job-alpha", "src": "jobs/cross-job-alpha/src", "config": "jobs/cross-job-alpha/backup_config.json"})

    cb = DATA / "jobs" / "cross-job-beta" / "src"
    write_file(cb / "shared.bin", shared)
    write_file(cb / "only-b.txt", b"beta-only-" + b"2" * 3200)
    write_file(DATA / "jobs" / "cross-job-beta" / "backup_config.json", json.dumps({"exclude": [], "gzip_level": 9}, indent=2).encode() + b"\n")
    jobs.append({"id": "cross-job-beta", "src": "jobs/cross-job-beta/src", "config": "jobs/cross-job-beta/backup_config.json"})

    # symlink-pack (symlink created in Dockerfile after COPY — avoid symlinks in build context)
    sy = DATA / "jobs" / "symlink-pack" / "src"
    write_file(sy / "real.txt", b"symlink-target-body-" + b"S" * 3100)
    (sy / "links").mkdir(parents=True, exist_ok=True)
    write_file(sy / "links" / ".keep", b"")
    write_file(DATA / "jobs" / "symlink-pack" / "backup_config.json", json.dumps({"exclude": [], "gzip_level": 6}, indent=2).encode() + b"\n")
    jobs.append({"id": "symlink-pack", "src": "jobs/symlink-pack/src", "config": "jobs/symlink-pack/backup_config.json"})

    # hardlink-cluster (second link created in Dockerfile — avoid hardlinks in build context)
    hl = DATA / "jobs" / "hardlink-cluster" / "src" / "hard"
    hl.mkdir(parents=True, exist_ok=True)
    write_file(hl / "a", b"hardlink-body-" + b"H" * 6000)
    write_file(DATA / "jobs" / "hardlink-cluster" / "backup_config.json", json.dumps({"exclude": [], "gzip_level": 6}, indent=2).encode() + b"\n")
    jobs.append({"id": "hardlink-cluster", "src": "jobs/hardlink-cluster/src", "config": "jobs/hardlink-cluster/backup_config.json"})

    # exclude-heavy
    ex = DATA / "jobs" / "exclude-heavy" / "src"
    write_file(ex / "keep.txt", b"keep-me-" + b"K" * 3100)
    write_file(ex / "drop.tmp", b"should-exclude")
    write_file(ex / "nested" / "x.log", b"also-exclude")
    write_file(DATA / "jobs" / "exclude-heavy" / "backup_config.json", json.dumps({"exclude": ["*.tmp", "*.log"], "gzip_level": 6}, indent=2).encode() + b"\n")
    jobs.append({"id": "exclude-heavy", "src": "jobs/exclude-heavy/src", "config": "jobs/exclude-heavy/backup_config.json"})

    # empty_job — empty after excludes
    ej = DATA / "jobs" / "empty_job" / "src"
    write_file(ej / "only.tmp", b"x")
    write_file(DATA / "jobs" / "empty_job" / "backup_config.json", json.dumps({"exclude": ["*.tmp"], "gzip_level": 6}, indent=2).encode() + b"\n")
    jobs.append({"id": "empty_job", "src": "jobs/empty_job/src", "config": "jobs/empty_job/backup_config.json"})

    # quarantine
    q = DATA / "jobs" / "quarantine-hit" / "src"
    write_file(q / "ok.txt", b"ok-" + b"O" * 3100)
    write_file(q / "bad__deny__x.txt", b"denied")
    write_file(DATA / "jobs" / "quarantine-hit" / "backup_config.json", json.dumps({"exclude": [], "gzip_level": 6}, indent=2).encode() + b"\n")
    jobs.append({"id": "quarantine-hit", "src": "jobs/quarantine-hit/src", "config": "jobs/quarantine-hit/backup_config.json"})

    # zero-byte
    zb = DATA / "jobs" / "zero-byte-pack" / "src"
    write_file(zb / "empty", b"")
    write_file(zb / "tiny.txt", b"tiny-" + b"T" * 3100)
    write_file(DATA / "jobs" / "zero-byte-pack" / "backup_config.json", json.dumps({"exclude": [], "gzip_level": 1}, indent=2).encode() + b"\n")
    jobs.append({"id": "zero-byte-pack", "src": "jobs/zero-byte-pack/src", "config": "jobs/zero-byte-pack/backup_config.json"})

    # deep-nest
    dn = DATA / "jobs" / "deep-nest" / "src"
    write_file(dn / "a/b/c/d/e.txt", b"deep-" + b"D" * 5000)
    write_file(DATA / "jobs" / "deep-nest" / "backup_config.json", json.dumps({"exclude": [], "gzip_level": 6}, indent=2).encode() + b"\n")
    jobs.append({"id": "deep-nest", "src": "jobs/deep-nest/src", "config": "jobs/deep-nest/backup_config.json"})

    (DATA / "manifest.json").write_text(json.dumps({"version": 1, "jobs": jobs}, indent=2) + "\n", encoding="utf-8")


def fetch_policy() -> tuple[str, bytes]:
    last_err = None
    for url in POLICY_CANDIDATES:
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                body = resp.read()
            if len(body) > 100:
                return url, body
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    # synthetic fallback committed for offline regen
    body = b"CDC-VAULT-POLICY-V3\n" + bytes(range(256)) * 4
    url = "https://example.invalid/policy/v3.bin"
    print("warning: using synthetic policy", last_err)
    return url, body


def main() -> None:
    build_trees()
    url, body = fetch_policy()
    digest = sha256_hex(body)
    (DATA / "endpoints.json").write_text(
        json.dumps({"policy_material_url": url, "policy_material_sha256": digest}, indent=2) + "\n",
        encoding="utf-8",
    )
    # Bundle policy bytes for docker offline? SPEC requires live fetch.
    # Store under environment for tests to also serve locally if needed.
    (ENV / "tools" / "policy_body.bin").write_bytes(body)

    out = TESTS / "fixtures" / "expected_output"
    if out.exists():
        shutil.rmtree(out)

    # pin input hashes
    pins = {}
    for p in sorted(DATA.rglob("*")):
        if p.is_file() and not p.is_symlink():
            rel = str(p.relative_to(DATA)).replace("\\", "/")
            pins[rel] = sha256_hex(p.read_bytes())
    (TESTS / "fixtures" / "_input_sha256.json").write_text(json.dumps(pins, indent=2) + "\n")
    policy = derive_policy(body)
    (TESTS / "fixtures" / "policy_meta.json").write_text(
        json.dumps({"url": url, "sha256": digest, "mac_key_hex": policy["mac_key_hex"]}, indent=2) + "\n"
    )
    print("jobs", len(json.loads((DATA / "manifest.json").read_text())["jobs"]))
    print("policy", digest[:16], "len", len(body))


if __name__ == "__main__":
    main()
