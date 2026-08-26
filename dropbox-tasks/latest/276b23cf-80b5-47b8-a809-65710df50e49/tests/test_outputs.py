"""Verifier for the path observation lab (Rust pathlab)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

OUT = Path("/app/output/lab_observations.json")
JOURNAL = Path("/app/var/run_journal.json")
ROUTE_PLAN = Path("/app/var/route_plan.json")
LAB = ["/app/bin/run_lab"]
REBUILD = ["/app/environment/scripts/rebuild_pathlab.sh"]
DATA = Path("/app/environment/data")
ENV_ROOT = Path("/app/environment")
MARKER = "TLS-LAB-01"
ALPN_CODES = {"challenge": 16777220, "app_default": 16777216, "stripped": 0}
EPOCH_MAP = {"primary": 101, "secondary": 202, "tertiary": 303}
TRUNCATION_PROBE_BYTES = 48


def _scan_sections(text: str, header: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    block: dict[str, str] = {}
    active = False
    for raw in text.splitlines():
        line = raw.strip()
        if line == header:
            if block:
                rows.append(block)
            block = {}
            active = True
            continue
        if line.startswith("[[") and active:
            if block:
                rows.append(block)
            block = {}
            active = line == header
            continue
        if (
            active
            and "=" in line
            and not line.startswith("[")
            and not line.startswith("#")
        ):
            key, _, val = line.partition("=")
            block[key.strip()] = val.strip().strip('"')
    if block and active:
        rows.append(block)
    return rows


def _load_kv_section(path: Path, section: str) -> dict[str, str]:
    out: dict[str, str] = {}
    in_section = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == f"[{section}]":
            in_section = True
            continue
        if line.startswith("[") and in_section:
            break
        if in_section and "=" in line:
            key, _, val = line.partition("=")
            out[key.strip()] = val.strip().strip('"')
    return out


def _layout_rows() -> list[dict[str, str]]:
    return _scan_sections((DATA / "layout_t9.toml").read_text(encoding="utf-8"), "[[row]]")


def _policy_rows() -> list[dict[str, str]]:
    return _scan_sections((DATA / "cohort_policy.toml").read_text(encoding="utf-8"), "[[plan]]")


def _arm_dispatch() -> dict[str, str]:
    rows = _scan_sections((DATA / "arm_dispatch.toml").read_text(encoding="utf-8"), "[[dispatch]]")
    return {r["dispatch_id"]: r["material_arm"] for r in rows}


def _plan_manifest() -> dict[str, str]:
    return _load_kv_section(DATA / "plan_manifest.toml", "plan_hash")


def _strip_rules() -> dict[str, str]:
    return _load_kv_section(DATA / "strip_rules.toml", "strip")


def _policy_revision() -> str:
    return _load_kv_section(DATA / "cohort_policy.toml", "meta").get("policy_revision", "")


def _seal_manifest() -> dict[str, str]:
    return _load_kv_section(DATA / "seal_manifest.toml", "observation_seal")


def _plan_hash_preimage(body: str, compile_generation: int, prior_digest: str = "") -> str:
    manifest = _plan_manifest()
    min_gen = int(manifest.get("prior_min_generation", "2"))
    for step in manifest.get("bind_sequence", "body").split(","):
        step = step.strip()
        if step == "revision":
            body = f"{body}{manifest.get('revision_sep', '|')}{_policy_revision()}"
        elif step == "prior" and compile_generation >= min_gen:
            body = f"{body}{manifest.get('prior_sep', '|')}{prior_digest}"
        elif step == "generation":
            body = f"{body}{manifest.get('generation_sep', '|')}{compile_generation}"
    return body


def _route_plan_cache() -> dict:
    return json.loads(ROUTE_PLAN.read_text(encoding="utf-8"))


def _alpn_rules() -> dict[str, str]:
    return _load_kv_section(DATA / "alpn_rules.toml", "alpn")


def _epoch_bind() -> dict[str, str]:
    return _load_kv_section(DATA / "epoch_bind.toml", "remote")


def _resolve_entry_arms(
    entry: dict, muxes: dict[str, dict], dispatch: dict[str, str]
) -> tuple[str, str]:
    mux_arm = _mux_slot(entry["mux_id"], entry["probe_kind"], muxes)
    material_arm = _resolve_arm(dispatch, entry["dispatch_id"], mux_arm)
    return mux_arm, material_arm


def _remote_epoch(
    material_arm: str, remote_material: bytes, rewrite_count: int
) -> int:
    if rewrite_count > 0 and not _has_marker(remote_material):
        slot = _epoch_bind().get("strip_substituted_epoch", "primary")
        return EPOCH_MAP[slot]
    if _has_marker(remote_material):
        return EPOCH_MAP["secondary"]
    if material_arm == "tertiary":
        return EPOCH_MAP["tertiary"]
    return EPOCH_MAP["primary"]


def _read_bytes(rel: str) -> bytes:
    return (ENV_ROOT / rel).read_bytes()


def _sha256_hex(data: bytes) -> str:
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256", "-hex"],
        input=data,
        capture_output=True,
        check=True,
        timeout=30,
    )
    line = proc.stdout.decode("utf-8").strip()
    return line.split("=", 1)[1].strip().replace(":", "")


def _has_marker(pem: bytes) -> bool:
    return MARKER.encode("utf-8") in pem


def _compact_json_value(value: object) -> str:
    if isinstance(value, dict):
        keys = sorted(value.keys())
        inner = ",".join(f'"{k}":{_compact_json_value(value[k])}' for k in keys)
        return "{" + inner + "}"
    if isinstance(value, list):
        return "[" + ",".join(_compact_json_value(v) for v in value) + "]"
    if isinstance(value, str):
        return json.dumps(value)
    if type(value) is bool:
        return "true" if value else "false"
    return json.dumps(value)


def _mux_slot(mux_id: str, probe_kind: str, muxes: dict[str, dict]) -> str:
    rec = muxes.get(mux_id, {})
    sni = rec.get("sni_slot", "")
    if sni == "chal" or probe_kind == "chal":
        return "secondary"
    return "primary"


def _resolve_arm(dispatch: dict[str, str], dispatch_id: str, mux_slot: str) -> str:
    arm = dispatch.get(dispatch_id, "mux")
    if arm == "mux":
        return mux_slot
    return arm


def _select_material(arm: str, primary: bytes, secondary: bytes, tertiary: bytes) -> bytes:
    if arm == "secondary":
        return secondary
    if arm == "tertiary":
        return tertiary
    return primary


def _epoch_for_material(arm: str, material: bytes) -> int:
    if _has_marker(material):
        return EPOCH_MAP["secondary"]
    if arm == "tertiary":
        return EPOCH_MAP["tertiary"]
    return EPOCH_MAP["primary"]


def _negotiate_alpn(negotiation_class: str, material: bytes, rewrite_count: int) -> int:
    rules = _alpn_rules()
    if (
        rules.get("retain_challenge_on_retain_local") == "true"
        and rewrite_count > 0
        and _has_marker(material)
    ):
        if negotiation_class == rules.get("app_class", "app"):
            return ALPN_CODES["app_default"]
        return ALPN_CODES["challenge"]
    if (
        rules.get("strip_alpn_without_marker") == "true"
        and rewrite_count > 0
        and not _has_marker(material)
    ):
        return ALPN_CODES["stripped"]
    if negotiation_class == rules.get("app_class", "app"):
        return ALPN_CODES["app_default"]
    if _has_marker(material):
        return ALPN_CODES["challenge"]
    return ALPN_CODES["app_default"]


def _simulate_remote(
    lane_id: str,
    local: bytes,
    primary: bytes,
    lanes: dict[str, dict],
    strip_rules: dict[str, str],
) -> tuple[bytes, int]:
    lane = lanes.get(lane_id, {})
    if lane.get("sim_kind") != "strip":
        return local, int(strip_rules.get("pass_rewrite_count", "0"))
    if _has_marker(local):
        return local, int(strip_rules.get("strip_rewrite_count", "1"))
    return primary, int(strip_rules.get("strip_rewrite_count", "1"))


def _compile_plan() -> list[dict]:
    policy_map = {
        (r["host_id"], r["lane_id"], r["cohort_label"]): r for r in _policy_rows()
    }
    entries: list[dict] = []
    for row in _layout_rows():
        key = (row["host_id"], row["lane_id"], row["cohort_label"])
        policy = policy_map[key]
        entries.append(
            {
                "host_id": row["host_id"],
                "lane_id": row["lane_id"],
                "cohort_label": row["cohort_label"],
                "mux_id": row["mux_id"],
                "probe_kind": row["probe_kind"],
                "plan_index": int(policy["plan_index"]),
                "negotiation_class": policy["negotiation_class"],
                "dispatch_id": policy["dispatch_id"],
            }
        )
    entries.sort(key=lambda e: e["plan_index"])
    return entries


def _plan_hash(plan: list[dict], compile_generation: int, prior_digest: str = "") -> str:
    manifest = _plan_manifest()
    muxes = {
        r["mux_id"]: r
        for r in _scan_sections((DATA / "mux_layout.toml").read_text(), "[[mux]]")
    }
    dispatch = _arm_dispatch()
    fields = manifest["fields"].split(",")
    sep = manifest.get("field_sep", "|")
    join = manifest.get("body_join", "\n")
    lines: list[str] = []
    for entry in plan:
        mux_arm, material_arm = _resolve_entry_arms(entry, muxes, dispatch)
        values: dict[str, str] = {
            "plan_index": str(entry["plan_index"]),
            "host_id": entry["host_id"],
            "lane_id": entry["lane_id"],
            "cohort_label": entry["cohort_label"],
            "negotiation_class": entry["negotiation_class"],
            "mux_arm": mux_arm,
            "material_arm": material_arm,
        }
        lines.append(sep.join(values[field] for field in fields))
    body = join.join(lines)
    return _sha256_hex(_plan_hash_preimage(body, compile_generation, prior_digest).encode("utf-8"))


def _seal_digest(rows: list[dict], route_plan: dict) -> str:
    seal = _seal_manifest()
    prefix_fields = [f.strip() for f in seal.get("prefix_fields", "plan_hash").split(",")]
    prefix_sep = seal.get("prefix_sep", "|")
    parts: list[str] = []
    for field in prefix_fields:
        if field == "plan_hash":
            parts.append(route_plan["plan_hash"])
        elif field == "compile_generation":
            parts.append(str(route_plan["compile_generation"]))
    prefix = prefix_sep.join(parts)
    row_body = ",".join(_compact_json_value(r) for r in rows)
    layout = seal.get("body_layout", "{prefix}|[{rows}]")
    body = layout.replace("{prefix}", prefix).replace("{rows}", row_body)
    return _sha256_hex(body.encode("utf-8"))


def _lex_seal_digest(rows: list[dict], route_plan: dict) -> str:
    sorted_rows = sorted(
        rows, key=lambda r: (r["host_id"], r["lane_id"], r["cohort_label"])
    )
    return _seal_digest(sorted_rows, route_plan)


def _execute_plan(plan: list[dict]) -> list[dict]:
    muxes = {
        r["mux_id"]: r
        for r in _scan_sections((DATA / "mux_layout.toml").read_text(), "[[mux]]")
    }
    lanes = {
        r["lane_id"]: r
        for r in _scan_sections((DATA / "lane_layout.toml").read_text(), "[[lane]]")
    }
    dispatch = _arm_dispatch()
    strip_rules = _strip_rules()
    primary = _read_bytes("data/pem_w8/primary.pem")
    secondary = _read_bytes("data/pem_w8/secondary.pem")
    tertiary = _read_bytes("data/pem_w8/tertiary.pem")

    rows: list[dict] = []
    for entry in plan:
        mux_slot = _mux_slot(entry["mux_id"], entry["probe_kind"], muxes)
        material_arm = _resolve_arm(dispatch, entry["dispatch_id"], mux_slot)
        local_material = _select_material(material_arm, primary, secondary, tertiary)
        local_epoch = _epoch_for_material(material_arm, local_material)
        remote_material, rewrite_count = _simulate_remote(
            entry["lane_id"], local_material, primary, lanes, strip_rules
        )
        remote_epoch = _remote_epoch(material_arm, remote_material, rewrite_count)
        rows.append(
            {
                "host_id": entry["host_id"],
                "lane_id": entry["lane_id"],
                "cohort_label": entry["cohort_label"],
                "plan_index": entry["plan_index"],
                "alpn_code": _negotiate_alpn(
                    entry["negotiation_class"], remote_material, rewrite_count
                ),
                "material_fingerprint": _sha256_hex(remote_material),
                "local_sink_epoch": local_epoch,
                "remote_sink_epoch": remote_epoch,
                "rewrite_count": rewrite_count,
            }
        )
    return rows


def _lane_stamp_hex(
    host_id: str, lane_id: str, cohort_label: str, rewrite_count: int, fingerprint: str
) -> str:
    body = f"{host_id}|{lane_id}|{cohort_label}|{rewrite_count}|{fingerprint}"
    return _sha256_hex(body.encode("utf-8"))


def _journal_chain_digest(
    generation: int,
    prior_digest: str,
    observation_digest: str,
    plan_hash: str,
    lane_stamps: list[dict],
) -> str:
    ordered = [
        {
            "host_id": s["host_id"],
            "lane_id": s["lane_id"],
            "cohort_label": s["cohort_label"],
            "stamp_hex": s["stamp_hex"],
        }
        for s in lane_stamps
    ]
    stamp_body = json.dumps(ordered, separators=(",", ":"))
    body = f"{generation}|{prior_digest}|{observation_digest}|{plan_hash}|{stamp_body}"
    return _sha256_hex(body.encode("utf-8"))


def _derive_expected(
    compile_generation: int = 1, prior_digest: str = "", plan_prior: str = ""
) -> dict:
    plan = _compile_plan()
    plan_hash = _plan_hash(plan, compile_generation, prior_digest=plan_prior)
    path_report = _execute_plan(plan)
    route_plan = {"plan_hash": plan_hash, "compile_generation": compile_generation}
    digest = _seal_digest(path_report, route_plan)
    lane_stamps = [
        {
            "host_id": r["host_id"],
            "lane_id": r["lane_id"],
            "cohort_label": r["cohort_label"],
            "stamp_hex": _lane_stamp_hex(
                r["host_id"],
                r["lane_id"],
                r["cohort_label"],
                r["rewrite_count"],
                r["material_fingerprint"],
            ),
        }
        for r in path_report
    ]
    return {
        "observation_digest": digest,
        "plan_hash": plan_hash,
        "journal_generation": compile_generation,
        "prior_digest": prior_digest,
        "journal_chain_digest": _journal_chain_digest(
            compile_generation, prior_digest, digest, plan_hash, lane_stamps
        ),
        "path_report": path_report,
    }


def _reset_state() -> None:
    for path in (JOURNAL, ROUTE_PLAN):
        if path.exists():
            path.unlink()


def _delete_out() -> None:
    if OUT.exists():
        OUT.unlink()


def _rebuild() -> None:
    subprocess.run(REBUILD, check=True, timeout=600)


def _run_lab() -> None:
    _delete_out()
    subprocess.run(LAB, check=True)


def _load() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8"))


def _row_by(report: dict, host_id: str, lane_id: str, cohort_label: str) -> dict:
    for row in report["path_report"]:
        if (
            row["host_id"] == host_id
            and row["lane_id"] == lane_id
            and row["cohort_label"] == cohort_label
        ):
            return row
    raise KeyError(f"missing row for {host_id}/{lane_id}/{cohort_label}")


@pytest.fixture(scope="session", autouse=True)
def _verifier_clean_state() -> None:
    _reset_state()
    _delete_out()


@pytest.fixture(scope="module")
def _built() -> None:
    _rebuild()


@pytest.fixture()
def report(_built: None) -> dict:
    _reset_state()
    _run_lab()
    return _load()


def test_rho_host_cli_dual_lane_coupling(report: dict) -> None:
    """host-cli alpha direct and proxy lanes must diverge on rewrite while sharing challenge material."""
    secondary_fp = _sha256_hex(_read_bytes("data/pem_w8/secondary.pem"))
    direct = _row_by(report, "host-cli", "direct", "alpha")
    proxy = _row_by(report, "host-cli", "proxy", "alpha")
    assert direct["rewrite_count"] == 0
    assert proxy["rewrite_count"] == 1
    assert direct["local_sink_epoch"] == direct["remote_sink_epoch"]
    assert direct["material_fingerprint"] == secondary_fp
    assert proxy["material_fingerprint"] == secondary_fp
    assert direct["alpn_code"] == ALPN_CODES["challenge"]
    assert proxy["alpn_code"] == ALPN_CODES["challenge"]


def test_tau_beta_proxy_retain_challenge_alpn(report: dict) -> None:
    """beta proxy strip with marker must keep challenge ALPN via alpn_rules retain path."""
    secondary_fp = _sha256_hex(_read_bytes("data/pem_w8/secondary.pem"))
    proxy = _row_by(report, "w7-go", "proxy", "beta")
    assert proxy["rewrite_count"] == 1
    assert proxy["material_fingerprint"] == secondary_fp
    assert proxy["alpn_code"] == ALPN_CODES["challenge"]


def test_kappa_seal_reads_route_plan_cache(report: dict) -> None:
    """observation_digest must seal from route_plan cache prefix and plan order, not lexical sort."""
    plan = _compile_plan()
    rows = _execute_plan(plan)
    cached = _route_plan_cache()
    assert report["plan_hash"] == cached["plan_hash"]
    assert report["observation_digest"] == _seal_digest(rows, cached)
    assert report["observation_digest"] != _lex_seal_digest(rows, cached)


def test_lambda_prior_tail_binds_plan_hash(_built: None) -> None:
    """generation >= 2 plan_hash must bind wal last_digest via plan_manifest prior step."""
    _reset_state()
    _run_lab()
    first = _load()
    _run_lab()
    second = _load()
    plan = _compile_plan()
    assert second["plan_hash"] == _plan_hash(
        plan, 2, prior_digest=first["observation_digest"]
    )
    assert second["prior_digest"] == first["observation_digest"]
    assert second["plan_hash"] != first["plan_hash"]


def test_delta_truncated_recovery_seal_manifest(_built: None) -> None:
    """truncated journal recovery must restore manifest seal and prior-bound plan_hash."""
    _reset_state()
    _run_lab()
    first = _load()
    expected_first = _derive_expected(compile_generation=1)
    assert first["observation_digest"] == expected_first["observation_digest"]

    partial = JOURNAL.read_text(encoding="utf-8")[:TRUNCATION_PROBE_BYTES]
    JOURNAL.write_text(partial, encoding="utf-8")
    _delete_out()
    _run_lab()
    second = _load()
    expected_second = _derive_expected(
        compile_generation=2,
        prior_digest=first["observation_digest"],
        plan_prior=first["observation_digest"],
    )
    assert second["observation_digest"] == expected_second["observation_digest"]
    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    assert journal.get("recovered") is False
    assert journal.get("plan_hash") == expected_second["plan_hash"]


def test_phi_truncated_journal_recovery(_built: None) -> None:
    """truncated run journal must rebuild stamps and restore observation digest."""
    _reset_state()
    _run_lab()
    expected_first = _derive_expected(compile_generation=1)
    first = _load()
    assert first["observation_digest"] == expected_first["observation_digest"]

    partial = JOURNAL.read_text(encoding="utf-8")[:TRUNCATION_PROBE_BYTES]
    JOURNAL.write_text(partial, encoding="utf-8")
    _delete_out()
    _run_lab()
    second = _load()

    expected_second = _derive_expected(
        compile_generation=2,
        prior_digest=first["observation_digest"],
        plan_prior=first["observation_digest"],
    )
    assert second["observation_digest"] == expected_second["observation_digest"]
    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    assert journal.get("recovered") is False
    assert journal.get("plan_hash") == expected_second["plan_hash"]
    assert len(journal.get("lane_stamps", [])) == len(expected_second["path_report"])


def test_sigma_journal_chain_binds_plan_hash(report: dict) -> None:
    """journal_chain_digest must bind cached plan_hash with lane stamps."""
    expected = _derive_expected(compile_generation=1)
    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    assert journal["plan_hash"] == expected["plan_hash"]
    assert report["journal_chain_digest"] == expected["journal_chain_digest"]
