"""Behavioral verification for the Prefect PFSEAL2 DuckDB worker."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


APP = Path(os.environ.get("PFSEAL_APP_ROOT", "/app"))
WORKER = APP / "bin" / "pfseal-worker"
SQL_DIR = APP / "sql"
FIXTURES = Path(__file__).with_name("fixtures")
AT = "2026-06-18T14:25:36.000Z"
SECRET = "never-print-this-prefect-secret"
WITNESS_IDS = ("alpha", "bravo", "charlie")
CONTRACT_DIGEST = "6961dfa79f6d523ff7b0cfe85d81e3e48d6317a8731b3286a33967107ad5bab6"
FIXTURE_DIGEST = "a3c7b1e8410d3815b84d6270ce19936ace675f10a7c0bdc4dec331f39fce7c53"


def tree_digest(paths: list[Path], base: Path) -> str:
    """Hash selected production inputs with names and file boundaries."""
    digest = hashlib.sha256()
    for path in sorted(paths):
        relative = path.relative_to(base).as_posix().encode()
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def contract_files() -> list[Path]:
    """Return immutable files that define the agent-visible production contract."""
    roots = [APP / name for name in ("docs", "sql", "config", "examples")]
    files = [path for root in roots for path in root.rglob("*") if path.is_file()]
    return files + [APP / "package.json", APP / "package-lock.json"]


def new_database(path: Path) -> duckdb.DuckDBPyConnection:
    """Create one isolated database from the shipped production DDL."""
    connection = duckdb.connect(str(path))
    for sql_path in sorted(SQL_DIR.glob("*.sql")):
        connection.execute(sql_path.read_text())
    return connection


def canonical_json(value: Any) -> bytes:
    """Encode the task's restricted canonical JSON form independently."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def deterministic_bytes(label: str, length: int = 32) -> bytes:
    """Produce deterministic fixture material without sharing production code."""
    output = b""
    counter = 0
    while len(output) < length:
        output += hashlib.sha256(f"{label}:{counter}".encode()).digest()
        counter += 1
    return output[:length]


def shares_for(label: str) -> tuple[bytes, bytes, bytes]:
    """Construct three shares with a stable, nontrivial XOR result."""
    return tuple(deterministic_bytes(f"{label}:share:{index}") for index in range(3))


def witness_private_keys(deployment_id: str) -> dict[str, Ed25519PrivateKey]:
    """Derive deterministic independent Ed25519 fixture witnesses."""
    return {
        witness_id: Ed25519PrivateKey.from_private_bytes(
            deterministic_bytes(f"{deployment_id}:witness:{witness_id}")
        )
        for witness_id in WITNESS_IDS
    }


def install_witnesses(
    connection: duckdb.DuckDBPyConnection,
    deployment_id: str,
    valid_from: int = 1,
    valid_through: int = 100,
) -> dict[str, Ed25519PrivateKey]:
    """Install three revision-scoped Ed25519 public trust roots."""
    private_keys = witness_private_keys(deployment_id)
    rows = []
    for witness_id in WITNESS_IDS:
        public_der = (
            private_keys[witness_id]
            .public_key()
            .public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        rows.append(
            (
                deployment_id,
                witness_id,
                base64.b64encode(public_der).decode(),
                valid_from,
                valid_through,
                None,
            )
        )
    connection.executemany(
        "INSERT INTO pfseal_key_witnesses VALUES (?, ?, ?, ?, ?, ?)", rows
    )
    return private_keys


def key_attestation(
    deployment_id: str,
    version: int,
    revision: int,
    workspace_id: str,
    work_pool: str,
    shares: tuple[bytes, bytes, bytes],
    private_keys: dict[str, Ed25519PrivateKey],
    signers: tuple[str, ...] = ("alpha", "bravo"),
) -> str:
    """Sign the canonical revision-bound key-set statement with a quorum."""
    statement = {
        "deploymentId": deployment_id,
        "keyVersion": version,
        "revision": revision,
        "shareDigests": [hashlib.sha256(share).hexdigest() for share in shares],
        "workPool": work_pool,
        "workspaceId": workspace_id,
    }
    signed = b"PFSEAL2-KEYSET-V1\n" + canonical_json(statement)
    signatures = [
        {
            "signature": base64.b64encode(private_keys[witness].sign(signed)).decode(),
            "witnessId": witness,
        }
        for witness in sorted(signers)
    ]
    return canonical_json({"revision": revision, "signatures": signatures}).decode()


def key_material(
    deployment_id: str,
    version: int,
    workspace_id: str,
    work_pool: str,
    shares: tuple[bytes, bytes, bytes],
) -> tuple[bytes, bytes]:
    """Apply the documented HKDF schedule for fixture generation."""
    ikm = bytes(left ^ middle ^ right for left, middle, right in zip(*shares))
    salt = hashlib.sha256(
        b"PFSEAL2\0" + workspace_id.encode() + b"\0" + work_pool.encode()
    ).digest()
    info = f"prefect-seal/deployment/{deployment_id}/key/{version}".encode()
    output = HKDF(algorithm=hashes.SHA256(), length=64, salt=salt, info=info).derive(
        ikm
    )
    return output[:32], output[32:]


def metadata_rows(
    deployment_id: str,
    revision: int,
    version: int,
    workspace_id: str,
    work_pool: str,
    shares: tuple[bytes, bytes, bytes],
    include_identity: bool = False,
    successor: str | None = None,
    witnesses: dict[str, Ed25519PrivateKey] | None = None,
) -> list[tuple[str, int, str, str]]:
    """Encode key shares exactly as Prefect stores them."""
    rows: list[tuple[str, int, str, str]] = []
    if include_identity:
        rows.extend(
            [
                (deployment_id, revision, "prefect.workspace-id", workspace_id),
                (deployment_id, revision, "prefect.work-pool", work_pool),
            ]
        )
    prefix = f"pfseal.key.v{version}."
    rows.extend(
        [
            (deployment_id, revision, prefix + "share0", "hex:" + shares[0].hex()),
            (
                deployment_id,
                revision,
                prefix + "share1",
                "b64:" + base64.b64encode(shares[1]).decode(),
            ),
            (
                deployment_id,
                revision,
                prefix + "share2",
                "b64url:" + base64.urlsafe_b64encode(shares[2]).decode().rstrip("="),
            ),
        ]
    )
    if successor is not None:
        rows.append((deployment_id, revision, prefix + "successor", successor))
    if witnesses is not None:
        rows.append(
            (
                deployment_id,
                revision,
                prefix + "attestation",
                key_attestation(
                    deployment_id,
                    version,
                    revision,
                    workspace_id,
                    work_pool,
                    shares,
                    witnesses,
                ),
            )
        )
    return rows


def lineage_proof(
    deployment_id: str,
    version: int,
    active: int,
    revision: int,
    workspace_id: str,
    work_pool: str,
    shares: tuple[bytes, bytes, bytes],
) -> str:
    """Create an authenticated old-to-active key transition fixture."""
    _, mac_key = key_material(deployment_id, version, workspace_id, work_pool, shares)
    message = (
        b"PFSEAL2-ROTATE\0"
        + deployment_id.encode()
        + b"\0"
        + str(version).encode()
        + b"\0"
        + str(active).encode()
        + b"\0"
        + str(revision).encode()
    )
    return f"v{active}:" + hmac.new(mac_key, message, hashlib.sha256).hexdigest()


def install_deployment(
    connection: duckdb.DuckDBPyConnection,
    deployment_id: str,
    active: int,
    minimum: int,
    versions: list[int],
    revision: int = 3,
    workspace_id: str | None = None,
    work_pool: str | None = None,
    valid_from: int = 1,
    valid_through: int = 100,
) -> dict[int, tuple[bytes, bytes, bytes]]:
    """Insert a deployment policy and its effective split-key metadata."""
    workspace_id = workspace_id or f"ws-{deployment_id}"
    work_pool = work_pool or f"pool-{deployment_id}"
    connection.execute(
        "INSERT INTO prefect_deployments VALUES (?, ?, ?, ?, ?)",
        [deployment_id, active, minimum, valid_from, valid_through],
    )
    witnesses = install_witnesses(
        connection, deployment_id, valid_from=valid_from, valid_through=valid_through
    )
    key_shares = {
        version: shares_for(f"{deployment_id}:v{version}") for version in versions
    }
    rows: list[tuple[str, int, str, str]] = []
    for index, version in enumerate(versions):
        successor = None
        if minimum <= version < active:
            successor = lineage_proof(
                deployment_id,
                version,
                active,
                revision,
                workspace_id,
                work_pool,
                key_shares[version],
            )
        rows.extend(
            metadata_rows(
                deployment_id,
                revision,
                version,
                workspace_id,
                work_pool,
                key_shares[version],
                include_identity=index == 0,
                successor=successor,
                witnesses=witnesses,
            )
        )
    connection.executemany(
        "INSERT INTO prefect_deployment_metadata VALUES (?, ?, ?, ?)", rows
    )
    return key_shares


def payload(
    deployment_id: str,
    secret_name: str,
    value: str = SECRET,
    **updates: Any,
) -> dict[str, Any]:
    """Return a valid decrypted payload, optionally adjusted for a test."""
    value_object: dict[str, Any] = {
        "deploymentId": deployment_id,
        "expiresAt": "2026-06-19T09:08:07.006Z",
        "issuedAt": "2026-06-17T09:08:07.006Z",
        "notBefore": "2026-06-18T00:00:00.000Z",
        "rotationCounter": 4,
        "secretName": secret_name,
        "value": value,
    }
    value_object.update(updates)
    return value_object


def seal(
    deployment_id: str,
    version: int,
    workspace_id: str,
    work_pool: str,
    shares: tuple[bytes, bytes, bytes],
    plaintext: bytes,
    nonce_label: str,
) -> tuple[str, dict[str, str]]:
    """Build an independent PFSEAL2 label and its expected audit hashes."""
    encryption_key, mac_key = key_material(
        deployment_id, version, workspace_id, work_pool, shares
    )
    nonce = deterministic_bytes(f"nonce:{nonce_label}", 12)
    core = (
        b"PFSEAL2"
        + b"\0"
        + version.to_bytes(2, "big")
        + nonce
        + len(plaintext).to_bytes(4, "big")
    )
    header_mac = hmac.new(mac_key, core, hashlib.sha256).digest()
    header = core + header_mac
    encrypted = AESGCM(encryption_key).encrypt(nonce, plaintext, header)
    envelope = header + encrypted
    return base64.b64encode(envelope).decode(), {
        "header_sha256": hashlib.sha256(header).hexdigest(),
        "plaintext_sha256": hashlib.sha256(plaintext).hexdigest(),
    }


def insert_image(
    connection: duckdb.DuckDBPyConnection,
    digest: str,
    encoded: str,
    extra_labels: dict[str, Any] | None = None,
) -> None:
    """Insert an OCI image record around one encrypted label."""
    labels = {
        "org.opencontainers.image.source": "prefect",
        "io.prefect.pfseal": encoded,
    }
    if extra_labels:
        labels.update(extra_labels)
    connection.execute(
        "INSERT INTO prefect_images VALUES (?, ?)",
        [digest, json.dumps(labels, separators=(",", ":"))],
    )


def chunked_labels(encoded: str, count: int = 3) -> dict[str, str]:
    """Split one envelope into an authenticated canonical OCI label transport."""
    width = (len(encoded) + count - 1) // count
    chunks = [encoded[index * width : (index + 1) * width] for index in range(count)]
    assert all(chunks)
    manifest = canonical_json(
        {
            "count": count,
            "sha256": hashlib.sha256(encoded.encode()).hexdigest(),
        }
    ).decode()
    labels = {"io.prefect.pfseal.manifest": manifest}
    labels.update(
        {
            f"io.prefect.pfseal.part.{index:03d}": chunk
            for index, chunk in enumerate(chunks)
        }
    )
    return labels


def insert_labels(
    connection: duckdb.DuckDBPyConnection, digest: str, labels: dict[str, Any]
) -> None:
    """Insert an image with an exact caller-provided OCI label object."""
    connection.execute(
        "INSERT INTO prefect_images VALUES (?, ?)",
        [digest, json.dumps(labels, separators=(",", ":"))],
    )


def insert_job(
    connection: duckdb.DuckDBPyConnection,
    job_id: int,
    deployment_id: str,
    digest: str,
    revision: int = 3,
    status: str = "pending",
    attempt_count: int = 0,
    lease_owner: str | None = None,
    lease_until: str | None = None,
) -> None:
    """Insert a queue row with explicit lease state."""
    connection.execute(
        """
        INSERT INTO prefect_secret_jobs (
          job_id, deployment_id, image_digest, metadata_revision, requested_at,
          status, attempt_count, lease_owner, lease_until
        ) VALUES (?, ?, ?, ?, CAST(? AS TIMESTAMP), ?, ?, ?, CAST(? AS TIMESTAMP))
        """,
        [
            job_id,
            deployment_id,
            digest,
            revision,
            "2026-06-18 13:00:00",
            status,
            attempt_count,
            lease_owner,
            lease_until,
        ],
    )


def run_worker(
    database: Path,
    *extra: str,
    worker_id: str = "verify-1",
    at: str = AT,
) -> subprocess.CompletedProcess[str]:
    """Run the public executable with deterministic common arguments."""
    return subprocess.run(
        [
            str(WORKER),
            "--db",
            str(database),
            "--worker-id",
            worker_id,
            *extra,
            "--at",
            at,
        ],
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def table_rows(
    connection: duckdb.DuckDBPyConnection,
    table: str,
    order: str = "job_id",
) -> list[dict[str, Any]]:
    """Read a result table as JSON-friendly dictionaries."""
    relation = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    names = [column[0] for column in relation.description]
    output = []
    for raw_row in relation.fetchall():
        row: dict[str, Any] = {}
        for name, item in zip(names, raw_row):
            if isinstance(item, datetime):
                row[name] = (
                    item.replace(tzinfo=timezone.utc)
                    .isoformat(timespec="milliseconds")
                    .replace("+00:00", "Z")
                )
            else:
                row[name] = item
        output.append(row)
    return output


def expected_audit_hash(row: dict[str, Any]) -> str:
    """Recompute one audit link independently from its persisted columns."""
    record = {
        "activeKeyVersion": row["active_key_version"],
        "auditSequence": row["audit_sequence"],
        "deploymentId": row["deployment_id"],
        "envelopeKeyVersion": row["envelope_key_version"],
        "headerSha256": row["header_sha256"],
        "imageDigest": row["image_digest"],
        "jobId": row["job_id"],
        "keyAttestationSha256": row["key_attestation_sha256"],
        "metadataRevision": row["metadata_revision"],
        "plaintextSha256": row["plaintext_sha256"],
        "previousAuditHash": row["previous_audit_hash"],
        "processedAt": row["processed_at"],
        "rotationCounter": row["rotation_counter"],
        "rotationDecision": row["rotation_decision"],
        "secretName": row["secret_name"],
        "workerId": row["worker_id"],
    }
    return hashlib.sha256(b"PFSEAL-AUDIT-V1\n" + canonical_json(record)).hexdigest()


def transparency_merkle_root(heads: dict[str, tuple[int, str]]) -> str:
    """Build the domain-separated global head tree without production code."""
    level = []
    for deployment_id, (sequence, audit_hash) in sorted(
        heads.items(), key=lambda item: item[0].encode()
    ):
        deployment_bytes = deployment_id.encode()
        leaf = (
            b"\x00"
            + len(deployment_bytes).to_bytes(2, "big")
            + deployment_bytes
            + sequence.to_bytes(8, "big")
            + bytes.fromhex(audit_hash)
        )
        level.append(hashlib.sha256(leaf).digest())
    assert level
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            hashlib.sha256(b"\x01" + level[index] + level[index + 1]).digest()
            for index in range(0, len(level), 2)
        ]
    return level[0].hex()


def bag_event_peaks(peaks: list[str | None]) -> str:
    """Bag event-MMR peaks from highest to lowest with the contract domain."""
    ordered = [bytes.fromhex(peak) for peak in reversed(peaks) if peak is not None]
    assert ordered
    root = ordered[0]
    for peak in ordered[1:]:
        root = hashlib.sha256(b"\x04" + root + peak).digest()
    return root.hex()


def append_event_frontier(
    prior_peaks: list[str | None],
    checkpoint_sequence: int,
    job_id: int,
    merkle_root: str,
    triggering_audit_hash: str,
) -> tuple[list[str | None], str]:
    """Append one independently encoded event leaf to a binary MMR frontier."""
    leaf = (
        b"\x02"
        + checkpoint_sequence.to_bytes(8, "big")
        + job_id.to_bytes(8, "big")
        + bytes.fromhex(merkle_root)
        + bytes.fromhex(triggering_audit_hash)
    )
    carry = hashlib.sha256(leaf).digest()
    peaks = list(prior_peaks)
    height = 0
    while height < len(peaks) and peaks[height] is not None:
        carry = hashlib.sha256(b"\x03" + bytes.fromhex(peaks[height]) + carry).digest()
        peaks[height] = None
        height += 1
    if height == len(peaks):
        peaks.append(carry.hex())
    else:
        peaks[height] = carry.hex()
    return peaks, bag_event_peaks(peaks)


def synthetic_event_frontier(sequence: int) -> tuple[str, str, str]:
    """Create a shape-valid deterministic prior frontier for anchor tests."""
    peaks: list[str | None] = []
    for height in range(sequence.bit_length()):
        if sequence & (1 << height):
            peaks.append(
                hashlib.sha256(f"frontier:{sequence}:{height}".encode()).hexdigest()
            )
        else:
            peaks.append(None)
    frontier_json = canonical_json(peaks).decode()
    return (
        frontier_json,
        hashlib.sha256(frontier_json.encode()).hexdigest(),
        bag_event_peaks(peaks),
    )


def insert_checkpoint_anchor(
    connection: duckdb.DuckDBPyConnection,
    sequence: int,
    job_id: int,
    checkpoint_hash: str,
    *,
    frontier_json: str | None = None,
    frontier_sha256: str | None = None,
    event_mmr_root: str | None = None,
) -> None:
    """Insert one explicit checkpoint anchor with an independently valid frontier."""
    valid_json, valid_sha256, valid_root = synthetic_event_frontier(sequence)
    connection.execute(
        """
        INSERT INTO pfseal_transparency_checkpoints (
          checkpoint_sequence, job_id, head_count, merkle_root,
          triggering_audit_hash, previous_checkpoint_hash,
          previous_event_mmr_root, event_mmr_root, frontier_json,
          frontier_sha256, checkpoint_hash, created_at
        ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, CAST(? AS TIMESTAMP))
        """,
        [
            sequence,
            job_id,
            "11" * 32,
            "22" * 32,
            "0" * 64,
            "0" * 64,
            event_mmr_root if event_mmr_root is not None else valid_root,
            frontier_json if frontier_json is not None else valid_json,
            frontier_sha256 if frontier_sha256 is not None else valid_sha256,
            checkpoint_hash,
            "2026-06-17 00:00:00",
        ],
    )


def expected_checkpoint_hash(row: dict[str, Any]) -> str:
    """Recompute one global checkpoint link from its persisted columns."""
    record = {
        "checkpointSequence": row["checkpoint_sequence"],
        "eventMmrRoot": row["event_mmr_root"],
        "frontierSha256": row["frontier_sha256"],
        "headCount": row["head_count"],
        "jobId": row["job_id"],
        "merkleRoot": row["merkle_root"],
        "previousCheckpointHash": row["previous_checkpoint_hash"],
        "previousEventMmrRoot": row["previous_event_mmr_root"],
        "processedAt": row["created_at"],
        "triggeringAuditHash": row["triggering_audit_hash"],
    }
    return hashlib.sha256(
        b"PFSEAL-CHECKPOINT-V1\n" + canonical_json(record)
    ).hexdigest()


def setup_one_valid_job(
    database: Path,
    deployment_id: str = "dep-one",
    job_id: int = 1,
    version: int = 1,
    active: int = 1,
    minimum: int = 1,
    secret_name: str = "ACCESS_TOKEN",
) -> tuple[duckdb.DuckDBPyConnection, dict[str, str]]:
    """Create a database containing one independently encrypted valid job."""
    connection = new_database(database)
    key_shares = install_deployment(
        connection, deployment_id, active, minimum, sorted({version, active})
    )
    workspace = f"ws-{deployment_id}"
    pool = f"pool-{deployment_id}"
    encoded, hashes_expected = seal(
        deployment_id,
        version,
        workspace,
        pool,
        key_shares[version],
        canonical_json(payload(deployment_id, secret_name)),
        f"{deployment_id}:{job_id}",
    )
    digest = f"sha256:{hashlib.sha256(encoded.encode()).hexdigest()}"
    insert_image(connection, digest, encoded)
    insert_job(connection, job_id, deployment_id, digest)
    attestation = connection.execute(
        "SELECT metadata_value FROM prefect_deployment_metadata "
        "WHERE deployment_id=? AND metadata_key=?",
        [deployment_id, f"pfseal.key.v{version}.attestation"],
    ).fetchone()[0]
    hashes_expected["key_attestation_sha256"] = hashlib.sha256(
        attestation.encode()
    ).hexdigest()
    return connection, hashes_expected


def test_authoritative_contract_and_golden_fixtures_are_unchanged() -> None:
    """Seal the production contracts and golden snapshots against shortcut edits."""
    assert tree_digest(contract_files(), APP) == CONTRACT_DIGEST
    fixture_files = [path for path in FIXTURES.rglob("*") if path.is_file()]
    assert tree_digest(fixture_files, FIXTURES) == FIXTURE_DIGEST


def test_help_and_invalid_cli_inputs_have_stable_public_boundaries(
    tmp_path: Path,
) -> None:
    """Verify help, usage errors, exit codes, and pre-open argument validation."""
    help_result = subprocess.run(
        [str(WORKER), "--help"], text=True, capture_output=True, check=False
    )
    assert help_result.returncode == 0
    assert help_result.stdout == (
        "Usage: pfseal-worker --db ABSOLUTE_PATH --worker-id ID "
        "[--once | --idle-limit N] [--poll-ms N] [--at RFC3339]\n"
    )
    assert help_result.stderr == ""

    bad_cases = [
        (["--db", "relative.db", "--worker-id", "w"], "--db must be an absolute path"),
        (
            ["--db", str(tmp_path / "x.db"), "--worker-id", "bad id"],
            "--worker-id is invalid",
        ),
        (
            ["--db", str(tmp_path / "x.db"), "--worker-id", "w", "--wat"],
            "unknown option --wat",
        ),
        (
            ["--help", "--db", str(tmp_path / "x.db"), "--worker-id", "w"],
            "unknown option --help",
        ),
        (
            [
                "--db",
                str(tmp_path / "x.db"),
                "--db",
                str(tmp_path / "y.db"),
                "--worker-id",
                "w",
            ],
            "duplicate --db",
        ),
        (
            [
                "--db",
                str(tmp_path / "x.db"),
                "--worker-id",
                "w",
                "--poll-ms",
                "9",
            ],
            "--poll-ms must be between 10 and 60000",
        ),
        (
            [
                "--db",
                str(tmp_path / "x.db"),
                "--worker-id",
                "w",
                "--idle-limit",
                "1001",
            ],
            "--idle-limit must be between 0 and 1000",
        ),
        (
            [
                "--db",
                str(tmp_path / "x.db"),
                "--worker-id",
                "w",
                "--at",
                "2026-06-18T14:25:36Z",
            ],
            "--at must be canonical UTC RFC3339 with milliseconds",
        ),
        (
            [
                "--db",
                str(tmp_path / "x.db"),
                "--worker-id",
                "w",
                "--once",
                "--idle-limit",
                "1",
            ],
            "--once cannot be combined with --idle-limit",
        ),
    ]
    for arguments, message in bad_cases:
        result = subprocess.run(
            [str(WORKER), *arguments], text=True, capture_output=True, check=False
        )
        assert result.returncode == 64
        assert result.stdout == ""
        assert result.stderr == f"pfseal-worker: {message}\n"
    assert not (tmp_path / "x.db").exists()

    default_time_database = tmp_path / "default-time.duckdb"
    connection = new_database(default_time_database)
    connection.close()
    default_time = subprocess.run(
        [
            str(WORKER),
            "--db",
            str(default_time_database),
            "--worker-id",
            "default-time",
            "--once",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert default_time.returncode == 0
    assert json.loads(default_time.stdout)["workerId"] == "default-time"
    assert default_time.stderr == ""


def test_empty_once_queue_emits_exact_snapshot_without_mutation(tmp_path: Path) -> None:
    """Verify an empty drain exits cleanly with the canonical zero summary."""
    database = tmp_path / "empty.duckdb"
    connection = new_database(database)
    connection.close()
    result = run_worker(database, "--once", worker_id="empty-worker")
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == (
        '{"workerId":"empty-worker","claimed":0,"succeeded":0,'
        '"failed":0,"rotations":0,"jobs":[]}\n'
    )
    connection = duckdb.connect(str(database))
    assert connection.execute(
        "SELECT count(*) FROM prefect_secret_jobs"
    ).fetchone() == (0,)
    assert connection.execute("SELECT count(*) FROM pfseal_audit").fetchone() == (0,)
    assert connection.execute(
        "SELECT count(*) FROM pfseal_transparency_checkpoints"
    ).fetchone() == (0,)
    connection.close()


def test_mixed_current_rotation_and_failure_match_golden_snapshots(
    tmp_path: Path,
) -> None:
    """Compare deterministic CLI, audit, and outbox results with golden fixtures."""
    database = tmp_path / "golden.duckdb"
    connection = new_database(database)
    alpha = install_deployment(connection, "alpha-deploy", 2, 1, [1, 2])
    beta = install_deployment(connection, "beta-deploy", 1, 1, [1])

    entries = [
        (41, "alpha-deploy", 2, "DATABASE_URL", alpha[2]),
        (7, "alpha-deploy", 1, "API_TOKEN", alpha[1]),
        (19, "beta-deploy", 1, "BETA_KEY", beta[1]),
    ]
    for job_id, deployment, version, name, selected_shares in entries:
        encoded, _ = seal(
            deployment,
            version,
            f"ws-{deployment}",
            f"pool-{deployment}",
            selected_shares,
            canonical_json(payload(deployment, name, value=f"{SECRET}-{job_id}")),
            f"golden:{job_id}",
        )
        if job_id == 19:
            raw = bytearray(base64.b64decode(encoded))
            raw[26] ^= 0x80
            encoded = base64.b64encode(raw).decode()
        digest = f"sha256:golden-{job_id}"
        insert_image(connection, digest, encoded)
        insert_job(connection, job_id, deployment, digest)
    connection.close()

    result = run_worker(database, "--once", worker_id="golden-worker")
    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout) == json.loads(
        (FIXTURES / "main_summary.json").read_text()
    )

    connection = duckdb.connect(str(database))
    assert table_rows(connection, "pfseal_audit") == json.loads(
        (FIXTURES / "main_audit.json").read_text()
    )
    assert table_rows(connection, "pfseal_rotation_outbox") == json.loads(
        (FIXTURES / "main_rotation.json").read_text()
    )
    assert table_rows(
        connection, "prefect_secret_state", "deployment_id, secret_name"
    ) == json.loads((FIXTURES / "main_state.json").read_text())
    assert table_rows(connection, "pfseal_audit_heads", "deployment_id") == json.loads(
        (FIXTURES / "main_heads.json").read_text()
    )
    assert table_rows(
        connection, "pfseal_transparency_checkpoints", "checkpoint_sequence"
    ) == json.loads((FIXTURES / "main_checkpoints.json").read_text())
    statuses = connection.execute(
        "SELECT job_id, status, failure_code, attempt_count "
        "FROM prefect_secret_jobs ORDER BY job_id"
    ).fetchall()
    assert statuses == [
        (7, "succeeded", None, 1),
        (19, "failed", "AUTH_HEADER", 1),
        (41, "succeeded", None, 1),
    ]
    assert SECRET not in result.stdout
    assert SECRET not in json.dumps(table_rows(connection, "pfseal_audit"))
    connection.close()


def test_job_revision_selects_historical_metadata_not_latest_rows(
    tmp_path: Path,
) -> None:
    """Verify per-key revision snapshots prevent latest-metadata key substitution."""
    database = tmp_path / "history.duckdb"
    connection = new_database(database)
    deployment = "history-deploy"
    connection.execute(
        "INSERT INTO prefect_deployments VALUES (?, 1, 1, 1, 50)", [deployment]
    )
    witnesses = install_witnesses(connection, deployment, valid_through=50)
    old_workspace = "workspace-before-rotation"
    old_pool = "pool-before-rotation"
    old_shares = shares_for("history:old")
    rows = metadata_rows(
        deployment,
        4,
        1,
        old_workspace,
        old_pool,
        old_shares,
        include_identity=True,
        witnesses=witnesses,
    )
    new_shares = shares_for("history:new")
    rows.extend(
        metadata_rows(
            deployment,
            9,
            1,
            "workspace-after-rotation",
            "pool-after-rotation",
            new_shares,
            include_identity=True,
            witnesses=witnesses,
        )
    )
    connection.executemany(
        "INSERT INTO prefect_deployment_metadata VALUES (?, ?, ?, ?)", rows
    )
    encoded, _ = seal(
        deployment,
        1,
        old_workspace,
        old_pool,
        old_shares,
        canonical_json(payload(deployment, "HISTORICAL_KEY")),
        "history",
    )
    insert_image(connection, "sha256:history", encoded)
    insert_job(connection, 88, deployment, "sha256:history", revision=6)
    connection.close()

    result = run_worker(database, "--once")
    assert result.returncode == 0
    assert json.loads(result.stdout)["jobs"] == [
        {"jobId": 88, "status": "succeeded", "decision": "current"}
    ]
    connection = duckdb.connect(str(database))
    assert connection.execute(
        "SELECT metadata_revision, secret_name FROM pfseal_audit"
    ).fetchall() == [(6, "HISTORICAL_KEY")]
    connection.close()


def test_expired_leases_are_reclaimed_and_terminal_or_live_jobs_are_ignored(
    tmp_path: Path,
) -> None:
    """Verify eligibility, attempt increments, terminal idempotence, and reruns."""
    database = tmp_path / "leases.duckdb"
    connection, _ = setup_one_valid_job(database, job_id=5)
    connection.execute(
        "UPDATE prefect_secret_jobs SET status='processing', attempt_count=2, "
        "lease_owner='old', lease_until=CAST(? AS TIMESTAMP) WHERE job_id=5",
        ["2026-06-18 14:25:35"],
    )
    encoded = connection.execute(
        "SELECT json_extract_string(image_annotations_json, '$.io.prefect.pfseal') "
        "FROM prefect_images"
    ).fetchone()[0]
    insert_image(connection, "sha256:live", encoded)
    insert_job(
        connection,
        6,
        "dep-one",
        "sha256:live",
        status="processing",
        attempt_count=4,
        lease_owner="live",
        lease_until="2026-06-18 14:26:00",
    )
    insert_image(connection, "sha256:terminal", encoded)
    insert_job(connection, 7, "dep-one", "sha256:terminal", status="succeeded")
    connection.close()

    first = run_worker(database, "--once")
    assert first.returncode == 0
    assert json.loads(first.stdout)["jobs"] == [
        {"jobId": 5, "status": "succeeded", "decision": "current"}
    ]
    second = run_worker(database, "--once")
    assert json.loads(second.stdout)["claimed"] == 0

    connection = duckdb.connect(str(database))
    rows = connection.execute(
        "SELECT job_id, status, attempt_count, lease_owner FROM prefect_secret_jobs "
        "ORDER BY job_id"
    ).fetchall()
    assert rows == [
        (5, "succeeded", 3, None),
        (6, "processing", 4, "live"),
        (7, "succeeded", 0, None),
    ]
    assert connection.execute("SELECT count(*) FROM pfseal_audit").fetchone() == (1,)
    connection.close()


def test_header_hmac_precedes_gcm_and_failure_is_atomic(tmp_path: Path) -> None:
    """Verify constant-time header authentication wins over a corrupt GCM tag."""
    database = tmp_path / "header.duckdb"
    connection, _ = setup_one_valid_job(database, job_id=10)
    labels = json.loads(
        connection.execute(
            "SELECT image_annotations_json FROM prefect_images"
        ).fetchone()[0]
    )
    raw = bytearray(base64.b64decode(labels["io.prefect.pfseal"]))
    raw[30] ^= 0x01
    raw[-1] ^= 0x01
    labels["io.prefect.pfseal"] = base64.b64encode(raw).decode()
    connection.execute(
        "UPDATE prefect_images SET image_annotations_json=?", [json.dumps(labels)]
    )
    connection.close()

    result = run_worker(database, "--once")
    assert result.returncode == 0
    assert json.loads(result.stdout)["jobs"] == [
        {"jobId": 10, "status": "failed", "error": "AUTH_HEADER"}
    ]
    connection = duckdb.connect(str(database))
    assert connection.execute("SELECT count(*) FROM pfseal_audit").fetchone() == (0,)
    assert connection.execute(
        "SELECT count(*) FROM pfseal_rotation_outbox"
    ).fetchone() == (0,)
    connection.close()


def test_gcm_authentication_failure_never_persists_plaintext_or_results(
    tmp_path: Path,
) -> None:
    """Verify valid-header tag failures produce AUTH_GCM and no result residue."""
    database = tmp_path / "gcm.duckdb"
    connection, _ = setup_one_valid_job(database, job_id=11)
    labels = json.loads(
        connection.execute(
            "SELECT image_annotations_json FROM prefect_images"
        ).fetchone()[0]
    )
    raw = bytearray(base64.b64decode(labels["io.prefect.pfseal"]))
    raw[-1] ^= 0x40
    labels["io.prefect.pfseal"] = base64.b64encode(raw).decode()
    connection.execute(
        "UPDATE prefect_images SET image_annotations_json=?", [json.dumps(labels)]
    )
    connection.close()

    result = run_worker(database, "--once")
    assert json.loads(result.stdout)["jobs"][0]["error"] == "AUTH_GCM"
    assert SECRET not in result.stdout
    connection = duckdb.connect(str(database))
    assert connection.execute("SELECT count(*) FROM pfseal_audit").fetchone() == (0,)
    assert connection.execute(
        "SELECT count(*) FROM pfseal_rotation_outbox"
    ).fetchone() == (0,)
    connection.close()


def test_malformed_image_annotations_and_envelopes_are_rejected_dynamically(
    tmp_path: Path,
) -> None:
    """Exercise canonical base64, framing, size, flags, and missing-image checks."""
    database = tmp_path / "format.duckdb"
    connection, _ = setup_one_valid_job(database, job_id=100)
    original_json = connection.execute(
        "SELECT image_annotations_json FROM prefect_images"
    ).fetchone()[0]
    original = json.loads(original_json)["io.prefect.pfseal"]
    connection.execute("DELETE FROM prefect_secret_jobs")
    connection.execute("DELETE FROM prefect_images")

    variants: list[tuple[int, str | None, str | None]] = []
    variants.append((101, "sha256:whitespace", original[:4] + "\n" + original[4:]))
    magic = bytearray(base64.b64decode(original))
    magic[0] = ord("X")
    variants.append((102, "sha256:magic", base64.b64encode(magic).decode()))
    flags = bytearray(base64.b64decode(original))
    flags[7] = 1
    variants.append((103, "sha256:flags", base64.b64encode(flags).decode()))
    trailing = base64.b64encode(base64.b64decode(original) + b"x").decode()
    variants.append((104, "sha256:trailing", trailing))
    oversize = bytearray(base64.b64decode(original))
    oversize[22:26] = (1_048_577).to_bytes(4, "big")
    variants.append((105, "sha256:oversize", base64.b64encode(oversize).decode()))
    variants.append((106, None, None))
    for job_id, digest, encoded in variants:
        image_digest = digest or "sha256:missing"
        if digest is not None and encoded is not None:
            insert_image(connection, digest, encoded)
        insert_job(connection, job_id, "dep-one", image_digest)
    connection.close()

    result = run_worker(database, "--once")
    summary = json.loads(result.stdout)
    assert summary["claimed"] == 6
    assert summary["succeeded"] == 0
    assert [item["error"] for item in summary["jobs"]] == ["ENVELOPE_FORMAT"] * 6
    connection = duckdb.connect(str(database))
    assert connection.execute("SELECT count(*) FROM pfseal_audit").fetchone() == (0,)
    connection.close()


def test_chunked_image_transport_is_reassembled_and_manifest_tampering_is_rejected(
    tmp_path: Path,
) -> None:
    """Verify chunk ordering, canonical manifests, hashes, exclusivity, and exact sets."""
    database = tmp_path / "chunks.duckdb"
    connection, _ = setup_one_valid_job(database, job_id=140)
    direct = json.loads(
        connection.execute(
            "SELECT image_annotations_json FROM prefect_images"
        ).fetchone()[0]
    )["io.prefect.pfseal"]
    connection.execute("DELETE FROM prefect_secret_jobs")
    connection.execute("DELETE FROM prefect_images")

    valid = chunked_labels(direct)
    both = dict(valid)
    both["io.prefect.pfseal"] = direct
    wrong_hash = dict(valid)
    wrong_hash["io.prefect.pfseal.manifest"] = canonical_json(
        {"count": 3, "sha256": "f" * 64}
    ).decode()
    missing = dict(valid)
    del missing["io.prefect.pfseal.part.001"]
    extra = dict(valid)
    extra["io.prefect.pfseal.part.003"] = "AAAA"
    cases = [
        (141, "sha256:chunk-valid", valid),
        (142, "sha256:chunk-both", both),
        (143, "sha256:chunk-hash", wrong_hash),
        (144, "sha256:chunk-missing", missing),
        (145, "sha256:chunk-extra", extra),
    ]
    for job_id, digest, labels in cases:
        insert_labels(connection, digest, labels)
        insert_job(connection, job_id, "dep-one", digest)
    connection.close()

    result = run_worker(database, "--once")
    assert result.returncode == 0
    assert json.loads(result.stdout)["jobs"] == [
        {"jobId": 141, "status": "succeeded", "decision": "current"},
        {"jobId": 142, "status": "failed", "error": "ENVELOPE_FORMAT"},
        {"jobId": 143, "status": "failed", "error": "ENVELOPE_FORMAT"},
        {"jobId": 144, "status": "failed", "error": "ENVELOPE_FORMAT"},
        {"jobId": 145, "status": "failed", "error": "ENVELOPE_FORMAT"},
    ]
    connection = duckdb.connect(str(database))
    assert connection.execute("SELECT count(*) FROM pfseal_audit").fetchone() == (1,)
    connection.close()


def test_revision_scoped_ed25519_key_attestation_requires_a_valid_quorum(
    tmp_path: Path,
) -> None:
    """Verify canonical commitments, distinct witnesses, revocation, and key binding."""
    database = tmp_path / "key-attestation.duckdb"
    connection = new_database(database)
    cases = [
        (180, "valid-alt", "succeeded"),
        (181, "forged", "KEY_ATTESTATION"),
        (182, "duplicate", "KEY_ATTESTATION"),
        (183, "revoked", "KEY_ATTESTATION"),
        (184, "stale-share", "KEY_ATTESTATION"),
        (185, "bad-spki", "KEY_ATTESTATION"),
    ]
    expected_valid_attestation_hash = ""
    for job_id, case_name, _ in cases:
        deployment = f"dep-attest-{case_name}"
        key_shares = install_deployment(connection, deployment, 1, 1, [1])
        metadata_key = "pfseal.key.v1.attestation"
        attestation_text = connection.execute(
            "SELECT metadata_value FROM prefect_deployment_metadata "
            "WHERE deployment_id=? AND metadata_key=?",
            [deployment, metadata_key],
        ).fetchone()[0]
        attestation = json.loads(attestation_text)

        if case_name == "valid-alt":
            attestation_text = key_attestation(
                deployment,
                1,
                3,
                f"ws-{deployment}",
                f"pool-{deployment}",
                key_shares[1],
                witness_private_keys(deployment),
                signers=("alpha", "charlie"),
            )
            expected_valid_attestation_hash = hashlib.sha256(
                attestation_text.encode()
            ).hexdigest()
            connection.execute(
                "UPDATE prefect_deployment_metadata SET metadata_value=? "
                "WHERE deployment_id=? AND metadata_key=?",
                [attestation_text, deployment, metadata_key],
            )
        elif case_name == "forged":
            signature = bytearray(
                base64.b64decode(attestation["signatures"][0]["signature"])
            )
            signature[0] ^= 0x80
            attestation["signatures"][0]["signature"] = base64.b64encode(
                signature
            ).decode()
            connection.execute(
                "UPDATE prefect_deployment_metadata SET metadata_value=? "
                "WHERE deployment_id=? AND metadata_key=?",
                [canonical_json(attestation).decode(), deployment, metadata_key],
            )
        elif case_name == "duplicate":
            attestation["signatures"][1] = dict(attestation["signatures"][0])
            connection.execute(
                "UPDATE prefect_deployment_metadata SET metadata_value=? "
                "WHERE deployment_id=? AND metadata_key=?",
                [canonical_json(attestation).decode(), deployment, metadata_key],
            )
        elif case_name == "revoked":
            connection.execute(
                "UPDATE pfseal_key_witnesses SET revoked_at_revision=3 "
                "WHERE deployment_id=? AND witness_id='bravo'",
                [deployment],
            )
        elif case_name == "stale-share":
            connection.execute(
                "UPDATE prefect_deployment_metadata SET metadata_value=? "
                "WHERE deployment_id=? AND metadata_key='pfseal.key.v1.share0'",
                ["hex:" + "00" * 32, deployment],
            )
        elif case_name == "bad-spki":
            connection.execute(
                "UPDATE pfseal_key_witnesses SET public_key_spki_b64=? "
                "WHERE deployment_id=? AND witness_id='bravo'",
                [base64.b64encode(b"not-an-ed25519-key").decode(), deployment],
            )

        encoded, _ = seal(
            deployment,
            1,
            f"ws-{deployment}",
            f"pool-{deployment}",
            key_shares[1],
            canonical_json(payload(deployment, "ATTESTED_KEY")),
            f"attestation:{case_name}",
        )
        digest = f"sha256:attestation-{case_name}"
        insert_image(connection, digest, encoded)
        insert_job(connection, job_id, deployment, digest)
    connection.close()

    result = run_worker(database, "--once")
    assert result.returncode == 0
    assert json.loads(result.stdout)["jobs"] == [
        {"jobId": 180, "status": "succeeded", "decision": "current"},
        *[
            {"jobId": job_id, "status": "failed", "error": "KEY_ATTESTATION"}
            for job_id in range(181, 186)
        ],
    ]
    connection = duckdb.connect(str(database))
    audit = table_rows(connection, "pfseal_audit")
    assert len(audit) == 1
    assert audit[0]["key_attestation_sha256"] == expected_valid_attestation_hash
    assert audit[0]["audit_hash"] == expected_audit_hash(audit[0])
    assert connection.execute(
        "SELECT count(*) FROM prefect_secret_state"
    ).fetchone() == (1,)
    connection.close()


def test_rotation_requires_an_authenticated_revision_bound_successor_proof(
    tmp_path: Path,
) -> None:
    """Verify readable old keys cannot request rotation with forged lineage metadata."""
    database = tmp_path / "lineage.duckdb"
    connection = new_database(database)
    deployment = "dep-lineage"
    key_shares = install_deployment(connection, deployment, 2, 1, [1, 2])
    connection.execute(
        "UPDATE prefect_deployment_metadata SET metadata_value=? "
        "WHERE deployment_id=? AND metadata_key='pfseal.key.v1.successor'",
        ["v2:" + "0" * 64, deployment],
    )
    encoded, _ = seal(
        deployment,
        1,
        f"ws-{deployment}",
        f"pool-{deployment}",
        key_shares[1],
        canonical_json(payload(deployment, "LINEAGE_KEY")),
        "lineage",
    )
    insert_image(connection, "sha256:lineage", encoded)
    insert_job(connection, 171, deployment, "sha256:lineage")
    connection.close()

    result = run_worker(database, "--once")
    assert json.loads(result.stdout)["jobs"] == [
        {"jobId": 171, "status": "failed", "error": "KEY_LINEAGE"}
    ]
    connection = duckdb.connect(str(database))
    for table in ("pfseal_audit", "pfseal_rotation_outbox", "prefect_secret_state"):
        assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)
    connection.close()


def test_metadata_and_key_policy_failures_follow_documented_precedence(
    tmp_path: Path,
) -> None:
    """Verify missing metadata, retired keys, future keys, and revision policy."""
    database = tmp_path / "policy.duckdb"
    connection = new_database(database)
    cases = [
        (201, "retired", 1, 3, 2, "KEY_RETIRED", True, (1, 100)),
        (202, "future", 4, 3, 2, "KEY_FUTURE", True, (1, 100)),
        (203, "missing", 2, 2, 1, "KEY_METADATA", False, (1, 100)),
        (204, "window", 4, 3, 2, "KEY_METADATA", True, (20, 30)),
    ]
    for job_id, name, version, active, minimum, _, include_keys, window in cases:
        deployment = f"dep-{name}"
        all_versions = sorted({version, active})
        key_shares = install_deployment(
            connection,
            deployment,
            active,
            minimum,
            all_versions,
            valid_from=window[0],
            valid_through=window[1],
        )
        selected_shares = key_shares[version]
        encoded, _ = seal(
            deployment,
            version,
            f"ws-{deployment}",
            f"pool-{deployment}",
            selected_shares,
            canonical_json(payload(deployment, "POLICY_KEY")),
            name,
        )
        if not include_keys:
            connection.execute(
                "DELETE FROM prefect_deployment_metadata "
                "WHERE deployment_id=? AND metadata_key LIKE ?",
                [deployment, f"pfseal.key.v{version}.%"],
            )
        digest = f"sha256:{name}"
        insert_image(connection, digest, encoded)
        insert_job(connection, job_id, deployment, digest, revision=3)
    connection.close()

    result = run_worker(database, "--once")
    assert [item["error"] for item in json.loads(result.stdout)["jobs"]] == [
        case[5] for case in cases
    ]
    connection = duckdb.connect(str(database))
    assert connection.execute("SELECT count(*) FROM pfseal_audit").fetchone() == (0,)
    connection.close()


@pytest.mark.parametrize(
    ("case_name", "plaintext"),
    [
        (
            "wrong-deployment",
            canonical_json(payload("someone-else", "PAYLOAD_KEY")),
        ),
        (
            "noncanonical",
            json.dumps(payload("dep-payload", "PAYLOAD_KEY"), sort_keys=True).encode(),
        ),
        (
            "extra-field",
            canonical_json(payload("dep-payload", "PAYLOAD_KEY", extra="forbidden")),
        ),
        (
            "bad-secret-name",
            canonical_json(payload("dep-payload", "lowercase")),
        ),
    ],
)
def test_authenticated_but_invalid_payloads_fail_atomically(
    tmp_path: Path, case_name: str, plaintext: bytes
) -> None:
    """Verify canonical JSON shape, binding, and semantic validation after GCM."""
    database = tmp_path / f"payload-{case_name}.duckdb"
    connection = new_database(database)
    deployment = "dep-payload"
    key_shares = install_deployment(connection, deployment, 1, 1, [1])
    encoded, _ = seal(
        deployment,
        1,
        f"ws-{deployment}",
        f"pool-{deployment}",
        key_shares[1],
        plaintext,
        case_name,
    )
    insert_image(connection, "sha256:payload", encoded)
    insert_job(connection, 301, deployment, "sha256:payload")
    connection.close()

    result = run_worker(database, "--once")
    assert json.loads(result.stdout)["jobs"] == [
        {"jobId": 301, "status": "failed", "error": "PAYLOAD_INVALID"}
    ]
    connection = duckdb.connect(str(database))
    assert connection.execute("SELECT count(*) FROM pfseal_audit").fetchone() == (0,)
    connection.close()


def test_temporal_payload_failures_use_distinct_precedence_codes(
    tmp_path: Path,
) -> None:
    """Verify internal time ordering, not-before, and exclusive expiry boundaries."""
    database = tmp_path / "temporal.duckdb"
    connection = new_database(database)
    cases = [
        (
            351,
            "dep-not-yet",
            payload(
                "dep-not-yet",
                "TIME_KEY",
                notBefore="2026-06-18T15:00:00.000Z",
                expiresAt="2026-06-19T15:00:00.000Z",
            ),
            "PAYLOAD_NOT_YET_VALID",
        ),
        (
            352,
            "dep-expired",
            payload(
                "dep-expired",
                "TIME_KEY",
                expiresAt=AT,
            ),
            "PAYLOAD_EXPIRED",
        ),
        (
            353,
            "dep-order",
            payload(
                "dep-order",
                "TIME_KEY",
                issuedAt="2026-06-18T12:00:00.000Z",
                notBefore="2026-06-18T11:00:00.000Z",
            ),
            "PAYLOAD_INVALID",
        ),
    ]
    for job_id, deployment, clear_payload, _ in cases:
        key_shares = install_deployment(connection, deployment, 1, 1, [1])
        encoded, _ = seal(
            deployment,
            1,
            f"ws-{deployment}",
            f"pool-{deployment}",
            key_shares[1],
            canonical_json(clear_payload),
            f"temporal:{job_id}",
        )
        digest = f"sha256:temporal-{job_id}"
        insert_image(connection, digest, encoded)
        insert_job(connection, job_id, deployment, digest)
    connection.close()

    result = run_worker(database, "--once")
    assert [item["error"] for item in json.loads(result.stdout)["jobs"]] == [
        case[3] for case in cases
    ]
    connection = duckdb.connect(str(database))
    assert connection.execute("SELECT count(*) FROM pfseal_audit").fetchone() == (0,)
    assert connection.execute(
        "SELECT count(*) FROM prefect_secret_state"
    ).fetchone() == (0,)
    connection.close()


def test_replay_state_and_per_deployment_audit_chain_advance_only_on_success(
    tmp_path: Path,
) -> None:
    """Verify counter isolation and every persisted cryptographic audit-chain link."""
    database = tmp_path / "replay-chain.duckdb"
    connection = new_database(database)
    deployment = "dep-chain"
    key_shares = install_deployment(connection, deployment, 1, 1, [1])
    jobs = [
        (601, "SHARED_KEY", 5),
        (602, "SHARED_KEY", 4),
        (603, "OTHER_KEY", 0),
    ]
    for job_id, name, counter in jobs:
        encoded, _ = seal(
            deployment,
            1,
            f"ws-{deployment}",
            f"pool-{deployment}",
            key_shares[1],
            canonical_json(payload(deployment, name, rotationCounter=counter)),
            f"chain:{job_id}",
        )
        digest = f"sha256:chain-{job_id}"
        insert_image(connection, digest, encoded)
        insert_job(connection, job_id, deployment, digest)
    connection.close()

    result = run_worker(database, "--once", worker_id="chain-worker")
    assert json.loads(result.stdout)["jobs"] == [
        {"jobId": 601, "status": "succeeded", "decision": "current"},
        {"jobId": 602, "status": "failed", "error": "PAYLOAD_REPLAY"},
        {"jobId": 603, "status": "succeeded", "decision": "current"},
    ]
    connection = duckdb.connect(str(database))
    audit = table_rows(connection, "pfseal_audit")
    assert [row["audit_sequence"] for row in audit] == [1, 2]
    assert audit[0]["previous_audit_hash"] == "0" * 64
    assert audit[1]["previous_audit_hash"] == audit[0]["audit_hash"]
    assert [row["audit_hash"] for row in audit] == [
        expected_audit_hash(row) for row in audit
    ]
    assert connection.execute(
        "SELECT secret_name, last_rotation_counter FROM prefect_secret_state "
        "ORDER BY secret_name"
    ).fetchall() == [("OTHER_KEY", 0), ("SHARED_KEY", 5)]
    assert connection.execute(
        "SELECT last_sequence, last_audit_hash FROM pfseal_audit_heads"
    ).fetchall() == [(2, audit[-1]["audit_hash"])]
    connection.close()


def test_existing_audit_head_is_continued_and_corrupt_heads_are_fatal(
    tmp_path: Path,
) -> None:
    """Verify non-genesis chaining and fail-closed handling of damaged chain state."""
    valid_database = tmp_path / "head-valid.duckdb"
    connection, _ = setup_one_valid_job(valid_database, job_id=701)
    seed_hash = "ab" * 32
    connection.execute(
        "INSERT INTO pfseal_audit_heads VALUES ('dep-one', 7, ?)", [seed_hash]
    )
    connection.close()
    result = run_worker(valid_database, "--once")
    assert result.returncode == 0
    connection = duckdb.connect(str(valid_database))
    row = table_rows(connection, "pfseal_audit")[0]
    assert (row["audit_sequence"], row["previous_audit_hash"]) == (8, seed_hash)
    assert row["audit_hash"] == expected_audit_hash(row)
    checkpoint = table_rows(
        connection, "pfseal_transparency_checkpoints", "checkpoint_sequence"
    )[0]
    assert checkpoint["checkpoint_sequence"] == 1
    assert checkpoint["previous_checkpoint_hash"] == "0" * 64
    assert checkpoint["merkle_root"] == transparency_merkle_root(
        {"dep-one": (8, row["audit_hash"])}
    )
    frontier, event_root = append_event_frontier(
        [], 1, 701, checkpoint["merkle_root"], row["audit_hash"]
    )
    assert checkpoint["frontier_json"] == canonical_json(frontier).decode()
    assert (
        checkpoint["frontier_sha256"]
        == hashlib.sha256(checkpoint["frontier_json"].encode()).hexdigest()
    )
    assert checkpoint["previous_event_mmr_root"] == "0" * 64
    assert checkpoint["event_mmr_root"] == event_root
    assert checkpoint["checkpoint_hash"] == expected_checkpoint_hash(checkpoint)
    connection.close()

    corrupt_database = tmp_path / "head-corrupt.duckdb"
    connection, _ = setup_one_valid_job(corrupt_database, job_id=702)
    connection.execute(
        "INSERT INTO pfseal_audit_heads VALUES ('dep-one', 7, 'not-a-hash')"
    )
    connection.close()
    result = run_worker(corrupt_database, "--once")
    assert result.returncode == 70
    assert result.stdout == ""
    assert result.stderr == "pfseal-worker: fatal worker error\n"
    connection = duckdb.connect(str(corrupt_database))
    assert connection.execute(
        "SELECT status, attempt_count FROM prefect_secret_jobs WHERE job_id=702"
    ).fetchone() == ("processing", 1)
    assert connection.execute("SELECT count(*) FROM pfseal_audit").fetchone() == (0,)
    assert connection.execute(
        "SELECT count(*) FROM prefect_secret_state"
    ).fetchone() == (0,)
    connection.close()


def test_global_transparency_tree_uses_utf8_order_all_heads_and_hash_chaining(
    tmp_path: Path,
) -> None:
    """Verify prospective roots, byte ordering, odd duplication, and global chaining."""
    database = tmp_path / "transparency.duckdb"
    connection = new_database(database)
    entries = [
        (903, "dep-\ue000", "UNICODE_PRIVATE"),
        (901, "dep-\U00010000", "ASTRAL_PRIVATE"),
        (902, "dep-z", "ASCII_PRIVATE"),
    ]
    for job_id, deployment, secret_name in entries:
        key_shares = install_deployment(connection, deployment, 1, 1, [1])
        encoded, _ = seal(
            deployment,
            1,
            f"ws-{deployment}",
            f"pool-{deployment}",
            key_shares[1],
            canonical_json(payload(deployment, secret_name)),
            f"transparency:{job_id}",
        )
        digest = f"sha256:transparency-{job_id}"
        insert_image(connection, digest, encoded)
        insert_job(connection, job_id, deployment, digest)
    connection.close()

    result = run_worker(database, "--once", worker_id="tree-worker")
    assert result.returncode == 0
    assert [item["jobId"] for item in json.loads(result.stdout)["jobs"]] == [
        901,
        902,
        903,
    ]
    connection = duckdb.connect(str(database))
    audits = table_rows(connection, "pfseal_audit")
    checkpoints = table_rows(
        connection, "pfseal_transparency_checkpoints", "checkpoint_sequence"
    )
    assert len(checkpoints) == len(audits) == 3
    prospective_heads: dict[str, tuple[int, str]] = {}
    previous_hash = "0" * 64
    previous_event_root = "0" * 64
    event_peaks: list[str | None] = []
    for sequence, (audit, checkpoint) in enumerate(zip(audits, checkpoints), start=1):
        prospective_heads[audit["deployment_id"]] = (
            audit["audit_sequence"],
            audit["audit_hash"],
        )
        event_peaks, event_root = append_event_frontier(
            event_peaks,
            sequence,
            audit["job_id"],
            transparency_merkle_root(prospective_heads),
            audit["audit_hash"],
        )
        frontier_json = canonical_json(event_peaks).decode()
        assert checkpoint == {
            "checkpoint_sequence": sequence,
            "job_id": audit["job_id"],
            "head_count": len(prospective_heads),
            "merkle_root": transparency_merkle_root(prospective_heads),
            "triggering_audit_hash": audit["audit_hash"],
            "previous_checkpoint_hash": previous_hash,
            "previous_event_mmr_root": previous_event_root,
            "event_mmr_root": event_root,
            "frontier_json": frontier_json,
            "frontier_sha256": hashlib.sha256(frontier_json.encode()).hexdigest(),
            "checkpoint_hash": checkpoint["checkpoint_hash"],
            "created_at": AT,
        }
        assert checkpoint["checkpoint_hash"] == expected_checkpoint_hash(checkpoint)
        previous_hash = checkpoint["checkpoint_hash"]
        previous_event_root = event_root
    assert [
        key.encode() for key in sorted(prospective_heads, key=lambda key: key.encode())
    ] == [
        b"dep-z",
        "dep-\ue000".encode(),
        "dep-\U00010000".encode(),
    ]
    connection.close()


@pytest.mark.parametrize(
    ("checkpoint_sequence", "checkpoint_hash"),
    [
        (7, "not-a-hash"),
        (9_007_199_254_740_991, "ab" * 32),
    ],
)
def test_corrupt_checkpoint_anchor_is_fatal_and_rolls_back_all_finalization(
    tmp_path: Path, checkpoint_sequence: int, checkpoint_hash: str
) -> None:
    """Verify a damaged global anchor cannot be bypassed or partially advanced."""
    database = tmp_path / f"checkpoint-corrupt-{checkpoint_sequence}.duckdb"
    connection, _ = setup_one_valid_job(database, job_id=951)
    insert_checkpoint_anchor(
        connection,
        checkpoint_sequence,
        77,
        checkpoint_hash,
    )
    connection.close()

    result = run_worker(database, "--once")
    assert result.returncode == 70
    assert result.stdout == ""
    assert result.stderr == "pfseal-worker: fatal worker error\n"
    connection = duckdb.connect(str(database))
    assert connection.execute(
        "SELECT status, attempt_count FROM prefect_secret_jobs WHERE job_id=951"
    ).fetchone() == ("processing", 1)
    assert connection.execute("SELECT count(*) FROM pfseal_audit").fetchone() == (0,)
    assert connection.execute("SELECT count(*) FROM pfseal_audit_heads").fetchone() == (
        0,
    )
    assert connection.execute(
        "SELECT count(*) FROM prefect_secret_state"
    ).fetchone() == (0,)
    assert connection.execute(
        "SELECT count(*) FROM pfseal_transparency_checkpoints"
    ).fetchone() == (1,)
    connection.close()


@pytest.mark.parametrize(
    "damage",
    ["noncanonical-json", "wrong-shape", "wrong-digest", "wrong-root"],
)
def test_event_mmr_frontier_corruption_is_fatal_before_any_proof_advances(
    tmp_path: Path, damage: str
) -> None:
    """Verify canonical shape, frontier digest, and independently bagged root."""
    database = tmp_path / f"frontier-{damage}.duckdb"
    connection, _ = setup_one_valid_job(database, job_id=952)
    valid_json, valid_sha256, valid_root = synthetic_event_frontier(7)
    frontier_json = valid_json
    frontier_sha256 = valid_sha256
    event_root = valid_root
    if damage == "noncanonical-json":
        frontier_json = valid_json.replace(",", ", ")
        frontier_sha256 = hashlib.sha256(frontier_json.encode()).hexdigest()
    elif damage == "wrong-shape":
        frontier_json = canonical_json([*json.loads(valid_json), None]).decode()
        frontier_sha256 = hashlib.sha256(frontier_json.encode()).hexdigest()
    elif damage == "wrong-digest":
        frontier_sha256 = "ff" * 32
    else:
        event_root = "ff" * 32
    insert_checkpoint_anchor(
        connection,
        7,
        78,
        "cc" * 32,
        frontier_json=frontier_json,
        frontier_sha256=frontier_sha256,
        event_mmr_root=event_root,
    )
    connection.close()

    result = run_worker(database, "--once")
    assert result.returncode == 70
    assert result.stdout == ""
    assert result.stderr == "pfseal-worker: fatal worker error\n"
    connection = duckdb.connect(str(database))
    assert connection.execute(
        "SELECT status, attempt_count FROM prefect_secret_jobs WHERE job_id=952"
    ).fetchone() == ("processing", 1)
    for table in (
        "pfseal_audit",
        "pfseal_audit_heads",
        "prefect_secret_state",
        "pfseal_rotation_outbox",
    ):
        assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)
    assert connection.execute(
        "SELECT count(*) FROM pfseal_transparency_checkpoints"
    ).fetchone() == (1,)
    connection.close()


def test_checkpoint_head_selection_is_numeric_and_continues_the_greatest_sequence(
    tmp_path: Path,
) -> None:
    """Verify UBIGINT checkpoint order is not accidentally changed into text order."""
    database = tmp_path / "checkpoint-order.duckdb"
    connection, _ = setup_one_valid_job(database, job_id=961)
    insert_checkpoint_anchor(connection, 2, 72, "aa" * 32)
    insert_checkpoint_anchor(connection, 10, 73, "bb" * 32)
    connection.close()

    result = run_worker(database, "--once")
    assert result.returncode == 0
    connection = duckdb.connect(str(database))
    checkpoint = connection.execute(
        "SELECT checkpoint_sequence, previous_checkpoint_hash, checkpoint_hash "
        "FROM pfseal_transparency_checkpoints ORDER BY checkpoint_sequence DESC LIMIT 1"
    ).fetchone()
    assert checkpoint[:2] == (11, "bb" * 32)
    persisted = table_rows(
        connection, "pfseal_transparency_checkpoints", "checkpoint_sequence"
    )[-1]
    prior_json, _, prior_root = synthetic_event_frontier(10)
    audit = table_rows(connection, "pfseal_audit")[0]
    expected_peaks, expected_root = append_event_frontier(
        json.loads(prior_json),
        11,
        961,
        persisted["merkle_root"],
        audit["audit_hash"],
    )
    assert persisted["previous_event_mmr_root"] == prior_root
    assert persisted["frontier_json"] == canonical_json(expected_peaks).decode()
    assert persisted["event_mmr_root"] == expected_root
    assert persisted["checkpoint_hash"] == expected_checkpoint_hash(persisted)
    connection.close()


@pytest.mark.parametrize(
    ("job_id", "metadata_revision"),
    [
        (9_007_199_254_740_992, 3),
        (801, 9_007_199_254_740_992),
    ],
)
def test_unsafe_unsigned_database_values_fail_before_claim_mutation(
    tmp_path: Path, job_id: int, metadata_revision: int
) -> None:
    """Verify UBIGINT identifiers are never rounded through JavaScript numbers."""
    database = tmp_path / f"unsafe-{job_id}-{metadata_revision}.duckdb"
    connection = new_database(database)
    connection.execute(
        """
        INSERT INTO prefect_secret_jobs (
          job_id, deployment_id, image_digest, metadata_revision, requested_at,
          status, attempt_count
        ) VALUES (?, 'unsafe', 'sha256:missing', ?, CAST(? AS TIMESTAMP), 'pending', 0)
        """,
        [job_id, metadata_revision, "2026-06-18 13:00:00"],
    )
    connection.close()

    result = run_worker(database, "--once")
    assert result.returncode == 70
    assert result.stdout == ""
    assert result.stderr == "pfseal-worker: fatal worker error\n"
    connection = duckdb.connect(str(database))
    assert connection.execute(
        "SELECT status, attempt_count FROM prefect_secret_jobs"
    ).fetchone() == ("pending", 0)
    connection.close()


def test_sigterm_interrupts_an_idle_poll_and_emits_one_clean_summary(
    tmp_path: Path,
) -> None:
    """Verify supervisors can stop an unbounded idle worker without residue."""
    database = tmp_path / "signal.duckdb"
    connection = new_database(database)
    connection.close()
    worker = subprocess.Popen(
        [
            str(WORKER),
            "--db",
            str(database),
            "--worker-id",
            "signal-worker",
            "--poll-ms",
            "60000",
            "--at",
            AT,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(0.8)
    assert worker.poll() is None
    worker.send_signal(signal.SIGTERM)
    stdout, stderr = worker.communicate(timeout=5)
    assert worker.returncode == 0
    assert stderr == ""
    assert json.loads(stdout) == {
        "workerId": "signal-worker",
        "claimed": 0,
        "succeeded": 0,
        "failed": 0,
        "rotations": 0,
        "jobs": [],
    }


def test_bounded_background_polling_processes_then_counts_consecutive_empty_polls(
    tmp_path: Path,
) -> None:
    """Verify non-once polling drains work and exits at the configured idle bound."""
    database = tmp_path / "poll.duckdb"
    connection, _ = setup_one_valid_job(database, job_id=401)
    connection.close()
    result = run_worker(database, "--poll-ms", "10", "--idle-limit", "2")
    assert result.returncode == 0
    assert result.stderr == ""
    summary = json.loads(result.stdout)
    assert summary == {
        "workerId": "verify-1",
        "claimed": 1,
        "succeeded": 1,
        "failed": 0,
        "rotations": 0,
        "jobs": [{"jobId": 401, "status": "succeeded", "decision": "current"}],
    }


def test_failed_audit_write_rolls_back_finalization_and_is_fatal(
    tmp_path: Path,
) -> None:
    """Verify result-table conflicts preserve the lease and expose only fatal stderr."""
    database = tmp_path / "rollback.duckdb"
    connection, hashes_expected = setup_one_valid_job(database, job_id=501)
    connection.execute(
        """
        INSERT INTO pfseal_audit (
          job_id, deployment_id, image_digest, envelope_key_version,
          active_key_version, metadata_revision, key_attestation_sha256,
          header_sha256, plaintext_sha256,
          secret_name, rotation_counter, rotation_decision, audit_sequence,
          previous_audit_hash, audit_hash, worker_id, processed_at
        ) VALUES (
          501, 'existing', 'sha256:existing', 1, 1, 1, ?, ?, ?, 'EXISTING',
          4, 'current', 1, ?, ?, 'old-worker', CAST(? AS TIMESTAMP)
        )
        """,
        [
            hashes_expected["key_attestation_sha256"],
            hashes_expected["header_sha256"],
            hashes_expected["plaintext_sha256"],
            "0" * 64,
            "1" * 64,
            "2026-06-17 00:00:00",
        ],
    )
    connection.close()

    result = run_worker(database, "--once")
    assert result.returncode == 70
    assert result.stdout == ""
    assert result.stderr == "pfseal-worker: fatal worker error\n"
    connection = duckdb.connect(str(database))
    job = connection.execute(
        "SELECT status, attempt_count, lease_owner, failure_code "
        "FROM prefect_secret_jobs WHERE job_id=501"
    ).fetchone()
    assert job == ("processing", 1, "verify-1", None)
    assert connection.execute("SELECT count(*) FROM pfseal_audit").fetchone() == (1,)
    assert connection.execute(
        "SELECT count(*) FROM pfseal_rotation_outbox"
    ).fetchone() == (0,)
    assert connection.execute(
        "SELECT count(*) FROM pfseal_transparency_checkpoints"
    ).fetchone() == (0,)
    connection.close()


def test_failed_checkpoint_write_rolls_back_audit_state_head_and_job(
    tmp_path: Path,
) -> None:
    """Verify a late checkpoint conflict reverses every earlier finalization write."""
    database = tmp_path / "checkpoint-rollback.duckdb"
    connection, _ = setup_one_valid_job(database, job_id=971)
    insert_checkpoint_anchor(connection, 7, 971, "ab" * 32)
    connection.close()

    result = run_worker(database, "--once")
    assert result.returncode == 70
    assert result.stdout == ""
    assert result.stderr == "pfseal-worker: fatal worker error\n"
    connection = duckdb.connect(str(database))
    assert connection.execute(
        "SELECT status, attempt_count, lease_owner, failure_code "
        "FROM prefect_secret_jobs WHERE job_id=971"
    ).fetchone() == ("processing", 1, "verify-1", None)
    for table in (
        "pfseal_audit",
        "pfseal_audit_heads",
        "prefect_secret_state",
        "pfseal_rotation_outbox",
    ):
        assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)
    assert connection.execute(
        "SELECT checkpoint_sequence, job_id, checkpoint_hash "
        "FROM pfseal_transparency_checkpoints"
    ).fetchone() == (7, 971, "ab" * 32)
    connection.close()
