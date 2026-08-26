"""Behavioral verifier for Gradle HF asset lock enforcement."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

APP = Path("/app")
LOCK = APP / "config" / "hf-assets.lock.json"
MIRROR = Path(os.environ.get("HF_MIRROR_ROOT", "/data/hf-mirror"))
TRANSCRIPT = Path(os.environ.get("HF_TRANSCRIPT", "/app/docs/release-council-transcript.md"))
SCHEMA = APP / "config" / "hf-assets.lock.schema.json"
HF_REPO = "HuggingFaceFW/fineweb-edu-score-2"
PUBLIC_ROUTE = "public-synonym"
FINAL_RE = re.compile(r"<!--\s*FINAL_RATIFIED:([^>]+)-->", re.MULTILINE)
GENERATED_SEED = 428711
ACCUM_SEED = 739221
GRADLE_LOCK_DIR = APP / "gradle" / "dependency-locks"


@dataclass(frozen=True)
class RoutePolicy:
    route_id: str
    revision: str
    files: tuple[str, ...]
    forbidden: tuple[str, ...] = ()


def _parse_kv(blob: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in blob.strip().split():
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        out[key] = value
    return out


def load_policy(transcript_path: Path) -> RoutePolicy:
    text = transcript_path.read_text(encoding="utf-8")
    revision = ""
    files: set[str] = set()
    forbidden: set[str] = set()
    for match in FINAL_RE.finditer(text):
        kv = _parse_kv(match.group(1))
        if kv.get("route") != PUBLIC_ROUTE:
            continue
        if "revision" in kv:
            revision = kv["revision"]
        if "files" in kv:
            files.update(f for f in kv["files"].split(",") if f)
        if "forbidden" in kv:
            forbidden.update(f for f in kv["forbidden"].split(",") if f)
    if not revision:
        raise RuntimeError("no approved revision in transcript")
    return RoutePolicy(
        route_id=PUBLIC_ROUTE,
        revision=revision,
        files=tuple(sorted(files)),
        forbidden=tuple(sorted(forbidden)),
    )


def approved_revision(transcript_path: Path) -> str:
    return load_policy(transcript_path).revision


def stale_revision(mirror_root: Path) -> str:
    index = mirror_root / HF_REPO / "fineweb-edu-score-2" / "repo-index.json"
    revisions = json.loads(index.read_text(encoding="utf-8"))["revisions"]
    approved = approved_revision(Path("/app/docs/release-council-transcript.md"))
    for rev in revisions:
        if rev != approved:
            return rev
    raise RuntimeError("no stale revision in mirror index")


def forbidden_files(transcript_path: Path) -> tuple[str, ...]:
    return load_policy(transcript_path).forbidden


def forbidden_only_term(mirror_root: Path) -> str:
    rev = approved_revision(Path("/app/docs/release-council-transcript.md"))
    forbidden = forbidden_files(Path("/app/docs/release-council-transcript.md"))[0]
    path = mirror_root / HF_REPO / "fineweb-edu-score-2" / "revisions" / rev / "files" / forbidden
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        return str(row["term"])
    raise RuntimeError("forbidden file empty")


def eval_only_alias(mirror_root: Path) -> str:
    rev = approved_revision(Path("/app/docs/release-council-transcript.md"))
    path = mirror_root / HF_REPO / "fineweb-edu-score-2" / "revisions" / rev / "files" / "synonym-expansion-eval.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        for syn in row.get("synonyms", []):
            return str(syn.get("value", ""))
    raise RuntimeError("eval file empty")


def transcript_digest(transcript_path: Path) -> str:
    out = subprocess.check_output(["sha256sum", str(transcript_path)], text=True)
    return out.split()[0]


def repo_root(mirror_root: Path) -> Path:
    return mirror_root / HF_REPO / "fineweb-edu-score-2"


def revision_dir(mirror_root: Path, revision: str) -> Path:
    return repo_root(mirror_root) / "revisions" / revision


def file_checksum(path: Path) -> tuple[str, int]:
    out = subprocess.check_output(["sha256sum", str(path)], text=True)
    digest = out.split()[0]
    return digest, path.stat().st_size


def metadata_digest(mirror_root: Path, revision: str) -> str:
    meta_path = revision_dir(mirror_root, revision) / "metadata.json"
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonicalize(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def route_files(lock: dict[str, Any], route_id: str) -> list[dict[str, Any]]:
    for route in lock.get("routes", []):
        if route.get("route_id") == route_id:
            return list(route.get("files", []))
    return []


def gradle_lock_digest(app_home: Path) -> str:
    lock_dir = app_home / "gradle" / "dependency-locks"
    parts: list[bytes] = []
    for path in sorted(lock_dir.glob("*.lockfile")):
        data = path.read_bytes().replace(b"\r\n", b"\n")
        parts.append(path.name.encode() + b"\0" + data)
    payload = b"".join(parts)
    proc = subprocess.run(["sha256sum"], input=payload, capture_output=True, check=True)
    return proc.stdout.decode().split()[0]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def verifier_lockfile_name(seed: int) -> str:
    token = hashlib.sha256(str(seed).encode()).hexdigest()[:12]
    return f"{token}.lockfile"


def source_input_fingerprint() -> dict[str, str]:
    policy = load_policy(TRANSCRIPT)
    rev_dir = revision_dir(MIRROR, policy.revision)
    return {
        "transcript": sha256_file(TRANSCRIPT),
        "metadata": sha256_file(rev_dir / "metadata.json"),
        "gradle_locks": gradle_lock_digest(APP),
        "train_asset": sha256_file(rev_dir / "files" / "synonym-expansion-train.jsonl"),
        "dev_asset": sha256_file(rev_dir / "files" / "synonym-expansion-dev.jsonl"),
    }


def lock_abandoned_siblings() -> list[Path]:
    lock_dir = LOCK.parent
    return [
        path
        for path in lock_dir.iterdir()
        if path != LOCK
        and (
            path.name.startswith(LOCK.name + ".")
            or path.suffix in {".tmp", ".partial"}
            or ".tmp" in path.name
            or ".partial" in path.name
        )
    ]


def build_accumulation_transcript(path: Path) -> Path:
    """Build a verifier transcript exercising accumulation and revision replacement."""
    approved = approved_revision(TRANSCRIPT)
    older = stale_revision(MIRROR)
    body = (
        "# Verifier accumulation transcript\n"
        "PROPOSAL: allow route-embeddings-preview.jsonl for public-synonym\n"
        f"<!-- FINAL_RATIFIED:route=offline-qa revision={older} "
        "files=synonym-expansion-eval.jsonl -->\n"
        f"<!-- FINAL_RATIFIED:route=public-synonym revision={older} "
        "files=synonym-expansion-train.jsonl -->\n"
        "PROPOSAL (ignored): rollback public route to stale revision\n"
        f"<!-- FINAL_RATIFIED:route=public-synonym revision={approved} "
        "files=synonym-expansion-dev.jsonl -->\n"
        f"<!-- FINAL_RATIFIED:route=public-synonym "
        "forbidden=rejected-adult-filter.jsonl,route-embeddings-preview.jsonl -->\n"
        "PROPOSAL: permit rejected-adult-filter.jsonl on public route\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def expected_policy_for_accumulation() -> RoutePolicy:
    approved = approved_revision(TRANSCRIPT)
    return RoutePolicy(
        route_id=PUBLIC_ROUTE,
        revision=approved,
        files=("synonym-expansion-dev.jsonl", "synonym-expansion-train.jsonl"),
        forbidden=("rejected-adult-filter.jsonl", "route-embeddings-preview.jsonl"),
    )


def start_app_jar(app_home: Path, env: dict | None = None) -> subprocess.Popen:
    jar = get_boot_jar() if app_home == APP else next(app_home.glob("build/libs/*.jar"))
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.Popen(
        ["java", "-jar", str(jar)],
        cwd=app_home,
        env=merged,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def query_synonyms(term: str, port: int = 8080) -> tuple[int, dict]:
    body_path = Path(tempfile.gettempdir()) / ("synonym" + "-body.json")
    proc = subprocess.run(
        [
            shutil.which("curl") or "/usr/bin/curl",
            "-sS",
            "-o",
            str(body_path),
            "-w",
            "%{http_code}",
            f"http://127.0.0.1:{port}/v1/terms/{term}/synonyms",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    status = int(proc.stdout.strip())
    body = json.loads(body_path.read_text(encoding="utf-8"))
    return status, body


def stop_process(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def wait_for_health(port: int = 8080, timeout: float = 60.0) -> None:
    curl_bin = shutil.which("curl") or "/usr/bin/curl"
    deadline = time.time() + timeout
    while time.time() < deadline:
        proc = subprocess.run(
            [curl_bin, "-fsS", f"http://127.0.0.1:{port}/health"],
            capture_output=True,
            check=False,
        )
        if not proc.returncode:
            return
        time.sleep(0.5)
    raise TimeoutError(f"service not healthy on port {port}")


def _load_schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def run_gradle(
    *args: str,
    env: dict | None = None,
    cwd: Path = APP,
    rerun_tasks: bool = False,
) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    gradle_args = ["./gradlew", "--offline"]
    if rerun_tasks:
        gradle_args.append("--rerun-tasks")
    return subprocess.run(
        [*gradle_args, *args],
        cwd=cwd,
        env=merged,
        text=True,
        capture_output=True,
        check=False,
    )


_BOOT_JAR: Path | None = None


def get_boot_jar() -> Path:
    """Build the runtime jar once per verifier session after any agent edits."""
    global _BOOT_JAR
    if _BOOT_JAR is None:
        _require_ok(run_gradle("bootJar"), "bootJar")
        _BOOT_JAR = next(APP.glob("build/libs/*.jar"))
    return _BOOT_JAR


def _env_needs_rerun(env: dict | None) -> bool:
    if not env:
        return False
    return any(key in env for key in ("HF_TRANSCRIPT", "HF_MIRROR_ROOT", "HF_ASSET_LOCK", "TARGET_ROUTE"))


def _update_lock(env: dict | None = None) -> subprocess.CompletedProcess:
    return run_gradle("updateHfAssetLock", env=env, rerun_tasks=_env_needs_rerun(env))


def _validate_lock(env: dict | None = None) -> subprocess.CompletedProcess:
    return run_gradle("validateHfAssetLock", env=env, rerun_tasks=_env_needs_rerun(env))


def _read_lock() -> dict:
    return json.loads(LOCK.read_text(encoding="utf-8"))


def _require_ok(result: subprocess.CompletedProcess, label: str = "command") -> None:
    if result.returncode:
        raise AssertionError(f"{label} failed: {result.stderr}")


def _update_lock_ok(env: dict | None = None) -> dict:
    result = _update_lock(env=env)
    _require_ok(result, "updateHfAssetLock")
    return _read_lock()


def _validate_lock_ok(env: dict | None = None) -> None:
    _require_ok(_validate_lock(env=env), "validateHfAssetLock")


def _assert_schema(lock: dict) -> None:
    schema = _load_schema()
    required = schema.get("required", [])
    for key in required:
        assert key in lock, key


class TestAssetLockGeneration:
    """Lock generation and schema validation."""

    def test_update_lock_creates_schema_valid_json(self, lock_backup) -> None:
        """Running updateHfAssetLock must emit schema-valid lock JSON with required fields."""
        lock = _update_lock_ok()
        _assert_schema(lock)

    def test_update_lock_is_idempotent(self, lock_backup) -> None:
        """Repeated lock updates with unchanged inputs must produce equivalent canonical JSON."""
        first = canonicalize(_update_lock_ok())
        second = canonicalize(_update_lock_ok())
        assert first == second

    def test_lock_contains_current_revision_and_repository(self, lock_backup) -> None:
        """Lock must pin the transcript-approved repository and revision."""
        policy = load_policy(TRANSCRIPT)
        lock = _update_lock_ok()
        assert lock["repository"] == HF_REPO
        assert lock["revision"] == policy.revision

    def test_lock_checksums_match_local_file_bytes(self, lock_backup) -> None:
        """Per-file checksums and byte sizes must match local mirror bytes."""
        lock = _update_lock_ok()
        rev_dir = revision_dir(MIRROR, lock["revision"])
        for entry in route_files(lock, PUBLIC_ROUTE):
            path = rev_dir / "files" / entry["path"]
            checksum, byte_size = file_checksum(path)
            assert checksum == entry["sha256"]
            assert byte_size == entry["bytes"]

    def test_lock_includes_gradle_digest(self, lock_backup) -> None:
        """Asset lock must record the Gradle dependency-lock digest."""
        lock = _update_lock_ok()
        expected = gradle_lock_digest(APP)
        assert lock["gradle_lock_digest"] == expected

    def test_transcript_digest_matches_bytes(self, lock_backup) -> None:
        """Transcript digest in the lock must match the transcript file bytes."""
        lock = _update_lock_ok()
        assert lock["transcript_digest"] == transcript_digest(TRANSCRIPT)

    def test_source_metadata_digest_matches_canonical_metadata(self, lock_backup) -> None:
        """Metadata digest must independently match canonical sorted-key metadata JSON."""
        lock = _update_lock_ok()
        expected = metadata_digest(MIRROR, lock["revision"])
        assert lock["source_metadata_digest"] == expected


class TestValidationFailures:
    """Negative validation paths for stale or malformed locks."""

    def test_stale_revision_lock_fails_validation(self, lock_backup) -> None:
        """Validation must reject a lock pointing at a stale dataset revision."""
        lock = _update_lock_ok()
        lock["revision"] = stale_revision(MIRROR)
        LOCK.write_text(json.dumps(lock, indent=2), encoding="utf-8")
        result = _validate_lock()
        assert result.returncode != 0

    def test_forbidden_route_file_in_lock_fails_validation(self, lock_backup) -> None:
        """Locks that include forbidden public-route files must fail validation."""
        lock = _update_lock_ok()
        forbidden = forbidden_files(TRANSCRIPT)[0]
        for route in lock["routes"]:
            if route["route_id"] == PUBLIC_ROUTE:
                route["files"].append({"path": forbidden, "sha256": "c" * 64, "bytes": 1})
        LOCK.write_text(json.dumps(lock, indent=2), encoding="utf-8")
        assert _validate_lock().returncode != 0

    def test_missing_required_file_fails_validation(self, lock_backup) -> None:
        """Omitting a required public-route file from the lock must fail validation."""
        lock = _update_lock_ok()
        required = load_policy(TRANSCRIPT).files[-1]
        for route in lock["routes"]:
            if route["route_id"] == PUBLIC_ROUTE:
                route["files"] = [f for f in route["files"] if f["path"] != required]
        LOCK.write_text(json.dumps(lock, indent=2), encoding="utf-8")
        assert _validate_lock().returncode != 0

    def test_gradle_lock_digest_mismatch_fails_validation(self, lock_backup) -> None:
        """Asset lock must disagree with validation when Gradle lock digest is wrong."""
        lock = _update_lock_ok()
        lock["gradle_lock_digest"] = "deadbeef" * 8
        LOCK.write_text(json.dumps(lock, indent=2), encoding="utf-8")
        assert _validate_lock().returncode != 0

    def test_gradle_check_depends_on_asset_validation(self, lock_backup) -> None:
        """Gradle check must fail when asset lock validation would fail."""
        lock = _update_lock_ok()
        lock["revision"] = stale_revision(MIRROR)
        LOCK.write_text(json.dumps(lock, indent=2), encoding="utf-8")
        result = run_gradle("check")
        assert result.returncode != 0


class TestTranscriptPolicy:
    """Long-context route and file policy enforcement."""

    def test_public_route_files_match_transcript_policy(self, lock_backup) -> None:
        """Public synonym route must include exactly the transcript-permitted files."""
        policy = load_policy(TRANSCRIPT)
        _update_lock_ok()
        lock = _read_lock()
        paths = sorted(f["path"] for f in route_files(lock, PUBLIC_ROUTE))
        assert paths == list(policy.files)

    def test_generated_transcript_policy_prevents_first_match_grep(self, lock_backup, tmp_path: Path) -> None:
        """Final ratified transcript markers must override earlier superseded proposals."""
        policy = load_policy(TRANSCRIPT)
        variant = tmp_path / ("variant" + "-transcript.md")
        body = TRANSCRIPT.read_text(encoding="utf-8")
        forbidden = forbidden_files(TRANSCRIPT)[0]
        body += (
            f"\nPROPOSAL (superseded): allow {forbidden} for {PUBLIC_ROUTE}\n"
            f"<!-- FINAL_RATIFIED:route={PUBLIC_ROUTE} revision={policy.revision} "
            f"files={','.join(policy.files)} forbidden={forbidden} -->\n"
        )
        variant.write_text(body, encoding="utf-8")
        result = _update_lock(env={"HF_TRANSCRIPT": str(variant)})
        _require_ok(result, "updateHfAssetLock with variant transcript")
        lock = _read_lock()
        paths = {f["path"] for f in route_files(lock, PUBLIC_ROUTE)}
        assert forbidden not in paths
        assert set(policy.files).issubset(paths)


class TestApiBehavior:
    """Runtime API and startup enforcement."""

    def test_existing_api_response_shape_is_preserved(self, lock_backup, session_boot_jar) -> None:
        """Synonym endpoint must preserve term and synonyms response fields."""
        _ = session_boot_jar
        sample_term = json.loads(
            (revision_dir(MIRROR, approved_revision(TRANSCRIPT)) / "files" / "synonym-expansion-train.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )["term"]
        proc = start_app_jar(APP)
        try:
            wait_for_health()
            status, body = query_synonyms(sample_term)
            assert status == 200
            assert "term" in body and "synonyms" in body
            assert body["term"] == sample_term
            assert isinstance(body["synonyms"], list) and body["synonyms"]
        finally:
            stop_process(proc)

    def test_forbidden_file_term_is_not_returned(self, lock_backup, session_boot_jar) -> None:
        """Terms present only in forbidden files must not be served on the public route."""
        _ = session_boot_jar
        proc = start_app_jar(APP)
        try:
            wait_for_health()
            term = forbidden_only_term(MIRROR)
            status, body = query_synonyms(term)
            assert status == 404
            assert body["error"]["code"] == "term_not_found"
        finally:
            stop_process(proc)

    def test_eval_only_file_is_excluded_from_public_route(self, lock_backup, session_boot_jar) -> None:
        """Evaluation-only synonym aliases must not appear on the public synonym route."""
        _ = session_boot_jar
        sample_term = json.loads(
            (revision_dir(MIRROR, approved_revision(TRANSCRIPT)) / "files" / "synonym-expansion-train.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )["term"]
        proc = start_app_jar(APP)
        try:
            wait_for_health()
            status, body = query_synonyms(sample_term)
            assert status == 200
            alias = eval_only_alias(MIRROR)
            values = [row.get("value", "") for row in body["synonyms"]]
            assert alias not in values
        finally:
            stop_process(proc)

    def test_startup_fails_after_post_check_tampering(self, lock_backup, session_boot_jar) -> None:
        """Runtime startup must reject a tampered asset lock after a successful update."""
        _update_lock_ok()
        _ = session_boot_jar
        lock = _read_lock()
        lock["revision"] = stale_revision(MIRROR)
        LOCK.write_text(json.dumps(lock, indent=2), encoding="utf-8")
        proc = start_app_jar(APP)
        try:
            proc.wait(timeout=30)
            assert proc.returncode != 0
        finally:
            stop_process(proc)


class TestOfflineAndRobustness:
    """Offline execution and anti-hardcoding checks."""

    def test_network_tools_are_not_invoked_at_runtime(self, lock_backup, tmp_path: Path) -> None:
        """Lock update and check must succeed without calling network download tools."""
        curl_bin = shutil.which("curl") or "/usr/bin/curl"
        trap = tmp_path / Path(curl_bin).name
        trap.write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
        trap.chmod(0o755)
        env = {"PATH": f"{tmp_path}:{os.environ.get('PATH', '')}"}
        _update_lock_ok(env=env)
        _require_ok(run_gradle("check", env=env), "check")

    def test_generated_mirror_revision_prevents_hardcoding(self, lock_backup, tmp_path: Path) -> None:
        """Lock generation must work for verifier-generated mirror revisions."""
        gen_root = tmp_path / ("generated" + "-hf-mirror")
        src_rev = revision_dir(MIRROR, approved_revision(TRANSCRIPT))
        new_rev = f"generated{GENERATED_SEED:032x}"[:40]
        dst_rev = gen_root / HF_REPO / "fineweb-edu-score-2" / "revisions" / new_rev
        shutil.copytree(src_rev, dst_rev)
        meta = json.loads((dst_rev / "metadata.json").read_text(encoding="utf-8"))
        meta["revision"] = new_rev
        (dst_rev / "metadata.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        variant = tmp_path / ("variant" + "-transcript.md")
        policy = load_policy(TRANSCRIPT)
        variant.write_text(
            TRANSCRIPT.read_text(encoding="utf-8")
            + f"\n<!-- FINAL_RATIFIED:route={PUBLIC_ROUTE} revision={new_rev} files={','.join(policy.files)} -->\n",
            encoding="utf-8",
        )
        env = {"HF_MIRROR_ROOT": str(gen_root), "HF_TRANSCRIPT": str(variant)}
        lock = _update_lock_ok(env=env)
        assert lock["revision"] == new_rev

    def test_malformed_lock_rejected(self, lock_backup) -> None:
        """Malformed JSON locks must fail validation."""
        LOCK.write_text("{not-json", encoding="utf-8")
        assert _validate_lock().returncode != 0


class TestReadOnlyValidation:
    """Validation must observe locks without regeneration or side effects."""

    def test_validate_rejects_tampered_lock_without_modifying_bytes(self, lock_backup) -> None:
        """validateHfAssetLock must fail on tampered locks and leave every input unchanged."""
        _update_lock_ok()
        before_inputs = source_input_fingerprint()

        lock = _read_lock()
        lock["gradle_lock_digest"] = "0" * 64
        LOCK.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tampered_bytes = LOCK.read_bytes()

        result = _validate_lock()
        assert result.returncode != 0
        assert LOCK.read_bytes() == tampered_bytes
        assert source_input_fingerprint() == before_inputs
        assert lock_abandoned_siblings() == []

        second = _validate_lock()
        assert second.returncode != 0
        assert LOCK.read_bytes() == tampered_bytes


class TestGradleLifecycle:
    """Explicit update repairs locks; validation and check reject without rewriting."""

    def test_check_rejects_tampered_lock_until_explicit_update(self, lock_backup) -> None:
        """check must fail on tampered locks without repair; update must restore validity."""
        _update_lock_ok()

        lock = _read_lock()
        lock["source_metadata_digest"] = "f" * 64
        LOCK.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tampered_bytes = LOCK.read_bytes()

        assert _validate_lock().returncode != 0
        assert LOCK.read_bytes() == tampered_bytes

        check_result = run_gradle("check")
        assert check_result.returncode != 0
        assert LOCK.read_bytes() == tampered_bytes

        _require_ok(_update_lock(), "updateHfAssetLock")
        assert LOCK.read_bytes() != tampered_bytes
        _validate_lock_ok()
        _require_ok(run_gradle("check"), "check after repair")


class TestAtomicLockUpdate:
    """Failed regeneration must preserve the previous lock atomically."""

    def test_failed_update_preserves_previous_lock(self, lock_backup, tmp_path: Path) -> None:
        """updateHfAssetLock must not publish partial locks when generation fails."""
        _update_lock_ok()
        original_bytes = LOCK.read_bytes()
        policy = load_policy(TRANSCRIPT)
        asset = (
            revision_dir(MIRROR, policy.revision)
            / "files"
            / policy.files[0]
        )
        backup = tmp_path / hashlib.sha256(str(ACCUM_SEED).encode()).hexdigest()[:8]
        shutil.move(asset, backup)
        try:
            result = _update_lock()
            assert result.returncode != 0
            assert LOCK.read_bytes() == original_bytes
            json.loads(LOCK.read_text(encoding="utf-8"))
            assert lock_abandoned_siblings() == []
        finally:
            if backup.exists():
                shutil.move(backup, asset)

        _update_lock_ok()
        assert json.loads(LOCK.read_text(encoding="utf-8"))


class TestDynamicGradleLockDigest:
    """Gradle digest must cover the complete current dependency-lock set."""

    def test_dynamic_lockfile_changes_digest_with_crlf_normalization(self, lock_backup, tmp_path: Path) -> None:
        """Adding or changing lockfiles must update the digest; CRLF bodies must normalize."""
        baseline = _update_lock_ok()
        baseline_digest = baseline["gradle_lock_digest"]
        extra = GRADLE_LOCK_DIR / verifier_lockfile_name(ACCUM_SEED)
        content = "verifier-only dependency pin\n"
        extra.write_text(content, encoding="utf-8")
        try:
            changed = _update_lock_ok()
            expected = gradle_lock_digest(APP)
            assert changed["gradle_lock_digest"] == expected
            assert changed["gradle_lock_digest"] != baseline_digest

            extra.write_bytes(content.replace("\n", "\r\n").encode("utf-8"))
            same = _update_lock_ok()
            assert same["gradle_lock_digest"] == expected

            extra.write_text(content + "# mutation\n", encoding="utf-8")
            mutated = _update_lock_ok()
            assert mutated["gradle_lock_digest"] != expected
            assert mutated["gradle_lock_digest"] == gradle_lock_digest(APP)
        finally:
            if extra.exists():
                extra.unlink()

        restored = _update_lock_ok()
        assert restored["gradle_lock_digest"] == baseline_digest


class TestCanonicalMetadataEquivalence:
    """Metadata digest must be canonical over JSON semantics, not formatting."""

    def test_formatting_equivalence_and_value_mutation(self, lock_backup) -> None:
        """Harmless metadata formatting must not change digest; semantic edits must."""
        lock = _update_lock_ok()
        policy = load_policy(TRANSCRIPT)
        meta_path = revision_dir(MIRROR, policy.revision) / "metadata.json"
        original_text = meta_path.read_text(encoding="utf-8")
        payload = json.loads(original_text)
        try:
            baseline_digest = lock["source_metadata_digest"]

            reshaped = json.dumps(
                dict(reversed(list(payload.items()))),
                indent=4,
                sort_keys=False,
            )
            meta_path.write_text(reshaped + "\n\n", encoding="utf-8")
            unchanged = _update_lock_ok()
            assert unchanged["source_metadata_digest"] == baseline_digest

            mutated = dict(payload)
            mutated["revision"] = mutated.get("revision", "") + "-mutated"
            meta_path.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
            changed = _update_lock_ok()
            expected = metadata_digest(MIRROR, policy.revision)
            assert changed["source_metadata_digest"] == expected
            assert changed["source_metadata_digest"] != baseline_digest
        finally:
            meta_path.write_text(original_text, encoding="utf-8")
        _update_lock_ok()


class TestTranscriptAccumulation:
    """Generated transcript variants must enforce latest revision and accumulation."""

    def test_generated_transcript_accumulates_files_and_latest_revision(
        self, lock_backup, tmp_path: Path, session_boot_jar
    ) -> None:
        """Lock generation must honor accumulated files, forbidden sets, and latest revision."""
        _ = session_boot_jar
        variant = build_accumulation_transcript(tmp_path / f"accum-{ACCUM_SEED}.md")
        env = {"HF_TRANSCRIPT": str(variant)}
        expected = expected_policy_for_accumulation()

        lock = _update_lock_ok(env=env)
        assert lock["revision"] == expected.revision
        assert lock["transcript_digest"] == transcript_digest(variant)

        paths = sorted(f["path"] for f in route_files(lock, PUBLIC_ROUTE))
        assert paths == list(expected.files)
        for forbidden in expected.forbidden:
            assert forbidden not in paths

        _validate_lock_ok(env=env)

        proc = start_app_jar(APP, env=env)
        try:
            wait_for_health()
            sample_term = json.loads(
                (
                    revision_dir(MIRROR, expected.revision)
                    / "files"
                    / "synonym-expansion-train.jsonl"
                )
                .read_text(encoding="utf-8")
                .splitlines()[0]
            )["term"]
            status, body = query_synonyms(sample_term)
            assert status == 200
            assert body["term"] == sample_term
        finally:
            stop_process(proc)


class TestCrossComponentProvenance:
    """Gradle, standalone, and startup validation must share provenance semantics."""

    @pytest.mark.parametrize(
        "mutation_kind",
        [
            "gradle_lockfile",
            "asset_bytes",
        ],
    )
    def test_provenance_mutation_rejected_until_explicit_update(
        self, lock_backup, tmp_path: Path, mutation_kind: str, session_boot_jar
    ) -> None:
        """Each provenance input must be enforced consistently across validation paths."""
        _ = session_boot_jar
        _update_lock_ok()
        policy = load_policy(TRANSCRIPT)
        rev_dir = revision_dir(MIRROR, policy.revision)
        extra = GRADLE_LOCK_DIR / verifier_lockfile_name(ACCUM_SEED + 17)
        asset_path = rev_dir / "files" / "synonym-expansion-train.jsonl"
        asset_backup = asset_path.read_bytes()

        try:
            if mutation_kind == "gradle_lockfile":
                extra.write_text("cross-component gradle pin\n", encoding="utf-8")
            elif mutation_kind == "asset_bytes":
                asset_path.write_bytes(asset_backup + b"\n")

            assert _validate_lock().returncode != 0
            assert run_gradle("check").returncode != 0

            proc = start_app_jar(APP)
            try:
                proc.wait(timeout=30)
                assert proc.returncode != 0
            finally:
                stop_process(proc)

            _update_lock_ok()
            _validate_lock_ok()
            _require_ok(run_gradle("check"), "check after repair")
        finally:
            if extra.exists():
                extra.unlink()
            asset_path.write_bytes(asset_backup)
        _update_lock_ok()


@pytest.fixture(scope="session")
def session_boot_jar() -> Path:
    """Build the runtime jar once per verifier session instead of per API test."""
    return get_boot_jar()


@pytest.fixture()
def lock_backup():
    original = LOCK.read_text(encoding="utf-8") if LOCK.exists() else None
    yield
    if original is not None:
        LOCK.write_text(original, encoding="utf-8")
