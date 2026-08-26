"""Behavior tests for the KEV remediation ledger CLI."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

APP = Path("/app")
BIN = APP / "bin" / "kev-ledger"
DEFAULT_INDEX = APP / "data" / "catalog_fragments" / "index.json"
DEFAULT_CONFIG = APP / "config" / "profiles.json"
DEFAULT_ACTIONS = APP / "config" / "remediation_actions.jsonl"
TEST_CISA_PRIVATE_KEY = Path("/tests/fixtures/cisa_kev_test_private.pem")
TEST_ACTIONS_PRIVATE_KEY = Path("/tests/fixtures/agency_actions_test_private.pem")
SUCCESS_FILES = [
    "kev-ledger.json",
    "entries.tsv",
    "actions.tsv",
    "vendor-summary.tsv",
    "rebuild-ledger.json",
    "manifest.sha256",
]
CWE_LOOKUP = {
    "CWE-78": "code-execution",
    "CWE-94": "code-execution",
    "CWE-502": "code-execution",
    "CWE-306": "code-execution",
    "CWE-918": "code-execution",
    "CWE-22": "path-traversal",
    "CWE-61": "path-traversal",
    "CWE-284": "auth-integrity",
    "CWE-287": "auth-integrity",
    "CWE-347": "auth-integrity",
    "CWE-20": "input-validation",
    "CWE-119": "memory-safety",
    "CWE-787": "memory-safety",
}
STATUS_RANK = {"overdue": 0, "due_soon": 1, "deferred": 2, "open": 3}
PRIORITY_RANK = {"emergency": 0, "accelerated": 1, "standard": 2}
VALID_ACTIONS = {"defer", "escalate", "suppress", "clear"}


def canonical_bytes(obj: object) -> bytes:
    """Serialize an object using the contract's canonical JSON rules."""
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest for independently derived bytes."""
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a generated or fixture file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> object:
    """Parse a JSON artifact without relying on application code."""
    return json.loads(path.read_text())


def run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run the public CLI and optionally require a successful exit status."""
    result = subprocess.run(
        [str(BIN), *args],
        cwd=str(APP),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"command failed: {result.returncode}\nSTDOUT={result.stdout}\nSTDERR={result.stderr}")
    return result


def fresh_dir(name: str) -> Path:
    """Create a clean per-test workspace under the application root."""
    root = APP / "tmp" / "kev-tests" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def sign_file(path: Path, private_key: Path, signature_path: Path | None = None) -> Path:
    """Create the detached base64 Ed25519 signature consumed by the public CLI."""
    target = signature_path or Path(f"{path}.sig")
    raw_signature = target.with_suffix(target.suffix + ".raw")
    subprocess.run(
        [
            "openssl",
            "pkeyutl",
            "-sign",
            "-rawin",
            "-inkey",
            str(private_key),
            "-in",
            str(path),
            "-out",
            str(raw_signature),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    target.write_bytes(base64.b64encode(raw_signature.read_bytes()) + b"\n")
    raw_signature.unlink()
    return target


def signed_fragment_descriptor(path: Path, source: str, generation: int) -> dict:
    """Sign one temporary catalog fragment and return its authenticated index descriptor."""
    signature = sign_file(path, TEST_CISA_PRIVATE_KEY)
    return {
        "path": path.name,
        "source": source,
        "generation": generation,
        "signer": "cisa-kev-feed",
        "signature": signature.name,
    }


def sign_actions_file(path: Path) -> Path:
    """Sign a temporary remediation overlay with the trusted agency-actions fixture key."""
    return sign_file(path, TEST_ACTIONS_PRIVATE_KEY)


def row_errors(row: dict) -> list[str]:
    """Independently classify catalog-row validation errors from the contract."""
    errors: list[str] = []
    required = [
        "seq",
        "cveID",
        "vendorProject",
        "product",
        "vulnerabilityName",
        "dateAdded",
        "dueDate",
        "knownRansomwareCampaignUse",
        "notes",
        "cwes",
    ]
    for key in required:
        if key not in row:
            errors.append(f"missing_{key}")
    if not isinstance(row.get("seq"), int):
        errors.append("seq_invalid")
    cve = row.get("cveID")
    if not isinstance(cve, str) or not re.match(r"^CVE-\d{4}-\d{4,19}$", cve):
        errors.append("cve_invalid")
    try:
        added = date.fromisoformat(row.get("dateAdded", ""))
    except Exception:
        added = None
        errors.append("date_added_invalid")
    try:
        due = date.fromisoformat(row.get("dueDate", ""))
    except Exception:
        due = None
        errors.append("due_date_invalid")
    if added is not None and due is not None and due < added:
        errors.append("due_before_added")
    if row.get("knownRansomwareCampaignUse") not in {"Known", "Unknown"}:
        errors.append("ransomware_invalid")
    for key in ["vendorProject", "product", "vulnerabilityName"]:
        if not isinstance(row.get(key), str) or not row[key].strip():
            errors.append(f"{key}_blank")
    cwes = row.get("cwes")
    if not isinstance(cwes, list) or not cwes or any(not isinstance(c, str) or not re.match(r"^CWE-\d+$", c) for c in cwes):
        errors.append("cwes_invalid")
    return sorted(errors)


def action_errors(row: dict) -> list[str]:
    """Independently classify action-row validation errors from the contract."""
    errors: list[str] = []
    required = ["seq", "cve_id", "action", "owner", "ticket", "effective_date", "expires_on", "source"]
    for key in required:
        if key not in row:
            errors.append(f"missing_{key}")
    if not isinstance(row.get("seq"), int):
        errors.append("seq_invalid")
    cve = row.get("cve_id")
    if not isinstance(cve, str) or not re.match(r"^CVE-\d{4}-\d{4,19}$", cve):
        errors.append("cve_invalid")
    if row.get("action") not in VALID_ACTIONS:
        errors.append("action_invalid")
    for key in ["owner", "ticket", "source"]:
        if not isinstance(row.get(key), str) or not row[key].strip():
            errors.append(f"{key}_blank")
    try:
        effective = date.fromisoformat(row.get("effective_date", ""))
    except Exception:
        effective = None
        errors.append("effective_date_invalid")
    try:
        expires = date.fromisoformat(row.get("expires_on", ""))
    except Exception:
        expires = None
        errors.append("expires_on_invalid")
    if effective is not None and expires is not None and expires < effective:
        errors.append("expired_before_effective")
    return sorted(errors)


def classes_for(cwes: list[str]) -> list[str]:
    """Map raw CWE identifiers to the documented canonical class set."""
    return sorted({CWE_LOOKUP.get(cwe, "other") for cwe in cwes})


def priority_for(row: dict, classes: list[str]) -> str:
    """Compute expected priority without invoking the implementation."""
    window = (date.fromisoformat(row["dueDate"]) - date.fromisoformat(row["dateAdded"])).days
    if row["knownRansomwareCampaignUse"] == "Known" or window <= 7:
        return "emergency"
    if window <= 14 or "code-execution" in classes:
        return "accelerated"
    return "standard"


def load_actions(actions_path: Path, as_of: date) -> tuple[list[dict], list[dict]]:
    """Parse, validate, deduplicate, and date-evaluate expected action rows."""
    valid: list[dict] = []
    invalid: list[dict] = []
    for line_no, line in enumerate(actions_path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            invalid.append({"seq": None, "cve_id": None, "errors": ["json_invalid"], "line": line_no})
            continue
        errs = action_errors(row)
        if errs:
            invalid.append({"seq": row.get("seq"), "cve_id": row.get("cve_id"), "errors": errs, "line": line_no})
        else:
            valid.append(row)
    invalid.sort(key=lambda r: (int(r["line"]), str(r["cve_id"])))
    winners: dict[str, dict] = {}
    for row in valid:
        old = winners.get(row["cve_id"])
        if old is None or row["seq"] > old["seq"] or (row["seq"] == old["seq"] and row["source"] < old["source"]):
            winners[row["cve_id"]] = row
    actions = []
    for cve in sorted(winners):
        row = winners[cve]
        applied = date.fromisoformat(row["effective_date"]) <= as_of <= date.fromisoformat(row["expires_on"])
        actions.append({
            "cve_id": cve,
            "action": row["action"],
            "source": row["source"],
            "seq": row["seq"],
            "owner": row["owner"].strip(),
            "ticket": row["ticket"].strip(),
            "effective_date": row["effective_date"],
            "expires_on": row["expires_on"],
            "applied": applied,
        })
    return actions, invalid


def expected_from(index_path: Path, config_path: Path, profile_name: str, actions_path: Path = DEFAULT_ACTIONS) -> dict:
    """Build the complete expected ledger independently from source fixtures."""
    index = read_json(index_path)
    config = read_json(config_path)
    profile = config["profiles"][profile_name]
    base = index_path.parent
    fragments = []
    valid = []
    invalid = []
    for frag in index["fragments"]:
        path = base / frag["path"]
        fragments.append({"path": frag["path"], "sha256": sha_file(path)})
        for line_no, line in enumerate(path.read_text().splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            errs = row_errors(row)
            if errs:
                invalid.append({
                    "source": frag["source"],
                    "generation": frag["generation"],
                    "seq": row.get("seq"),
                    "cve_id": row.get("cveID"),
                    "errors": errs,
                    "line": line_no,
                })
            else:
                row = {**row, "_source": frag["source"], "_generation": frag["generation"]}
                valid.append(row)
    invalid.sort(key=lambda r: (str(r["source"]), int(r["generation"]), int(r["line"]), str(r["cve_id"])))
    winners: dict[str, dict] = {}
    for row in valid:
        old = winners.get(row["cveID"])
        if old is None or (row["_generation"], row["seq"], old["_source"]) > (old["_generation"], old["seq"], row["_source"]):
            winners[row["cveID"]] = row
    include_all = "*" in profile["include_vendors"]
    vendors = {v.strip().lower() for v in profile["include_vendors"]}
    allowed_classes = set(profile["include_cwe_classes"])
    as_of = date.fromisoformat(config["as_of"])
    soon_days = int(profile["due_soon_days"])
    actions, invalid_actions = load_actions(actions_path, as_of)
    actions_by_cve = {action["cve_id"]: action for action in actions}
    lineage = []
    entries = []
    for cve in sorted(winners):
        row = winners[cve]
        classes = classes_for(row["cwes"])
        profile_selected = (include_all or row["vendorProject"].strip().lower() in vendors) and bool(set(classes) & allowed_classes)
        action = actions_by_cve.get(cve)
        active_action = action if action and action["applied"] else None
        suppressed = bool(active_action and active_action["action"] == "suppress")
        selected = profile_selected and not suppressed
        lineage.append({"cve_id": cve, "source": row["_source"], "generation": row["_generation"], "seq": row["seq"], "selected": selected})
        if not selected:
            continue
        due = date.fromisoformat(row["dueDate"])
        if active_action and active_action["action"] == "defer":
            status = "deferred"
        elif due < as_of:
            status = "overdue"
        elif due <= as_of + timedelta(days=soon_days):
            status = "due_soon"
        else:
            status = "open"
        priority = priority_for(row, classes)
        if active_action and active_action["action"] == "escalate":
            priority = "emergency"
        entries.append({
            "cve_id": row["cveID"],
            "vendor": row["vendorProject"].strip(),
            "product": row["product"].strip(),
            "vulnerability_name": row["vulnerabilityName"].strip(),
            "date_added": row["dateAdded"],
            "due_date": row["dueDate"],
            "ransomware": row["knownRansomwareCampaignUse"],
            "cwe_classes": classes,
            "status": status,
            "priority": priority,
            "source": row["_source"],
            "generation": row["_generation"],
            "seq": row["seq"],
            "notes_digest": sha_bytes(row["notes"].encode()),
        })
    entries.sort(key=lambda e: (STATUS_RANK[e["status"]], PRIORITY_RANK[e["priority"]], e["vendor"].lower(), e["product"].lower(), e["cve_id"]))

    def count_by(key: str) -> dict:
        """Count expected entries by one canonical ledger field."""
        out: dict[str, int] = {}
        for entry in entries:
            out[entry[key]] = out.get(entry[key], 0) + 1
        return dict(sorted(out.items()))

    by_action: dict[str, int] = {}
    for action in actions:
        if action["applied"]:
            by_action[action["action"]] = by_action.get(action["action"], 0) + 1
    input_fp = sha_bytes(canonical_bytes(sorted(fragments, key=lambda f: f["path"])))
    actions_fp = sha_bytes(canonical_bytes({"path": str(actions_path), "sha256": sha_file(actions_path)}))
    return {
        "schema_version": "kev.ledger.v1",
        "summary": {
            "profile": profile_name,
            "as_of": config["as_of"],
            "entry_count": len(entries),
            "invalid_row_count": len(invalid),
            "action_count": len(actions),
            "invalid_action_count": len(invalid_actions),
            "by_status": count_by("status"),
            "by_priority": count_by("priority"),
            "by_vendor": count_by("vendor"),
            "by_action": dict(sorted(by_action.items())),
            "input_fingerprint": input_fp,
            "actions_fingerprint": actions_fp,
        },
        "entries": entries,
        "actions": actions,
        "invalid_rows": invalid,
        "invalid_actions": invalid_actions,
        "lineage": lineage,
    }


def expected_config_fingerprint(config_path: Path, profile_name: str) -> str:
    """Compute SHA-256 over exact config bytes, NUL, and the profile name."""
    material = config_path.read_bytes() + b"\0" + profile_name.encode()
    return sha_bytes(material)


def expected_generation_max(index_path: Path) -> int:
    """Return the maximum generation declared by the fragment index."""
    index = read_json(index_path)
    return max((fragment["generation"] for fragment in index["fragments"]), default=0)


def expected_entries_tsv(ledger: dict) -> str:
    """Render the exact expected entries TSV from an independent ledger."""
    lines = ["cve_id\tvendor\tproduct\tstatus\tpriority\tdue_date\transomware\tcwe_classes"]
    for entry in ledger["entries"]:
        lines.append("\t".join([
            entry["cve_id"],
            entry["vendor"],
            entry["product"],
            entry["status"],
            entry["priority"],
            entry["due_date"],
            entry["ransomware"],
            "|".join(entry["cwe_classes"]),
        ]))
    return "\n".join(lines) + "\n"


def expected_actions_tsv(ledger: dict) -> str:
    """Render the exact expected actions TSV from an independent ledger."""
    lines = ["cve_id\taction\tapplied\towner\tticket\texpires_on"]
    for action in ledger["actions"]:
        lines.append("\t".join([
            action["cve_id"],
            action["action"],
            str(action["applied"]).lower(),
            action["owner"],
            action["ticket"],
            action["expires_on"],
        ]))
    return "\n".join(lines) + "\n"


def expected_vendor_summary_tsv(ledger: dict) -> str:
    """Render the exact expected vendor summary TSV from ledger entries."""
    lines = ["vendor\tentry_count\temergency\taccelerated\tstandard"]
    for vendor in sorted(ledger["summary"]["by_vendor"], key=str.lower):
        rows = [entry for entry in ledger["entries"] if entry["vendor"] == vendor]
        priorities = {"emergency": 0, "accelerated": 0, "standard": 0}
        for entry in rows:
            priorities[entry["priority"]] += 1
        lines.append("\t".join([
            vendor,
            str(len(rows)),
            str(priorities["emergency"]),
            str(priorities["accelerated"]),
            str(priorities["standard"]),
        ]))
    return "\n".join(lines) + "\n"


def assert_tsv_exports(out_dir: Path, ledger: dict) -> None:
    """Assert every TSV artifact exactly matches independently rendered content."""
    assert (out_dir / "entries.tsv").read_text() == expected_entries_tsv(ledger)
    assert (out_dir / "actions.tsv").read_text() == expected_actions_tsv(ledger)
    assert (out_dir / "vendor-summary.tsv").read_text() == expected_vendor_summary_tsv(ledger)


def assert_dual_state_directory(
    out_dir: Path,
    state_dir: Path,
    ledger: dict,
    config_path: Path = DEFAULT_CONFIG,
    index_path: Path = DEFAULT_INDEX,
) -> None:
    """Verify both state copies and every state value against source inputs."""
    out_state_path = out_dir / "state" / "kev-ledger.state.json"
    external_state_path = state_dir / "kev-ledger.state.json"
    assert sorted(p.relative_to(state_dir).as_posix() for p in state_dir.rglob("*") if p.is_file()) == [
        "kev-ledger.state.json"
    ]
    out_state = read_json(out_state_path)
    external_state = read_json(external_state_path)
    assert external_state == out_state
    assert set(external_state) == {
        "schema_version",
        "profile",
        "config_fingerprint",
        "input_fingerprint",
        "actions_fingerprint",
        "ledger_digest",
        "generation_max",
    }
    assert external_state["schema_version"] == "kev.state.v1"
    assert external_state["profile"] == ledger["summary"]["profile"]
    assert external_state["config_fingerprint"] == expected_config_fingerprint(
        config_path, ledger["summary"]["profile"]
    )
    assert external_state["input_fingerprint"] == ledger["summary"]["input_fingerprint"]
    assert external_state["actions_fingerprint"] == ledger["summary"]["actions_fingerprint"]
    assert external_state["ledger_digest"] == sha_file(out_dir / "kev-ledger.json")
    assert external_state["generation_max"] == expected_generation_max(index_path)


def assert_manifest_and_canonical(
    out_dir: Path,
    ledger: dict,
    config_path: Path = DEFAULT_CONFIG,
    index_path: Path = DEFAULT_INDEX,
) -> None:
    """Verify canonical bytes, digests, manifest entries, and exact state values."""
    assert (out_dir / "kev-ledger.json").read_bytes() == canonical_bytes(ledger)
    manifest = (out_dir / "manifest.sha256").read_text().splitlines()
    manifest_files = ["actions.tsv", "entries.tsv", "kev-ledger.json", "rebuild-ledger.json", "vendor-summary.tsv"]
    expected = [f"{sha_file(out_dir / rel)}  {rel}" for rel in manifest_files]
    assert manifest == sorted(expected)
    rebuild = read_json(out_dir / "rebuild-ledger.json")
    assert rebuild == {
        "schema_version": "kev.rebuild.v1",
        "entry_count": len((out_dir / "entries.tsv").read_text().splitlines()) - 1,
        "action_count": len((out_dir / "actions.tsv").read_text().splitlines()) - 1,
        "vendor_count": len((out_dir / "vendor-summary.tsv").read_text().splitlines()) - 1,
        "entries_digest": sha_file(out_dir / "entries.tsv"),
        "actions_digest": sha_file(out_dir / "actions.tsv"),
        "vendor_summary_digest": sha_file(out_dir / "vendor-summary.tsv"),
    }
    state = read_json(out_dir / "state" / "kev-ledger.state.json")
    assert state["schema_version"] == "kev.state.v1"
    assert state["config_fingerprint"] == expected_config_fingerprint(
        config_path, ledger["summary"]["profile"]
    )
    assert state["input_fingerprint"] == ledger["summary"]["input_fingerprint"]
    assert state["actions_fingerprint"] == ledger["summary"]["actions_fingerprint"]
    assert state["ledger_digest"] == sha_file(out_dir / "kev-ledger.json")
    assert state["generation_max"] == expected_generation_max(index_path)


def assert_no_success_artifacts(out_dir: Path) -> None:
    """Verify run-level failures do not promote any success artifact."""
    assert not any((out_dir / rel).exists() for rel in SUCCESS_FILES)
    assert not (out_dir / "state" / "kev-ledger.state.json").exists()


def assert_regular_file(path: Path) -> None:
    """Verify a local artifact is a regular file rather than a symlink."""
    assert path.exists(), f"missing expected local file: {path}"
    assert path.is_file(), f"expected regular file: {path}"
    assert not path.is_symlink(), f"expected symlink to be replaced: {path}"


def test_default_cisa_sample_outputs_are_canonical_actioned_and_rebuildable() -> None:
    """Verify the default CISA-derived sample applies action overlays and produces canonical artifacts."""
    out_dir = fresh_dir("default") / "out"
    run_cli("--out-dir", str(out_dir))
    ledger = read_json(out_dir / "kev-ledger.json")
    expected = expected_from(DEFAULT_INDEX, DEFAULT_CONFIG, "bod26")
    # Ledger body, count maps, and action effects must match the independently computed expectation.
    assert ledger == expected
    assert ledger["summary"]["entry_count"] == 13
    assert ledger["summary"]["invalid_row_count"] == 2
    assert ledger["summary"]["action_count"] == 4
    assert ledger["summary"]["invalid_action_count"] == 1
    assert ledger["summary"]["by_action"] == {"defer": 1, "escalate": 1, "suppress": 1}
    by_cve = {entry["cve_id"]: entry for entry in ledger["entries"]}
    assert by_cve["CVE-2026-48558"]["status"] == "deferred"
    assert by_cve["CVE-2026-20262"]["priority"] == "emergency"
    assert "CVE-2026-48907" not in by_cve
    assert [action["applied"] for action in ledger["actions"] if action["cve_id"] == "CVE-2026-45659"] == [False]

    # TSV bodies are checked directly, not only through rebuild or manifest hashes.
    assert_tsv_exports(out_dir, expected)

    # Canonical JSON, rebuild digests, manifest entries, and state metadata must agree.
    assert_manifest_and_canonical(out_dir, expected)
    assert not (out_dir / "error-report.json").exists()


def test_edge_device_profile_filters_after_dedup_actions_and_preserves_tsv_order() -> None:
    """Verify profile filtering happens before active action effects and TSV exports retain ledger order."""
    out_dir = fresh_dir("edge-profile") / "out"
    run_cli("--profile", "edge-devices", "--out-dir", str(out_dir))
    ledger = read_json(out_dir / "kev-ledger.json")
    expected = expected_from(DEFAULT_INDEX, DEFAULT_CONFIG, "edge-devices")
    # Profile filtering is applied after catalog deduplication.
    assert ledger == expected
    assert {entry["vendor"] for entry in ledger["entries"]} == {"Cisco", "Ivanti", "Lantronix", "LiteSpeed", "Ubiquiti"}
    assert "CVE-2026-34908" not in {entry["cve_id"] for entry in ledger["entries"]}

    # Action applied status is date-window-only and does not depend on profile membership.
    action_by_cve = {action["cve_id"]: action for action in ledger["actions"]}
    assert action_by_cve["CVE-2026-48558"]["applied"] is True
    assert "CVE-2026-48558" not in {entry["cve_id"] for entry in ledger["entries"]}

    # TSV exports preserve the same canonical order as the JSON arrays and exact body text.
    assert_tsv_exports(out_dir, expected)
    tsv_rows = (out_dir / "entries.tsv").read_text().splitlines()[1:]
    assert [row.split("\t")[0] for row in tsv_rows] == [entry["cve_id"] for entry in ledger["entries"]]
    action_rows = (out_dir / "actions.tsv").read_text().splitlines()
    assert action_rows[0] == "cve_id\taction\tapplied\towner\tticket\texpires_on"
    assert [row.split("\t")[0] for row in action_rows[1:]] == [action["cve_id"] for action in ledger["actions"]]


def test_custom_fixture_exercises_action_dedup_suppression_and_invalid_action_rows() -> None:
    """Verify custom data covers action tie resolution, suppression, inactive clear rows, and invalid action reporting."""
    root = fresh_dir("custom-fixture")
    data = root / "fragments"
    data.mkdir()
    config = root / "profiles.json"
    config.write_text(json.dumps({
        "schema_version": "kev.profiles.v1",
        "as_of": "2026-06-20",
        "profiles": {"custom": {"include_vendors": ["Cisco", "Microsoft"], "include_cwe_classes": ["code-execution", "path-traversal"], "due_soon_days": 5}},
    }))
    (data / "a.jsonl").write_text("\n".join([
        json.dumps({"seq": 7, "cveID": "CVE-2026-45659", "vendorProject": "Microsoft", "product": "SharePoint Server", "vulnerabilityName": "Microsoft SharePoint Server Deserialization of Untrusted Data Vulnerability", "dateAdded": "2026-07-01", "dueDate": "2026-07-04", "knownRansomwareCampaignUse": "Unknown", "notes": "https://msrc.microsoft.com/update-guide/vulnerability/CVE-2026-45659 ; https://nvd.nist.gov/vuln/detail/CVE-2026-45659", "cwes": ["CWE-502"]}),
        json.dumps({"seq": 2, "cveID": "CVE-2026-20262", "vendorProject": "Cisco", "product": "Catalyst SD-WAN Manager", "vulnerabilityName": "Cisco Catalyst SD-WAN Manager Directory or Path Traversal Vulnerability", "dateAdded": "2026-06-15", "dueDate": "2026-06-29", "knownRansomwareCampaignUse": "Unknown", "notes": "lower generation should lose", "cwes": ["CWE-22"]}),
    ]) + "\n")
    (data / "b.jsonl").write_text(json.dumps({"seq": 4, "cveID": "CVE-2026-20262", "vendorProject": "Cisco", "product": "Catalyst SD-WAN Manager", "vulnerabilityName": "Cisco Catalyst SD-WAN Manager Directory or Path Traversal Vulnerability", "dateAdded": "2026-06-15", "dueDate": "2026-06-29", "knownRansomwareCampaignUse": "Unknown", "notes": "alpha source tie should win", "cwes": ["CWE-22"]}) + "\n")
    (data / "c.jsonl").write_text(json.dumps({"seq": 4, "cveID": "CVE-2026-20262", "vendorProject": "Cisco", "product": "Catalyst SD-WAN Manager", "vulnerabilityName": "Cisco Catalyst SD-WAN Manager Directory or Path Traversal Vulnerability", "dateAdded": "2026-06-15", "dueDate": "2026-06-29", "knownRansomwareCampaignUse": "Unknown", "notes": "zeta source tie should lose", "cwes": ["CWE-22"]}) + "\n")
    index = data / "index.json"
    index.write_text(json.dumps({
        "schema_version": "kev.index.v1",
        "fragments": [
            signed_fragment_descriptor(data / "a.jsonl", "custom/base", 1),
            signed_fragment_descriptor(data / "b.jsonl", "alpha/tie", 2),
            signed_fragment_descriptor(data / "c.jsonl", "zeta/tie", 2),
        ],
    }))
    actions = root / "actions.jsonl"
    actions.write_text("\n".join([
        json.dumps({"seq": 2, "cve_id": "CVE-2026-20262", "action": "escalate", "owner": "net", "ticket": "N-2", "effective_date": "2026-06-18", "expires_on": "2026-06-30", "source": "zeta"}),
        json.dumps({"seq": 2, "cve_id": "CVE-2026-20262", "action": "suppress", "owner": "net", "ticket": "N-1", "effective_date": "2026-06-18", "expires_on": "2026-06-30", "source": "alpha"}),
        json.dumps({"seq": 3, "cve_id": "CVE-2026-45659", "action": "defer", "owner": "app", "ticket": "A-3", "effective_date": "2026-06-19", "expires_on": "2026-06-25", "source": "appsec"}),
        json.dumps({"seq": 4, "cve_id": "CVE-2026-0000", "action": "clear", "owner": "old", "ticket": "OLD-4", "effective_date": "2026-06-01", "expires_on": "2026-06-10", "source": "expired"}),
        json.dumps({"seq": "bad", "cve_id": "CVE-2026-9999", "action": "hold", "owner": "", "ticket": "BAD", "effective_date": "2026-06-01", "expires_on": "2026-05-01", "source": "bad"}),
    ]) + "\n")
    sign_actions_file(actions)
    out_dir = root / "out"
    run_cli("--index", str(index), "--config", str(config), "--actions", str(actions), "--profile", "custom", "--out-dir", str(out_dir))
    ledger = read_json(out_dir / "kev-ledger.json")
    expected = expected_from(index, config, "custom", actions)
    # Custom fixture checks catalog tie-breaking, action tie-breaking, and suppression.
    assert ledger == expected
    assert {entry["cve_id"] for entry in ledger["entries"]} == {"CVE-2026-45659"}
    assert ledger["entries"][0]["status"] == "deferred"
    assert ledger["actions"][1]["action"] == "suppress"
    assert ledger["summary"]["invalid_action_count"] == 1

    # Invalid action objects have exactly the public schema and preserve raw invalid seq values.
    assert set(ledger["invalid_actions"][0]) == {"seq", "cve_id", "errors", "line"}
    assert ledger["invalid_actions"][0]["seq"] == "bad"
    assert ledger["invalid_actions"][0]["errors"] == ["action_invalid", "expired_before_effective", "owner_blank", "seq_invalid"]

    # Custom TSV bodies are checked directly against the expected rows.
    assert_tsv_exports(out_dir, expected)


def test_signed_evidence_rejects_tampering_and_unknown_publishers_before_processing() -> None:
    """Verify detached Ed25519 checks reject altered feeds, altered actions, and unknown signers."""
    root = fresh_dir("signature-verification")

    fragment_dir = root / "fragment-tamper"
    shutil.copytree(DEFAULT_INDEX.parent, fragment_dir)
    tampered_fragment = fragment_dir / "kev-june-network.jsonl"
    tampered_fragment.write_bytes(tampered_fragment.read_bytes() + b" ")
    fragment_out = root / "fragment-out"
    result = run_cli("--index", str(fragment_dir / "index.json"), "--out-dir", str(fragment_out), check=False)
    assert result.returncode != 0
    fragment_error = read_json(fragment_out / "error-report.json")
    assert fragment_error["reason"] == "fragment_signature_invalid"
    assert not any((fragment_out / rel).exists() for rel in SUCCESS_FILES)

    actions = root / "tampered-actions.jsonl"
    actions.write_bytes(DEFAULT_ACTIONS.read_bytes() + b" ")
    Path(f"{actions}.sig").write_bytes(Path(f"{DEFAULT_ACTIONS}.sig").read_bytes())
    actions_out = root / "actions-out"
    result = run_cli("--actions", str(actions), "--out-dir", str(actions_out), check=False)
    assert result.returncode != 0
    actions_error = read_json(actions_out / "error-report.json")
    assert actions_error["reason"] == "actions_signature_invalid"
    assert not any((actions_out / rel).exists() for rel in SUCCESS_FILES)

    untrusted_dir = root / "untrusted-signer"
    shutil.copytree(DEFAULT_INDEX.parent, untrusted_dir)
    untrusted_index = read_json(untrusted_dir / "index.json")
    untrusted_index["fragments"][0]["signer"] = "unknown-feed"
    (untrusted_dir / "index.json").write_text(json.dumps(untrusted_index) + "\n")
    untrusted_out = root / "untrusted-out"
    result = run_cli("--index", str(untrusted_dir / "index.json"), "--out-dir", str(untrusted_out), check=False)
    assert result.returncode != 0
    untrusted_error = read_json(untrusted_out / "error-report.json")
    assert untrusted_error["reason"] == "untrusted_fragment_signer"
    assert untrusted_error["details"]["signer"] == "unknown-feed"


def test_catalog_validation_reports_each_error_type_and_trims_stored_strings() -> None:
    """Verify each catalog error contract and whitespace trimming with one focused fixture row."""
    root = fresh_dir("catalog-validation")
    data = root / "fragments"
    data.mkdir()
    config = root / "profiles.json"
    config.write_text(json.dumps({
        "schema_version": "kev.profiles.v1",
        "as_of": "2026-06-10",
        "profiles": {
            "trim": {
                "include_vendors": ["Vendor"],
                "include_cwe_classes": ["code-execution"],
                "due_soon_days": 5,
            }
        },
    }) + "\n")
    actions = root / "actions.jsonl"
    actions.write_text("\n")
    sign_actions_file(actions)
    base_row = {
        "seq": 1,
        "cveID": "CVE-2026-1000",
        "vendorProject": "  Vendor  ",
        "product": "  Product  ",
        "vulnerabilityName": "  Vulnerability Name  ",
        "dateAdded": "2026-06-01",
        "dueDate": "2026-06-20",
        "knownRansomwareCampaignUse": "Unknown",
        "notes": "fixture note",
        "cwes": ["CWE-78"],
    }
    counter = 0

    def variant(*, remove: str | None = None, updates: dict | None = None) -> dict:
        """Return a unique valid catalog row with one requested validation mutation."""
        nonlocal counter
        counter += 1
        row = dict(base_row)
        row["seq"] = counter + 1
        row["cveID"] = f"CVE-2026-{1000 + counter:04d}"
        if updates:
            row.update(updates)
        if remove is not None:
            row.pop(remove)
        return row

    cases = [
        (variant(remove="seq"), ["missing_seq", "seq_invalid"]),
        (variant(remove="cveID"), ["cve_invalid", "missing_cveID"]),
        (variant(remove="vendorProject"), ["missing_vendorProject", "vendorProject_blank"]),
        (variant(remove="product"), ["missing_product", "product_blank"]),
        (variant(remove="vulnerabilityName"), ["missing_vulnerabilityName", "vulnerabilityName_blank"]),
        (variant(remove="dateAdded"), ["date_added_invalid", "missing_dateAdded"]),
        (variant(remove="dueDate"), ["due_date_invalid", "missing_dueDate"]),
        (
            variant(remove="knownRansomwareCampaignUse"),
            ["missing_knownRansomwareCampaignUse", "ransomware_invalid"],
        ),
        (variant(remove="notes"), ["missing_notes"]),
        (variant(remove="cwes"), ["cwes_invalid", "missing_cwes"]),
        (variant(updates={"seq": "bad"}), ["seq_invalid"]),
        (variant(updates={"cveID": "not-a-cve"}), ["cve_invalid"]),
        (variant(updates={"dateAdded": "2026-99-99"}), ["date_added_invalid"]),
        (variant(updates={"dueDate": "2026-99-99"}), ["due_date_invalid"]),
        (
            variant(updates={"dateAdded": "2026-06-20", "dueDate": "2026-06-19"}),
            ["due_before_added"],
        ),
        (variant(updates={"knownRansomwareCampaignUse": "Maybe"}), ["ransomware_invalid"]),
        (variant(updates={"vendorProject": "   "}), ["vendorProject_blank"]),
        (variant(updates={"product": "   "}), ["product_blank"]),
        (variant(updates={"vulnerabilityName": "   "}), ["vulnerabilityName_blank"]),
        (variant(updates={"cwes": []}), ["cwes_invalid"]),
    ]
    lines = [json.dumps(base_row), *(json.dumps(row) for row, _ in cases), '{"seq":']
    fragment = data / "validation.jsonl"
    fragment.write_text("\n".join(lines) + "\n")
    index = data / "index.json"
    index.write_text(json.dumps({
        "schema_version": "kev.index.v1",
        "fragments": [signed_fragment_descriptor(fragment, "validation", 7)],
    }) + "\n")
    out_dir = root / "out"
    state_dir = root / "state"
    run_cli(
        "--index", str(index),
        "--config", str(config),
        "--actions", str(actions),
        "--profile", "trim",
        "--out-dir", str(out_dir),
        "--state-dir", str(state_dir),
    )
    ledger = read_json(out_dir / "kev-ledger.json")

    assert ledger["entries"][0]["vendor"] == "Vendor"
    assert ledger["entries"][0]["product"] == "Product"
    assert ledger["entries"][0]["vulnerability_name"] == "Vulnerability Name"

    expected_by_line = {line_no: errors for line_no, (_, errors) in enumerate(cases, start=2)}
    json_error_line = len(lines)
    expected_by_line[json_error_line] = ["json_invalid"]
    actual_by_line = {row["line"]: row for row in ledger["invalid_rows"]}
    assert set(actual_by_line) == set(expected_by_line)
    for line_no, expected_errors in expected_by_line.items():
        assert actual_by_line[line_no]["errors"] == expected_errors

    documented_errors = {
        "missing_seq",
        "missing_cveID",
        "missing_vendorProject",
        "missing_product",
        "missing_vulnerabilityName",
        "missing_dateAdded",
        "missing_dueDate",
        "missing_knownRansomwareCampaignUse",
        "missing_notes",
        "missing_cwes",
        "seq_invalid",
        "cve_invalid",
        "date_added_invalid",
        "due_date_invalid",
        "due_before_added",
        "ransomware_invalid",
        "vendorProject_blank",
        "product_blank",
        "vulnerabilityName_blank",
        "cwes_invalid",
        "json_invalid",
    }
    observed_errors = {error for row in ledger["invalid_rows"] for error in row["errors"]}
    assert observed_errors == documented_errors
    assert "message" in actual_by_line[json_error_line]


def test_run_level_failure_removes_stale_success_artifacts_and_reports_only_error() -> None:
    """Verify unsafe fragment and action paths are rejected and stale success outputs are cleaned."""
    root = fresh_dir("failure-cleanup")
    out_dir = root / "out"
    out_dir.mkdir()
    for rel in SUCCESS_FILES:
        (out_dir / rel).write_text("stale\n")
    (out_dir / "state").mkdir()
    (out_dir / "state" / "kev-ledger.state.json").write_text("stale\n")
    data = root / "fragments"
    data.mkdir()
    bad_index = data / "index.json"
    bad_index.write_text(json.dumps({
        "schema_version": "kev.index.v1",
        "fragments": [{
            "path": "../escape.jsonl",
            "source": "bad",
            "generation": 1,
            "signer": "cisa-kev-feed",
            "signature": "escape.jsonl.sig",
        }],
    }))
    # Unsafe fragment paths are run-level failures and clean old success files.
    result = run_cli("--index", str(bad_index), "--out-dir", str(out_dir), check=False)
    assert result.returncode != 0
    assert sorted(p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*") if p.is_file()) == ["error-report.json"]
    error = read_json(out_dir / "error-report.json")
    assert error == {"schema_version": "kev.error.v1", "profile": "bod26", "reason": "unsafe_fragment_path", "details": {"path": "../escape.jsonl"}}

    # Unsafe action paths are reported with the action-specific reason and details.
    action_out = root / "action_out"
    result = run_cli("--actions", "/tmp/not-in-app.jsonl", "--out-dir", str(action_out), check=False)
    assert result.returncode != 0
    action_error = read_json(action_out / "error-report.json")
    assert action_error == {"schema_version": "kev.error.v1", "profile": "bod26", "reason": "unsafe_actions_path", "details": {"path": "/tmp/not-in-app.jsonl"}}


def test_generated_output_file_symlinks_are_replaced_without_following_targets() -> None:
    """Verify every generated output file target is safely replaced when it already is a symlink."""
    root = fresh_dir("generated-file-symlink-targets")
    outside = Path("/tmp/kev-ledger-output-targets")
    if outside.exists():
        shutil.rmtree(outside)
    outside.mkdir()
    sentinel = b"outside sentinel remains unchanged\n"

    success_targets = [(rel, rel) for rel in SUCCESS_FILES]
    success_targets.append(("output-state", "state/kev-ledger.state.json"))
    success_targets.append(("external-state", "__external_state__"))
    for label, rel in success_targets:
        out_dir = root / f"out-{label.replace('/', '-') }"
        state_dir = root / f"state-{label.replace('/', '-') }"
        out_dir.mkdir(parents=True)
        state_dir.mkdir(parents=True)
        outside_target = outside / f"{label.replace('/', '-')}.txt"
        outside_target.write_bytes(sentinel)
        if rel == "__external_state__":
            local_target = state_dir / "kev-ledger.state.json"
        else:
            local_target = out_dir / rel
        local_target.parent.mkdir(parents=True, exist_ok=True)
        local_target.symlink_to(outside_target)

        run_cli("--out-dir", str(out_dir), "--state-dir", str(state_dir))

        assert outside_target.read_bytes() == sentinel
        assert_regular_file(local_target)
        if rel == "__external_state__":
            assert read_json(local_target)["schema_version"] == "kev.state.v1"
        elif rel.endswith(".json"):
            assert read_json(local_target)["schema_version"].startswith("kev.")

    error_out = root / "error-out"
    error_out.mkdir()
    outside_error = outside / "error-report.json"
    outside_error.write_bytes(sentinel)
    error_target = error_out / "error-report.json"
    error_target.symlink_to(outside_error)
    result = run_cli("--actions", "/tmp/not-in-app.jsonl", "--out-dir", str(error_out), check=False)
    assert result.returncode != 0
    assert outside_error.read_bytes() == sentinel
    assert_regular_file(error_target)
    assert read_json(error_target)["reason"] == "unsafe_actions_path"


def test_resume_authenticates_changed_inputs_before_fingerprint_comparison() -> None:
    """Verify stale signatures on changed resume inputs fail authentication before resume mismatch."""
    root = fresh_dir("resume-authentication-order")
    baseline = root / "baseline"
    state_dir = root / "state"
    run_cli("--out-dir", str(baseline), "--state-dir", str(state_dir))
    resume = state_dir / "kev-ledger.state.json"
    original_checkpoint = resume.read_bytes()

    fragment_dir = root / "changed-fragment-stale-signature"
    shutil.copytree(DEFAULT_INDEX.parent, fragment_dir)
    fragment = fragment_dir / "kev-june-network.jsonl"
    fragment.write_bytes(fragment.read_bytes() + b"# changed after checkpoint\n")
    fragment_out = root / "fragment-out"
    result = run_cli(
        "--index", str(fragment_dir / "index.json"),
        "--resume-from", str(resume),
        "--out-dir", str(fragment_out),
        check=False,
    )
    assert result.returncode != 0
    assert read_json(fragment_out / "error-report.json")["reason"] == "fragment_signature_invalid"
    assert_no_success_artifacts(fragment_out)
    assert resume.read_bytes() == original_checkpoint

    changed_actions = root / "changed-actions.jsonl"
    changed_actions.write_text(
        DEFAULT_ACTIONS.read_text()
        + json.dumps({
            "seq": 100,
            "cve_id": "CVE-2026-12569",
            "action": "escalate",
            "owner": "incident-response",
            "ticket": "IR-100",
            "effective_date": "2026-06-20",
            "expires_on": "2026-06-30",
            "source": "stale-signature",
        })
        + "\n"
    )
    Path(f"{changed_actions}.sig").write_bytes(Path(f"{DEFAULT_ACTIONS}.sig").read_bytes())
    actions_out = root / "actions-out"
    result = run_cli(
        "--actions", str(changed_actions),
        "--resume-from", str(resume),
        "--out-dir", str(actions_out),
        check=False,
    )
    assert result.returncode != 0
    assert read_json(actions_out / "error-report.json")["reason"] == "actions_signature_invalid"
    assert_no_success_artifacts(actions_out)
    assert resume.read_bytes() == original_checkpoint


def test_selected_profile_schema_errors_and_non_ed25519_trust_keys_fail_cleanly() -> None:
    """Verify malformed selected profiles and wrong-algorithm public keys produce documented error reports."""
    root = fresh_dir("profile-and-trust-validation")
    base_config = read_json(DEFAULT_CONFIG)
    profile_variants = {
        "missing_include_vendors": lambda p: p.pop("include_vendors"),
        "include_vendors_not_array": lambda p: p.update({"include_vendors": "*"}),
        "include_vendors_bad_member": lambda p: p.update({"include_vendors": ["Cisco", 7]}),
        "include_cwe_classes_not_array": lambda p: p.update({"include_cwe_classes": "code-execution"}),
        "include_cwe_classes_bad_member": lambda p: p.update({"include_cwe_classes": ["code-execution", None]}),
        "missing_due_soon_days": lambda p: p.pop("due_soon_days"),
        "due_soon_days_not_integer": lambda p: p.update({"due_soon_days": "7"}),
    }
    for name, mutate in profile_variants.items():
        config = json.loads(json.dumps(base_config))
        config["profiles"]["bad"] = json.loads(json.dumps(config["profiles"]["bod26"]))
        mutate(config["profiles"]["bad"])
        config_path = root / f"{name}.json"
        config_path.write_text(json.dumps(config, sort_keys=True) + "\n")
        out = root / f"profile-out-{name}"
        result = run_cli("--config", str(config_path), "--profile", "bad", "--out-dir", str(out), check=False)
        assert result.returncode != 0
        assert read_json(out / "error-report.json")["reason"] == "config_schema_invalid"
        assert_no_success_artifacts(out)

    rsa_key = root / "rsa-private.pem"
    rsa_pub = root / "rsa-public.pem"
    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(rsa_key)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(rsa_key), "-pubout", "-out", str(rsa_pub)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    trust = read_json(APP / "config" / "trusted_publishers.json")
    trust["publishers"]["cisa-kev-feed"]["public_key"] = str(rsa_pub)
    trust_path = root / "trust-rsa.json"
    trust_path.write_text(json.dumps(trust, sort_keys=True) + "\n")
    out = root / "wrong-algorithm-key"
    result = run_cli("--trust-store", str(trust_path), "--out-dir", str(out), check=False)
    assert result.returncode != 0
    assert read_json(out / "error-report.json")["reason"] == "trust_key_invalid"
    assert_no_success_artifacts(out)


def test_resume_state_is_byte_stable_and_action_change_is_rejected() -> None:
    """Verify valid resume rebuilds byte-stable artifacts and action/config fingerprint changes reject stale state."""
    root = fresh_dir("resume")
    out1 = root / "out1"
    state_dir = root / "state"
    run_cli("--out-dir", str(out1), "--state-dir", str(state_dir))
    first_ledger = read_json(out1 / "kev-ledger.json")

    # The external state directory must contain the same complete state document as the output bundle.
    assert_dual_state_directory(out1, state_dir, first_ledger)
    first_bytes = {rel: (out1 / rel).read_bytes() for rel in SUCCESS_FILES}
    out2 = root / "out2"
    run_cli("--out-dir", str(out2), "--state-dir", str(state_dir), "--resume-from", str(state_dir / "kev-ledger.state.json"))
    # A valid resume regenerates byte-identical success artifacts and refreshes both state locations.
    for rel, data in first_bytes.items():
        assert (out2 / rel).read_bytes() == data
    assert_dual_state_directory(out2, state_dir, first_ledger)

    # Changing the action overlay is rejected before promoting stale success outputs.
    changed_actions = root / "actions_changed.jsonl"
    changed_actions.write_text(DEFAULT_ACTIONS.read_text() + json.dumps({"seq": 99, "cve_id": "CVE-2026-12569", "action": "escalate", "owner": "plm", "ticket": "PLM-99", "effective_date": "2026-06-20", "expires_on": "2026-06-30", "source": "late"}) + "\n")
    sign_actions_file(changed_actions)
    bad_out = root / "bad_out"
    for rel in SUCCESS_FILES:
        bad_out.mkdir(parents=True, exist_ok=True)
        (bad_out / rel).write_text("stale\n")
    result = run_cli("--actions", str(changed_actions), "--out-dir", str(bad_out), "--resume-from", str(state_dir / "kev-ledger.state.json"), check=False)
    assert result.returncode != 0
    assert not any((bad_out / rel).exists() for rel in SUCCESS_FILES)
    error = read_json(bad_out / "error-report.json")
    assert error["reason"] == "resume_fingerprint_mismatch"
    assert read_json(state_dir / "kev-ledger.state.json")["actions_fingerprint"] != sha_bytes(canonical_bytes({"path": str(changed_actions), "sha256": sha_file(changed_actions)}))


def test_resolved_path_guards_reject_symlink_and_parent_escapes_across_all_path_classes() -> None:
    """Verify lexical traversal and resolved symlink escapes fail for inputs, keys, signatures, resume, outputs, and state."""
    root = fresh_dir("resolved-path-guards")
    outside = Path("/tmp/kev-ledger-escape-fixtures")
    if outside.exists():
        shutil.rmtree(outside)
    outside.mkdir()
    (outside / "index.json").write_text(DEFAULT_INDEX.read_text())
    (outside / "config.json").write_text(DEFAULT_CONFIG.read_text())
    (outside / "actions.jsonl").write_bytes(DEFAULT_ACTIONS.read_bytes())
    (outside / "actions.jsonl.sig").write_bytes(Path(f"{DEFAULT_ACTIONS}.sig").read_bytes())
    (outside / "state.json").write_text("{}\n")
    (outside / "trust.json").write_text((APP / "config" / "trusted_publishers.json").read_text())
    (outside / "key.pem").write_bytes((APP / "config" / "cisa-kev-ed25519.pubkey").read_bytes())

    links = root / "links"
    links.mkdir()
    for name in ["index.json", "config.json", "actions.jsonl", "actions.jsonl.sig", "state.json", "trust.json", "key.pem"]:
        (links / name).symlink_to(outside / name)

    cases = [
        (("--index", str(links / "index.json")), "unsafe_index_path"),
        (("--config", str(links / "config.json")), "unsafe_config_path"),
        (("--actions", str(links / "actions.jsonl")), "unsafe_actions_path"),
        (("--actions-signature", str(links / "actions.jsonl.sig")), "unsafe_actions_signature_path"),
        (("--resume-from", str(links / "state.json")), "unsafe_resume_path"),
        (("--trust-store", str(links / "trust.json")), "unsafe_trust_store_path"),
    ]
    for idx, (args, reason) in enumerate(cases):
        out = root / f"out-{idx}"
        result = run_cli(*args, "--out-dir", str(out), check=False)
        assert result.returncode != 0
        assert read_json(out / "error-report.json")["reason"] == reason

    raw = root / "raw-parent-segments"
    raw.mkdir()
    (raw / "nested").mkdir()
    shutil.copy(DEFAULT_INDEX, raw / "index.json")
    shutil.copy(DEFAULT_CONFIG, raw / "config.json")
    shutil.copy(DEFAULT_ACTIONS, raw / "actions.jsonl")
    shutil.copy(Path(f"{DEFAULT_ACTIONS}.sig"), raw / "actions.jsonl.sig")
    shutil.copy(APP / "config" / "trusted_publishers.json", raw / "trust.json")
    (raw / "state.json").write_text("{}\n")
    raw_cases = [
        (("--index", f"{raw}/nested/../index.json"), "unsafe_index_path"),
        (("--config", f"{raw}/nested/../config.json"), "unsafe_config_path"),
        (("--actions", f"{raw}/nested/../actions.jsonl"), "unsafe_actions_path"),
        (("--actions-signature", f"{raw}/nested/../actions.jsonl.sig"), "unsafe_actions_signature_path"),
        (("--resume-from", f"{raw}/nested/../state.json"), "unsafe_resume_path"),
        (("--trust-store", f"{raw}/nested/../trust.json"), "unsafe_trust_store_path"),
    ]
    for idx, (args, reason) in enumerate(raw_cases):
        out = root / f"raw-out-{idx}"
        result = run_cli(*args, "--out-dir", str(out), check=False)
        assert result.returncode != 0
        assert read_json(out / "error-report.json")["reason"] == reason

    raw_output = f"{raw}/nested/../output"
    result = run_cli("--out-dir", raw_output, check=False)
    assert result.returncode != 0
    assert not (raw / "output").exists()

    raw_state_out = root / "raw-state-out"
    raw_state = f"{raw}/nested/../state-dir"
    result = run_cli("--state-dir", raw_state, "--out-dir", str(raw_state_out), check=False)
    assert result.returncode != 0
    assert read_json(raw_state_out / "error-report.json")["reason"] == "unsafe_state_path"

    trust = root / "trust.json"
    trust.write_text(json.dumps({
        "schema_version": "kev.trust.v1",
        "publishers": {
            "cisa-kev-feed": {"public_key": str(links / "key.pem")},
            "agency-actions": {"public_key": str(APP / "config" / "agency-actions-ed25519.pubkey")},
        },
    }) + "\n")
    key_out = root / "key-out"
    result = run_cli("--trust-store", str(trust), "--out-dir", str(key_out), check=False)
    assert result.returncode != 0
    assert read_json(key_out / "error-report.json")["reason"] == "unsafe_trust_key_path"

    raw_key_trust = root / "raw-key-trust.json"
    raw_key_trust.write_text(json.dumps({
        "schema_version": "kev.trust.v1",
        "publishers": {
            "cisa-kev-feed": {"public_key": "/app/config/nested/../cisa-kev-ed25519.pubkey"},
            "agency-actions": {"public_key": str(APP / "config" / "agency-actions-ed25519.pubkey")},
        },
    }) + "\n")
    raw_key_out = root / "raw-key-out"
    result = run_cli("--trust-store", str(raw_key_trust), "--out-dir", str(raw_key_out), check=False)
    assert result.returncode != 0
    assert read_json(raw_key_out / "error-report.json")["reason"] == "unsafe_trust_key_path"

    fragment_dir = root / "fragment-links"
    shutil.copytree(DEFAULT_INDEX.parent, fragment_dir)
    (fragment_dir / "escape.jsonl").symlink_to(outside / "actions.jsonl")
    idx = read_json(fragment_dir / "index.json")
    idx["fragments"][0]["path"] = "escape.jsonl"
    (fragment_dir / "index.json").write_text(json.dumps(idx) + "\n")
    frag_out = root / "fragment-out"
    result = run_cli("--index", str(fragment_dir / "index.json"), "--out-dir", str(frag_out), check=False)
    assert result.returncode != 0
    assert read_json(frag_out / "error-report.json")["reason"] == "unsafe_fragment_path"

    raw_fragment_dir = root / "raw-fragments"
    shutil.copytree(DEFAULT_INDEX.parent, raw_fragment_dir)
    (raw_fragment_dir / "nested").mkdir()
    raw_fragment_index = read_json(raw_fragment_dir / "index.json")
    raw_fragment_index["fragments"][0]["path"] = "nested/../kev-june-network.jsonl"
    (raw_fragment_dir / "index.json").write_text(json.dumps(raw_fragment_index) + "\n")
    raw_fragment_out = root / "raw-fragment-out"
    result = run_cli("--index", str(raw_fragment_dir / "index.json"), "--out-dir", str(raw_fragment_out), check=False)
    assert result.returncode != 0
    assert read_json(raw_fragment_out / "error-report.json")["reason"] == "unsafe_fragment_path"

    signature_dir = root / "signature-links"
    shutil.copytree(DEFAULT_INDEX.parent, signature_dir)
    outside_sig = outside / "fragment.sig"
    outside_sig.write_bytes((DEFAULT_INDEX.parent / "kev-june-network.jsonl.sig").read_bytes())
    (signature_dir / "escape.sig").symlink_to(outside_sig)
    sig_index = read_json(signature_dir / "index.json")
    sig_index["fragments"][0]["signature"] = "escape.sig"
    (signature_dir / "index.json").write_text(json.dumps(sig_index) + "\n")
    sig_out = root / "signature-out"
    result = run_cli("--index", str(signature_dir / "index.json"), "--out-dir", str(sig_out), check=False)
    assert result.returncode != 0
    assert read_json(sig_out / "error-report.json")["reason"] == "unsafe_fragment_signature_path"

    raw_signature_dir = root / "raw-signatures"
    shutil.copytree(DEFAULT_INDEX.parent, raw_signature_dir)
    (raw_signature_dir / "nested").mkdir()
    raw_signature_index = read_json(raw_signature_dir / "index.json")
    raw_signature_index["fragments"][0]["signature"] = "nested/../kev-june-network.jsonl.sig"
    (raw_signature_dir / "index.json").write_text(json.dumps(raw_signature_index) + "\n")
    raw_signature_out = root / "raw-signature-out"
    result = run_cli("--index", str(raw_signature_dir / "index.json"), "--out-dir", str(raw_signature_out), check=False)
    assert result.returncode != 0
    assert read_json(raw_signature_out / "error-report.json")["reason"] == "unsafe_fragment_signature_path"

    outside_out = outside / "promoted"
    output_link = root / "output-link"
    output_link.symlink_to(outside_out, target_is_directory=True)
    result = run_cli("--out-dir", str(output_link), check=False)
    assert result.returncode != 0
    assert not outside_out.exists()

    nested_target = outside / "nested-output-target"
    nested_target.mkdir()
    output_parent_link = root / "output-parent-link"
    output_parent_link.symlink_to(nested_target, target_is_directory=True)
    result = run_cli("--out-dir", str(output_parent_link / "child"), check=False)
    assert result.returncode != 0
    assert not (nested_target / "child").exists()

    output_state_target = outside / "output-state-target"
    output_state_target.mkdir()
    output_state_out = root / "output-state-out"
    output_state_out.mkdir()
    (output_state_out / "state").symlink_to(output_state_target, target_is_directory=True)
    result = run_cli("--out-dir", str(output_state_out), check=False)
    assert result.returncode != 0
    assert read_json(output_state_out / "error-report.json")["reason"] == "unsafe_output_path"
    assert not (output_state_target / "kev-ledger.state.json").exists()

    state_target = outside / "state-target"
    state_target.mkdir()
    state_link = root / "state-link"
    state_link.symlink_to(state_target, target_is_directory=True)
    state_out = root / "state-out"
    result = run_cli("--state-dir", str(state_link), "--out-dir", str(state_out), check=False)
    assert result.returncode != 0
    assert read_json(state_out / "error-report.json")["reason"] == "unsafe_state_path"

    traversal_out = root / "traversal-out"
    traversal = f"{root}/sub/../actions.jsonl"
    result = run_cli("--actions", traversal, "--out-dir", str(traversal_out), check=False)
    assert result.returncode != 0
    assert read_json(traversal_out / "error-report.json")["reason"] == "unsafe_actions_path"


def test_authentication_precedes_parsing_and_action_trust_overrides_are_enforced() -> None:
    """Verify malformed unauthenticated evidence fails signature checks and configured action trust controls are honored."""
    root = fresh_dir("authentication-order")
    malformed_fragment_dir = root / "fragment"
    shutil.copytree(DEFAULT_INDEX.parent, malformed_fragment_dir)
    fragment = malformed_fragment_dir / "kev-june-network.jsonl"
    fragment.write_text("{not-json\n")
    fragment_out = root / "fragment-out"
    result = run_cli("--index", str(malformed_fragment_dir / "index.json"), "--out-dir", str(fragment_out), check=False)
    assert result.returncode != 0
    assert read_json(fragment_out / "error-report.json")["reason"] == "fragment_signature_invalid"

    malformed_actions = root / "malformed-actions.jsonl"
    malformed_actions.write_text("{not-json\n")
    Path(f"{malformed_actions}.sig").write_text("not-base64\n")
    action_out = root / "action-out"
    result = run_cli("--actions", str(malformed_actions), "--out-dir", str(action_out), check=False)
    assert result.returncode != 0
    assert read_json(action_out / "error-report.json")["reason"] == "actions_signature_invalid"

    signed_actions = root / "signed-actions.jsonl"
    signed_actions.write_bytes(DEFAULT_ACTIONS.read_bytes())
    explicit_sig = root / "explicit-action.sig"
    sign_file(signed_actions, TEST_ACTIONS_PRIVATE_KEY, explicit_sig)
    trust = root / "trust.json"
    trust.write_text(json.dumps(read_json(APP / "config" / "trusted_publishers.json")) + "\n")
    success_out = root / "success"
    run_cli(
        "--actions", str(signed_actions),
        "--actions-signature", str(explicit_sig),
        "--actions-signer", "agency-actions",
        "--trust-store", str(trust),
        "--out-dir", str(success_out),
    )
    assert (success_out / "kev-ledger.json").exists()

    unknown_out = root / "unknown"
    result = run_cli(
        "--actions", str(signed_actions),
        "--actions-signature", str(explicit_sig),
        "--actions-signer", "unknown-action-publisher",
        "--trust-store", str(trust),
        "--out-dir", str(unknown_out),
        check=False,
    )
    assert result.returncode != 0
    assert read_json(unknown_out / "error-report.json")["reason"] == "untrusted_actions_signer"


def test_non_object_documents_and_signed_action_validation_are_reported_without_crashes() -> None:
    """Verify non-object index/config/trust JSON and malformed or cumulatively invalid signed actions are handled deterministically."""
    root = fresh_dir("non-object-json")
    for flag, name, reason in [
        ("--index", "index.json", "index_schema_invalid"),
        ("--config", "config.json", "config_schema_invalid"),
        ("--trust-store", "trust.json", "trust_store_schema_invalid"),
    ]:
        for shape, payload in [("null", "null\n"), ("array", "[]\n")]:
            path = root / name
            path.write_text(payload)
            out = root / f"{name}-{shape}-out"
            result = run_cli(flag, str(path), "--out-dir", str(out), check=False)
            assert result.returncode != 0
            assert read_json(out / "error-report.json")["reason"] == reason

    actions = root / "validation-actions.jsonl"
    actions.write_text("\n".join([
        "{bad-json",
        "null",
        json.dumps({"seq": "bad", "cve_id": "bad", "action": "hold", "owner": " ", "ticket": " ", "effective_date": "bad", "expires_on": "bad", "source": " "}),
        json.dumps({}),
    ]) + "\n")
    sign_actions_file(actions)
    out = root / "actions-out"
    run_cli("--actions", str(actions), "--out-dir", str(out))
    invalid = read_json(out / "kev-ledger.json")["invalid_actions"]
    assert invalid[0]["errors"] == ["json_invalid"]
    assert invalid[1]["errors"] == ["json_object_required"]
    assert invalid[2]["errors"] == [
        "action_invalid", "cve_invalid", "effective_date_invalid", "expires_on_invalid",
        "owner_blank", "seq_invalid", "source_blank", "ticket_blank",
    ]
    assert invalid[3]["errors"] == [
        "action_invalid", "cve_invalid", "effective_date_invalid", "expires_on_invalid",
        "missing_action", "missing_cve_id", "missing_effective_date", "missing_expires_on",
        "missing_owner", "missing_seq", "missing_source", "missing_ticket", "owner_blank",
        "seq_invalid", "source_blank", "ticket_blank",
    ]


def test_resume_rejects_changed_config_and_correctly_resigned_fragment() -> None:
    """Verify resume binds the config bytes and authenticated catalog-fragment bytes as well as the action overlay."""
    root = fresh_dir("resume-all-fingerprints")
    baseline = root / "baseline"
    state_dir = root / "state"
    run_cli("--out-dir", str(baseline), "--state-dir", str(state_dir))
    resume = state_dir / "kev-ledger.state.json"

    changed_config = root / "profiles.json"
    config = read_json(DEFAULT_CONFIG)
    config["as_of"] = "2026-07-02"
    changed_config.write_text(json.dumps(config, sort_keys=True) + "\n")
    config_out = root / "config-out"
    result = run_cli(
        "--config", str(changed_config), "--out-dir", str(config_out),
        "--resume-from", str(resume), check=False,
    )
    assert result.returncode != 0
    assert read_json(config_out / "error-report.json")["reason"] == "resume_fingerprint_mismatch"
    assert not any((config_out / rel).exists() for rel in SUCCESS_FILES)

    fragment_dir = root / "fragments"
    shutil.copytree(DEFAULT_INDEX.parent, fragment_dir)
    fragment = fragment_dir / "kev-june-network.jsonl"
    fragment.write_bytes(fragment.read_bytes() + b"\n")
    sign_file(fragment, TEST_CISA_PRIVATE_KEY, fragment_dir / "kev-june-network.jsonl.sig")
    fragment_out = root / "fragment-out"
    result = run_cli(
        "--index", str(fragment_dir / "index.json"), "--out-dir", str(fragment_out),
        "--resume-from", str(resume), check=False,
    )
    assert result.returncode != 0
    assert read_json(fragment_out / "error-report.json")["reason"] == "resume_fingerprint_mismatch"
    assert not any((fragment_out / rel).exists() for rel in SUCCESS_FILES)
