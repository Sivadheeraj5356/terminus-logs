# ruff: noqa: E501
"""Gated hard verifier for CDC vault v3 (~55 discriminating tests)."""
from __future__ import annotations

import gzip
import hashlib
import hmac
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any

import pytest

from _reference import (
    ZERO64,
    derive_policy,
    dumps,
    merkle_root,
    process_batch,
    sha256_hex,
    sha512_256_hex,
)

BINARY = Path("/app/bin/backup-dedup")
MAIN_GO = Path("/app/main.go")
RUN_SH = Path("/app/run.sh")
OUTPUT = Path("/app/output")
DATA = Path("/app/data")
SPEC = Path("/app/spec/SPEC.md")
RESOURCES = Path("/app/resources")
REMOTE = RESOURCES / "remote_catalog"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
INPUT_SHA = json.loads((FIXTURES / "_input_sha256.json").read_text(encoding="utf-8"))

OK_JOBS = [
    "baseline",
    "sparse-primary",
    "cross-job-alpha",
    "cross-job-beta",
    "symlink-pack",
    "hardlink-cluster",
    "exclude-heavy",
    "zero-byte-pack",
    "deep-nest",
]


class Gates:
    infra = False
    policy = False
    batch = False
    crypto = False
    catalog = False
    remote = False


def require_gate(name: str) -> None:
    assert getattr(Gates, name), f"gate {name} must pass first"


def run_backup() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(RUN_SH)], capture_output=True, text=True, timeout=600, check=False
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def report_rows() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (OUTPUT / "report.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def row_by_id(job_id: str) -> dict[str, Any]:
    for row in report_rows():
        if row["job_id"] == job_id:
            return row
    raise AssertionError(job_id)


def fetch_policy() -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    import urllib.request

    ep = load_json(DATA / "endpoints.json")
    with urllib.request.urlopen(ep["policy_material_url"], timeout=120) as resp:
        body = resp.read()
    return ep, body, derive_policy(body)


def stage_remote_job() -> None:
    src = REMOTE / "jobs" / "remote-holdout" / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "hold.bin").write_bytes(b"REMOTE-HOLD-" + b"R" * 9000)
    cfg = REMOTE / "jobs" / "remote-holdout" / "backup_config.json"
    cfg.write_text(
        json.dumps({"exclude": [], "gzip_level": 6}, indent=2) + "\n", encoding="utf-8"
    )
    (REMOTE / "extra_jobs.json").write_text(
        json.dumps(
            [
                {
                    "id": "remote-holdout",
                    "src": "jobs/remote-holdout/src",
                    "config": "jobs/remote-holdout/backup_config.json",
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


@pytest.fixture(scope="session", autouse=True)
def baseline() -> None:
    assert MAIN_GO.is_file(), "missing /app/main.go"
    assert RUN_SH.is_file(), "missing /app/run.sh"
    assert not Path("/app/starter.go").is_file()
    if REMOTE.exists():
        shutil.rmtree(REMOTE)
    REMOTE.mkdir(parents=True, exist_ok=True)
    proc = run_backup()
    assert proc.returncode == 0, proc.stderr[:800]
    assert proc.stdout == "" and proc.stderr == ""
    assert (OUTPUT / "policy_receipt.json").is_file()
    Gates.infra = True
    Gates.policy = True


# ---- infra ----


def test_binary_is_static_elf() -> None:
    """Release binary must be an executable ELF at /app/bin/backup-dedup."""
    require_gate("infra")
    assert BINARY.is_file()
    assert BINARY.read_bytes()[:4] == b"\x7fELF"


def test_spec_describes_gear_cdc() -> None:
    """SPEC.md must document gear-table CDC, HMAC attestation, and remote catalog."""
    require_gate("infra")
    text = SPEC.read_text(encoding="utf-8")
    assert "gear_seed" in text and "SHA-512/256" in text and "HMAC-SHA256" in text
    assert "0xA5" in text and "store_binding" in text and "extra_jobs.json" in text


def test_run_sh_mentions_cgo_off() -> None:
    """run.sh must disable CGO and build backup-dedup."""
    require_gate("infra")
    text = RUN_SH.read_text(encoding="utf-8")
    assert "CGO_ENABLED=0" in text and "backup-dedup" in text


def test_inputs_sha_pinned() -> None:
    """Bundled /app/data files must match pinned digests."""
    require_gate("infra")
    for rel, digest in INPUT_SHA.items():
        assert sha256_hex((DATA / rel).read_bytes()) == digest, rel


# ---- policy ----


def test_policy_receipt_keys_and_live_fetch() -> None:
    """policy_receipt must match a live download of the pinned policy URL."""
    require_gate("policy")
    ep, body, pol = fetch_policy()
    assert pol["sha256"] == ep["policy_material_sha256"]
    receipt = load_json(OUTPUT / "policy_receipt.json")
    assert list(receipt.keys()) == [
        "url",
        "sha256",
        "byte_length",
        "attestation_domain",
        "gear_seed_hex",
        "store_salt_hex",
        "mac_key_hex",
    ]
    assert receipt["url"] == ep["policy_material_url"]
    assert receipt["sha256"] == pol["sha256"]
    assert receipt["byte_length"] == len(body)
    assert receipt["attestation_domain"] == pol["attestation_domain"]
    assert receipt["gear_seed_hex"] == pol["gear_seed_hex"]
    assert receipt["store_salt_hex"] == pol["store_salt_hex"]
    assert receipt["mac_key_hex"] == pol["mac_key_hex"]
    Gates.batch = True


def test_report_jsonl_covers_all_manifest_jobs() -> None:
    """report.jsonl must include every manifest job id in order with compact key order."""
    require_gate("batch")
    man = load_json(DATA / "manifest.json")
    lines = (OUTPUT / "report.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(man["jobs"])
    rows = report_rows()
    assert [r["job_id"] for r in rows] == [j["id"] for j in man["jobs"]]
    for line, row in zip(lines, rows):
        assert line == json.dumps(row, separators=(",", ":"), ensure_ascii=False)
        assert list(json.loads(line).keys()) == [
            "job_id",
            "status",
            "file_count",
            "byte_count",
            "chunk_count",
            "unique_chunks",
            "merkle_root",
        ]


def test_empty_job_failed() -> None:
    """empty_job must be reported failed with null metrics and no job directory."""
    require_gate("batch")
    row = row_by_id("empty_job")
    assert row["status"] == "failed"
    assert row["file_count"] is None and row["merkle_root"] is None
    assert not (OUTPUT / "jobs" / "empty_job").exists()


def test_quarantine_job() -> None:
    """quarantine-hit must be quarantined, omitted from ledger, and lack a job dir."""
    require_gate("batch")
    row = row_by_id("quarantine-hit")
    assert row["status"] == "quarantined"
    assert row["chunk_count"] is None
    assert not (OUTPUT / "jobs" / "quarantine-hit").exists()
    ledger_ids = [e["job_id"] for e in load_json(OUTPUT / "ledger.json")["entries"]]
    assert "quarantine-hit" not in ledger_ids
    assert "empty_job" not in ledger_ids


@pytest.mark.parametrize("job_id", OK_JOBS)
def test_successful_job_artifact_set(job_id: str) -> None:
    """Each successful job must emit the full artifact set with non-empty summary."""
    require_gate("batch")
    base = OUTPUT / "jobs" / job_id
    for name in (
        "manifest.json",
        "chunk_catalog.json",
        "dedup_report.json",
        "restoration_map.json",
        "summary.json",
        "archive.tar.gz",
        "attestation.json",
    ):
        assert (base / name).is_file(), name
    summary = load_json(base / "summary.json")
    assert summary["job_id"] == job_id
    assert summary["file_count"] >= 1
    Gates.crypto = True


# ---- crypto / merkle / attestation ----


def test_ledger_chain_matches_merkle_and_binding() -> None:
    """Ledger entry hashes must chain prev_hash||job||merkle||store_binding."""
    require_gate("crypto")
    ledger = load_json(OUTPUT / "ledger.json")["entries"]
    assert [e["job_id"] for e in ledger] == OK_JOBS
    prev = ZERO64
    for entry in ledger:
        assert list(entry.keys()) == [
            "job_id",
            "merkle_root",
            "store_binding",
            "prev_hash",
            "entry_hash",
        ]
        att = load_json(OUTPUT / "jobs" / entry["job_id"] / "attestation.json")
        assert entry["merkle_root"] == att["merkle_root"]
        assert entry["store_binding"] == att["store_binding"]
        expect = sha256_hex(
            (prev + entry["job_id"] + entry["merkle_root"] + entry["store_binding"]).encode(
                "ascii"
            )
        )
        assert entry["entry_hash"] == expect
        assert entry["prev_hash"] == prev
        prev = entry["entry_hash"]


def test_attestation_hmac_verifies() -> None:
    """Attestation signature_hex must equal HMAC-SHA256 over the normative message."""
    require_gate("crypto")
    _, _, pol = fetch_policy()
    for entry in load_json(OUTPUT / "ledger.json")["entries"]:
        jid = entry["job_id"]
        att = load_json(OUTPUT / "jobs" / jid / "attestation.json")
        man_bytes = (OUTPUT / "jobs" / jid / "manifest.json").read_bytes()
        msg = "\n".join(
            [
                att["domain"],
                jid,
                att["merkle_root"],
                sha256_hex(man_bytes),
                att["store_binding"],
            ]
        ).encode("utf-8")
        expect = hmac.new(pol["mac_key"], msg, hashlib.sha256).hexdigest()
        assert att["signature_hex"] == expect
        assert att["domain"] == pol["attestation_domain"]
        assert att["manifest_sha256"] == sha256_hex(man_bytes)


def test_store_binding_matches_catalog() -> None:
    """store_binding must hash sorted unique store_name values joined by newlines."""
    require_gate("crypto")
    for job_id in ("baseline", "cross-job-beta", "hardlink-cluster"):
        cat = load_json(OUTPUT / "jobs" / job_id / "chunk_catalog.json")
        names = sorted({c["store_name"] for c in cat["chunks"]})
        expect = sha256_hex("\n".join(names).encode("ascii"))
        att = load_json(OUTPUT / "jobs" / job_id / "attestation.json")
        assert att["store_binding"] == expect


@pytest.mark.parametrize("job_id", OK_JOBS)
def test_merkle_root_matches_catalog(job_id: str) -> None:
    """summary merkle_root must equal Merkle over unique catalog chunk_ids."""
    require_gate("crypto")
    cat = load_json(OUTPUT / "jobs" / job_id / "chunk_catalog.json")
    ids = [c["chunk_id"] for c in cat["chunks"]]
    assert ids == sorted(ids)
    summary = load_json(OUTPUT / "jobs" / job_id / "summary.json")
    assert summary["merkle_root"] == merkle_root(ids)


def test_chunk_ids_are_sha512_256() -> None:
    """Stored chunk bytes must hash to catalog chunk_id via SHA-512/256."""
    require_gate("crypto")
    cat = load_json(OUTPUT / "jobs" / "baseline" / "chunk_catalog.json")
    assert cat["chunks"], "expected chunks"
    for ch in cat["chunks"]:
        store = OUTPUT / "chunk_store" / ch["store_name"][:2] / ch["store_name"]
        assert store.is_file()
        raw = store.read_bytes()
        assert sha512_256_hex(raw) == ch["chunk_id"]
        assert len(raw) == ch["size"]
        assert 1 <= ch["size"] <= 12288
    Gates.catalog = True


def test_store_name_uses_salt() -> None:
    """store_name must be SHA-256(store_salt||chunk), not raw chunk_id."""
    require_gate("catalog")
    _, _, pol = fetch_policy()
    cat = load_json(OUTPUT / "jobs" / "baseline" / "chunk_catalog.json")
    for ch0 in cat["chunks"][:3]:
        raw = (OUTPUT / "chunk_store" / ch0["store_name"][:2] / ch0["store_name"]).read_bytes()
        assert sha256_hex(pol["store_salt"] + raw) == ch0["store_name"]
        assert ch0["store_name"] != ch0["chunk_id"]


def test_cdc_nonfinal_chunks_respect_bounds() -> None:
    """Non-final CDC chunks must be in [3072, 12288]; final may be shorter."""
    require_gate("catalog")
    man = load_json(OUTPUT / "jobs" / "baseline" / "manifest.json")
    cat = {c["chunk_id"]: c for c in load_json(OUTPUT / "jobs" / "baseline" / "chunk_catalog.json")["chunks"]}
    for f in man["files"]:
        if f["kind"] != "regular" or not f["chunk_ids"]:
            continue
        sizes = [cat[cid]["size"] for cid in f["chunk_ids"]]
        for sz in sizes[:-1]:
            assert 3072 <= sz <= 12288, sizes
        assert 1 <= sizes[-1] <= 12288


def test_sparse_holes_recorded_exact() -> None:
    """sparse-primary must record the exact 5000-byte zero hole at offset 4."""
    require_gate("catalog")
    rm = load_json(OUTPUT / "jobs" / "sparse-primary" / "restoration_map.json")
    entry = next(e for e in rm["entries"] if e["path"] == "hole.bin")
    assert {"offset": 4, "length": 5000} in entry["holes"]
    assert entry["holes"] == sorted(entry["holes"], key=lambda h: h["offset"])


def test_hardlink_alias_shares_chunks() -> None:
    """hardlink-cluster alias must reference primary_path and share chunk_ids."""
    require_gate("catalog")
    man = load_json(OUTPUT / "jobs" / "hardlink-cluster" / "manifest.json")
    by_path = {f["path"]: f for f in man["files"]}
    prim = by_path["hard/a"]
    alias = by_path["hard/b"]
    assert prim["kind"] == "regular"
    assert alias["kind"] == "hardlink"
    assert alias["primary_path"] == "hard/a"
    assert alias["chunk_ids"] == prim["chunk_ids"]
    assert alias["file_id"] == prim["file_id"]
    dedup = load_json(OUTPUT / "jobs" / "hardlink-cluster" / "dedup_report.json")
    assert dedup["primary_files"] == 1 and dedup["alias_files"] == 1


def test_symlink_has_target_no_chunks() -> None:
    """symlink-pack link entry must carry link_target and empty chunk_ids."""
    require_gate("catalog")
    man = load_json(OUTPUT / "jobs" / "symlink-pack" / "manifest.json")
    link = next(f for f in man["files"] if f["kind"] == "symlink")
    assert link["path"] == "links/to-real"
    assert link["link_target"] in ("../real.txt", "real.txt")
    assert link["chunk_ids"] == []
    assert link["file_id"] is None


def test_exclude_drops_tmp_and_log() -> None:
    """exclude-heavy must keep keep.txt and drop *.tmp/*.log paths."""
    require_gate("catalog")
    man = load_json(OUTPUT / "jobs" / "exclude-heavy" / "manifest.json")
    paths = {f["path"] for f in man["files"]}
    assert paths == {"keep.txt"}


def test_cross_job_dedup_shared_store_object() -> None:
    """Identical cross-job payloads must share one chunk_store object and file_id."""
    require_gate("catalog")
    a = load_json(OUTPUT / "jobs" / "cross-job-alpha" / "manifest.json")
    b = load_json(OUTPUT / "jobs" / "cross-job-beta" / "manifest.json")
    af = next(f for f in a["files"] if f["path"] == "shared.bin")
    bf = next(f for f in b["files"] if f["path"] == "shared.bin")
    assert af["file_id"] == bf["file_id"]
    assert af["chunk_ids"] == bf["chunk_ids"]
    da = load_json(OUTPUT / "jobs" / "cross-job-alpha" / "dedup_report.json")
    db = load_json(OUTPUT / "jobs" / "cross-job-beta" / "dedup_report.json")
    assert da["stored_bytes"] > 0
    assert db["stored_bytes"] < da["stored_bytes"]


def test_baseline_duplicate_files_share_file_id() -> None:
    """baseline a.txt and b.txt must share file_id and chunk_ids when contents match."""
    require_gate("catalog")
    man = load_json(OUTPUT / "jobs" / "baseline" / "manifest.json")
    by = {f["path"]: f for f in man["files"]}
    assert by["a.txt"]["file_id"] == by["b.txt"]["file_id"]
    assert by["a.txt"]["chunk_ids"] == by["b.txt"]["chunk_ids"]
    cat = load_json(OUTPUT / "jobs" / "baseline" / "chunk_catalog.json")
    for cid in by["a.txt"]["chunk_ids"]:
        entry = next(c for c in cat["chunks"] if c["chunk_id"] == cid)
        assert entry["ref_count"] >= 2


def test_zero_byte_empty_chunk_ids() -> None:
    """Empty regular file must use chunk_ids [] and zero merkle when alone is not required."""
    require_gate("catalog")
    man = load_json(OUTPUT / "jobs" / "zero-byte-pack" / "manifest.json")
    empty = next(f for f in man["files"] if f["path"] == "empty")
    assert empty["chunk_ids"] == []
    assert empty["size"] == 0
    assert empty["kind"] == "regular"


def test_global_registry_matches_reference_refcounts() -> None:
    """global_chunk_registry must match an independent reference rebuild."""
    require_gate("catalog")
    ep, body, _ = fetch_policy()
    tmp = Path("/tmp/cdc_ref_global")
    if tmp.exists():
        shutil.rmtree(tmp)
    process_batch(DATA, tmp, body, ep["policy_material_url"])
    got = load_json(OUTPUT / "global_chunk_registry.json")
    ref = load_json(tmp / "global_chunk_registry.json")
    assert got == ref


def test_deterministic_rerun() -> None:
    """Re-running must reproduce ledger and baseline attestation bytes."""
    require_gate("catalog")
    before_ledger = (OUTPUT / "ledger.json").read_bytes()
    before_att = (OUTPUT / "jobs" / "baseline" / "attestation.json").read_bytes()
    before_receipt = (OUTPUT / "policy_receipt.json").read_bytes()
    shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()
    assert run_backup().returncode == 0
    assert (OUTPUT / "ledger.json").read_bytes() == before_ledger
    assert (OUTPUT / "jobs" / "baseline" / "attestation.json").read_bytes() == before_att
    assert (OUTPUT / "policy_receipt.json").read_bytes() == before_receipt


def test_reference_rebuild_matches_job_artifacts() -> None:
    """Independent Python rebuild must match agent summaries, catalogs, and dedup reports."""
    require_gate("catalog")
    ep, body, _ = fetch_policy()
    tmp = Path("/tmp/cdc_ref_jobs")
    if tmp.exists():
        shutil.rmtree(tmp)
    process_batch(DATA, tmp, body, ep["policy_material_url"])
    for job_id in OK_JOBS:
        for name in ("summary.json", "chunk_catalog.json", "dedup_report.json", "restoration_map.json"):
            assert load_json(OUTPUT / "jobs" / job_id / name) == load_json(
                tmp / "jobs" / job_id / name
            ), f"{job_id}/{name}"
        assert load_json(OUTPUT / "jobs" / job_id / "manifest.json") == load_json(
            tmp / "jobs" / job_id / "manifest.json"
        )
    assert load_json(OUTPUT / "ledger.json") == load_json(tmp / "ledger.json")


@pytest.mark.parametrize("job_id", OK_JOBS)
def test_summary_matches_report_row(job_id: str) -> None:
    """summary.json counters must match the compact report.jsonl row."""
    require_gate("catalog")
    row = row_by_id(job_id)
    summary = load_json(OUTPUT / "jobs" / job_id / "summary.json")
    assert summary["file_count"] == row["file_count"]
    assert summary["byte_count"] == row["byte_count"]
    assert summary["chunk_count"] == row["chunk_count"]
    assert summary["unique_chunks"] == row["unique_chunks"]
    assert summary["merkle_root"] == row["merkle_root"]


@pytest.mark.parametrize("job_id", ["baseline", "cross-job-alpha", "deep-nest"])
def test_attestation_key_order(job_id: str) -> None:
    """attestation.json must use the normative key order."""
    require_gate("crypto")
    raw = (OUTPUT / "jobs" / job_id / "attestation.json").read_text(encoding="utf-8")
    obj = json.loads(raw)
    assert list(obj.keys()) == [
        "job_id",
        "merkle_root",
        "domain",
        "manifest_sha256",
        "store_binding",
        "signature_hex",
    ]
    assert raw == dumps(obj)


def test_archive_members_match_manifest() -> None:
    """archive.tar.gz members must match manifest paths/kinds with ustar hardlink/symlink rules."""
    require_gate("catalog")
    for job_id in ("baseline", "hardlink-cluster", "symlink-pack"):
        man = load_json(OUTPUT / "jobs" / job_id / "manifest.json")
        data = (OUTPUT / "jobs" / job_id / "archive.tar.gz").read_bytes()
        assert data[:2] == b"\x1f\x8b"
        with gzip.open(io.BytesIO(data), "rb") as gz:
            with tarfile.open(fileobj=gz, mode="r:") as tar:
                members = [m for m in tar.getmembers()]
        assert [m.name for m in members] == [f["path"] for f in man["files"]]
        for m, f in zip(members, man["files"]):
            if f["kind"] == "symlink":
                assert m.issym()
                assert m.linkname == f["link_target"]
            elif f["kind"] == "hardlink":
                assert m.islnk()
                assert m.linkname == f["primary_path"]
            else:
                assert m.isreg()
                assert m.size == f["size"]


def test_deep_nest_path_preserved() -> None:
    """deep-nest must retain nested relative path a/b/c/d/e.txt with matching file_id."""
    require_gate("catalog")
    man = load_json(OUTPUT / "jobs" / "deep-nest" / "manifest.json")
    deep = next(f for f in man["files"] if f["path"] == "a/b/c/d/e.txt")
    body = (DATA / "jobs" / "deep-nest" / "src" / "a/b/c/d/e.txt").read_bytes()
    assert deep["file_id"] == sha512_256_hex(body)
    assert deep["size"] == len(body)


def test_remote_holdout_appends_ledger() -> None:
    """Staging remote-holdout must extend report/ledger and keep prior merkle roots."""
    require_gate("catalog")
    before_roots = {
        jid: load_json(OUTPUT / "jobs" / jid / "summary.json")["merkle_root"] for jid in OK_JOBS
    }
    stage_remote_job()
    shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()
    assert run_backup().returncode == 0
    rows = report_rows()
    assert rows[-1]["job_id"] == "remote-holdout" and rows[-1]["status"] == "ok"
    assert [r["job_id"] for r in rows[:-1]] == [j["id"] for j in load_json(DATA / "manifest.json")["jobs"]]
    ledger = load_json(OUTPUT / "ledger.json")["entries"]
    assert ledger[-1]["job_id"] == "remote-holdout"
    for jid, root in before_roots.items():
        assert load_json(OUTPUT / "jobs" / jid / "summary.json")["merkle_root"] == root
    rem = load_json(OUTPUT / "jobs" / "remote-holdout" / "summary.json")
    assert rem["file_count"] == 1 and rem["unique_chunks"] >= 1
    # reference agreement for remote job
    ep, body, _ = fetch_policy()
    tmp = Path("/tmp/cdc_ref_remote")
    if tmp.exists():
        shutil.rmtree(tmp)
    process_batch(DATA, tmp, body, ep["policy_material_url"])
    assert load_json(OUTPUT / "jobs" / "remote-holdout" / "summary.json") == load_json(
        tmp / "jobs" / "remote-holdout" / "summary.json"
    )
    Gates.remote = True


def test_remote_attestation_hmac() -> None:
    """remote-holdout attestation must verify under the same policy mac_key."""
    require_gate("remote")
    _, _, pol = fetch_policy()
    att = load_json(OUTPUT / "jobs" / "remote-holdout" / "attestation.json")
    man_bytes = (OUTPUT / "jobs" / "remote-holdout" / "manifest.json").read_bytes()
    msg = "\n".join(
        [
            att["domain"],
            "remote-holdout",
            att["merkle_root"],
            sha256_hex(man_bytes),
            att["store_binding"],
        ]
    ).encode("utf-8")
    assert att["signature_hex"] == hmac.new(pol["mac_key"], msg, hashlib.sha256).hexdigest()


def test_no_output_formats_json() -> None:
    """Task must not ship output_formats.json; SPEC.md is normative."""
    require_gate("infra")
    assert not (Path("/app/spec") / "output_formats.json").exists()
    assert not (Path("/app/spec") / "cdc_contract.json").exists()
