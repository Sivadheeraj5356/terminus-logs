"""Chain-gated closure report verifier for overlay-patch-closure-skew."""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import subprocess
import tomllib
from pathlib import Path

import pytest

APP = Path("/app")
REPORT = Path("/app/output/closure_report.json")
BIN = Path("/app/bin/cl_publish")
COMPILE = Path("/app/scripts/compile_report.sh")
LAUNCHER = Path("/app/launcher/cl_publish")
MANIFEST = Path("/app/data/tenant_registry.json")
FRAGMENT_PINS = json.loads(
    (Path(__file__).resolve().parent / "fragment_pins.json").read_text(encoding="utf-8")
)
SCHEMA_STUB = Path("/app/stubs/revision_stamp.txt")
RUNTIME = Path("/app/cfg/runtime.toml")

TENANT_FIELDS = frozenset({"effective_digest_hex", "resolved_key_count", "overlay_drifted"})
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SCRATCH_SEQ = 0

SHIPPED_TENANT_IDS = [
    "tenant_alpha",
    "tenant_beta",
    "tenant_gamma",
    "tenant_delta",
    "tenant_epsilon",
    "tenant_zeta",
    "tenant_iota",
    "tenant_kappa",
    "tenant_lambda",
    "tenant_mu",
    "tenant_nu",
    "tenant_omicron",
    "tenant_sigma",
    "tenant_tau",
    "tenant_upsilon",
    "tenant_phi",
]


def _scratch_tenant_id() -> str:
    global _SCRATCH_SEQ
    _SCRATCH_SEQ += 1
    token = hashlib.sha256(str(_SCRATCH_SEQ).encode()).hexdigest()[:10]
    return f"tenant_{token}"


def _coerce_scalar(value: object) -> object:
    if not isinstance(value, str):
        return value
    lowered = value.strip().lower()
    if lowered in {"true", "yes", "on", "1"}:
        return True
    if lowered in {"false", "no", "off", "0", ""}:
        return False
    return value


def _read_fragment(path: Path) -> dict[str, dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, object]] = {}
    for key, spec in raw.items():
        kind = str(spec["kind"])
        value = spec["value"]
        if kind == "scalar":
            value = _coerce_scalar(value)
        out[key] = {"kind": kind, "value": value}
    return out


def _merge_scalar(_current: object, new: object) -> object:
    return new


def _merge_list_replace(_current: object, new: object) -> list[object]:
    return list(new)


def _merge_list_append(current: object, new: object) -> list[object]:
    cur = list(current or [])
    for item in new:
        if not any(item == existing for existing in cur):
            cur.append(item)
    return cur


def _merge_map(current: object, new: object) -> dict[str, object]:
    cur = dict(current or {})
    for key, val in dict(new).items():
        if isinstance(val, dict) and isinstance(cur.get(key), dict):
            cur[key] = _merge_map(cur[key], val)
        else:
            cur[key] = val
    return cur


def _merge_layer(
    base: dict[str, dict[str, object]],
    incoming: dict[str, dict[str, object]],
    list_mode: str = "replace",
) -> dict[str, dict[str, object]]:
    out = {key: {"kind": spec["kind"], "value": spec["value"]} for key, spec in base.items()}
    for key, spec in incoming.items():
        kind = str(spec["kind"])
        val = spec["value"]
        if kind == "tombstone":
            continue
        if kind == "scalar":
            out[key] = {"kind": "scalar", "value": _merge_scalar(out.get(key, {}).get("value"), val)}
        elif kind == "list":
            prev = out.get(key, {}).get("value", []) if out.get(key, {}).get("kind") == "list" else []
            if list_mode == "append" and out.get(key, {}).get("kind") == "list":
                out[key] = {"kind": "list", "value": _merge_list_append(prev, val)}
            else:
                out[key] = {"kind": "list", "value": _merge_list_replace(prev, val)}
        elif kind == "map":
            prev = out.get(key, {}).get("value", {}) if out.get(key, {}).get("kind") == "map" else {}
            out[key] = {"kind": "map", "value": _merge_map(prev, val)}
    return out


def _apply_patch(
    acc: dict[str, dict[str, object]],
    patch: dict[str, dict[str, object]],
    list_mode: str,
    layer_index: int,
) -> dict[str, dict[str, object]]:
    out = {key: {"kind": spec["kind"], "value": spec["value"]} for key, spec in acc.items()}
    for key, spec in patch.items():
        kind = str(spec["kind"])
        val = spec["value"]
        if kind == "tombstone":
            if layer_index >= 1:
                out.pop(key, None)
            continue
        if key in out and str(out[key]["kind"]) != kind:
            out[key] = {"kind": kind, "value": val}
            continue
        if kind == "scalar":
            out[key] = {"kind": "scalar", "value": _merge_scalar(out.get(key, {}).get("value"), val)}
        elif kind == "list":
            if list_mode == "append" and out.get(key, {}).get("kind") == "list":
                out[key] = {
                    "kind": "list",
                    "value": _merge_list_append(out[key]["value"], val),
                }
            else:
                out[key] = {
                    "kind": "list",
                    "value": _merge_list_replace(out.get(key, {}).get("value", []), val),
                }
        elif kind == "map":
            prev = out.get(key, {}).get("value", {}) if out.get(key, {}).get("kind") == "map" else {}
            out[key] = {"kind": "map", "value": _merge_map(prev, val)}
    return out


def _lookup_path(acc: dict[str, dict[str, object]], path: str) -> object:
    if "." not in path:
        entry = acc.get(path)
        return None if entry is None else entry.get("value")
    head, tail = path.split(".", 1)
    entry = acc.get(head)
    if entry is None or str(entry.get("kind")) != "map":
        return None
    cur: object = entry.get("value")
    for part in tail.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _resolve_value(acc: dict[str, dict[str, object]], value: object) -> object:
    if isinstance(value, str) and value.startswith("$ref:"):
        target = value[5:]
        resolved = _lookup_path(acc, target)
        if resolved is None:
            return value
        return _resolve_value(acc, resolved)
    if isinstance(value, list):
        return [_resolve_value(acc, item) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_value(acc, item) for key, item in value.items()}
    return value


def _materialize_aliases(acc: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    out = {
        key: {"kind": spec["kind"], "value": _resolve_value(acc, spec["value"])}
        for key, spec in acc.items()
    }
    changed = True
    while changed:
        changed = False
        for key, spec in out.items():
            resolved = _resolve_value(out, spec["value"])
            if resolved != spec["value"]:
                out[key] = {"kind": str(spec["kind"]), "value": resolved}
                changed = True
    return out


def _digest(acc: dict[str, dict[str, object]]) -> str:
    lines = [
        json.dumps(
            {"key": key, "kind": acc[key]["kind"], "value": acc[key]["value"]},
            separators=(",", ":"),
        )
        for key in sorted(acc)
    ]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def _runtime_list_mode() -> str:
    data = tomllib.loads(RUNTIME.read_text(encoding="utf-8"))
    runtime = data.get("runtime", data)
    return str(runtime.get("default_list_mode", "replace"))


def _expected_tenant(row: dict[str, object]) -> dict[str, object]:
    list_mode = str(row.get("list_mode", _runtime_list_mode()))
    acc = _read_fragment(Path(str(row["base"])))
    if "overlay" in row:
        acc = _merge_layer(acc, _read_fragment(Path(str(row["overlay"]))), list_mode)
    pre_digest = _digest(acc)
    layer_index = 0
    for path_str in row.get("patches", []) or []:
        layer_index += 1
        acc = _apply_patch(acc, _read_fragment(Path(str(path_str))), list_mode, layer_index)
    inline = row.get("tenant_patches")
    if isinstance(inline, dict) and inline:
        layer_index += 1
        patch = {
            key: {"kind": str(spec["kind"]), "value": spec["value"]}
            for key, spec in inline.items()
        }
        acc = _apply_patch(acc, patch, list_mode, layer_index)
    acc = _materialize_aliases(acc)
    effective = _digest(acc)
    return {
        "effective_digest_hex": effective,
        "resolved_key_count": len(acc),
        "overlay_drifted": effective != pre_digest,
    }


def _expected_rows(rows: list[dict[str, object]] | None = None) -> dict[str, dict[str, object]]:
    manifest_rows = rows if rows is not None else json.loads(MANIFEST.read_text(encoding="utf-8"))["tenants"]
    return {str(row["id"]): _expected_tenant(row) for row in manifest_rows}


def _rebuild(script: Path = COMPILE) -> None:
    if REPORT.exists():
        REPORT.unlink()
    proc = subprocess.run([str(script)], cwd="/app", check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert REPORT.is_file(), "compile did not write closure_report.json"


def _doc() -> dict[str, object]:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _schema_mark() -> int:
    return int(SCHEMA_STUB.read_text(encoding="utf-8").strip())


def _manifest_row(tenant_id: str) -> dict[str, object]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return next(row for row in manifest["tenants"] if row["id"] == tenant_id)


def _expected_for_tenant(tenant_id: str) -> dict[str, object]:
    return _expected_tenant(_manifest_row(tenant_id))


@contextlib.contextmanager
def _probe_tenant(
    row: dict[str, object],
    *,
    fragments: dict[Path, str] | None = None,
):
    original_manifest = MANIFEST.read_text(encoding="utf-8")
    original_report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else None
    written: list[Path] = []
    try:
        if fragments:
            for path, body in fragments.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
                written.append(path)
        MANIFEST.write_text(json.dumps({"tenants": [row]}, indent=2) + "\n", encoding="utf-8")
        _rebuild()
        yield _doc()
    finally:
        MANIFEST.write_text(original_manifest, encoding="utf-8")
        for path in written:
            path.unlink(missing_ok=True)
        if original_report is not None:
            REPORT.write_text(original_report, encoding="utf-8")
        elif REPORT.exists():
            REPORT.unlink()


@pytest.fixture(scope="session")
def closure_doc() -> dict[str, object]:
    """Baseline closure report produced by the shipped compile entrypoint."""
    _rebuild()
    return _doc()


# --- Phase 1: build chain (01-06) ---


@pytest.mark.order(1)
@pytest.mark.dependency(name="p01_gomod")
def test_01() -> None:
    """Agent must supply /app/go.mod declaring the clmerge module."""
    text = (APP / "go.mod").read_text(encoding="utf-8")
    assert "clmerge" in text


@pytest.mark.order(2)
@pytest.mark.dependency(name="p02_cmd", depends=["p01_gomod"])
def test_02() -> None:
    """Publisher command sources must live under /app/cmd."""
    sources = list((APP / "cmd").rglob("*.go"))
    assert sources, "expected Go sources under /app/cmd"


@pytest.mark.order(3)
@pytest.mark.dependency(name="p03_internal", depends=["p02_cmd"])
def test_03() -> None:
    """Merge engine packages must live under /app/internal."""
    sources = list((APP / "internal").rglob("*.go"))
    assert sources, "expected Go sources under /app/internal"


@pytest.mark.order(4)
@pytest.mark.dependency(name="p04_binary", depends=["p03_internal"])
def test_04() -> None:
    """compile_report.sh builds and leaves cl_publish at /app/bin/cl_publish."""
    _rebuild()
    assert BIN.is_file()


@pytest.mark.order(5)
@pytest.mark.dependency(name="p05_report", depends=["p04_binary"])
def test_05() -> None:
    """Successful compile emits /app/output/closure_report.json."""
    assert REPORT.is_file()


@pytest.mark.order(6)
@pytest.mark.dependency(name="p06_elf", depends=["p05_report"])
def test_06() -> None:
    """Launcher wrapper runs and cl_publish is a native ELF executable."""
    _rebuild(LAUNCHER)
    assert REPORT.is_file()
    probe = subprocess.run(["file", "/app/bin/cl_publish"], check=True, capture_output=True, text=True)
    assert "ELF" in probe.stdout


# --- Phase 2: schema and field shape (07-11) ---


@pytest.mark.order(7)
@pytest.mark.dependency(depends=["p06_elf"])
def test_07(closure_doc: dict[str, object]) -> None:
    """schema_mark equals the integer in /app/stubs/revision_stamp.txt."""
    assert closure_doc["schema_mark"] == _schema_mark()


@pytest.mark.order(8)
@pytest.mark.dependency(depends=["p06_elf"])
def test_08(closure_doc: dict[str, object]) -> None:
    """Report tenants map keys match every registry id at publish time."""
    manifest_ids = [row["id"] for row in json.loads(MANIFEST.read_text(encoding="utf-8"))["tenants"]]
    assert sorted(closure_doc["tenants"]) == sorted(manifest_ids)


@pytest.mark.order(9)
@pytest.mark.dependency(depends=["p06_elf"])
def test_09(closure_doc: dict[str, object]) -> None:
    """Each tenant block exports only the three documented handoff fields."""
    for block in closure_doc["tenants"].values():
        assert set(block.keys()) == TENANT_FIELDS


@pytest.mark.order(10)
@pytest.mark.dependency(depends=["p06_elf"])
def test_10(closure_doc: dict[str, object]) -> None:
    """effective_digest_hex values are 64-character lowercase hex strings."""
    for block in closure_doc["tenants"].values():
        digest = str(block["effective_digest_hex"])
        assert _HEX64.match(digest)
        int(digest, 16)


@pytest.mark.order(11)
@pytest.mark.dependency(name="p11_schema", depends=["p06_elf"])
def test_11(closure_doc: dict[str, object]) -> None:
    """overlay_drifted is a boolean on every tenant block."""
    for block in closure_doc["tenants"].values():
        assert isinstance(block["overlay_drifted"], bool)


# --- Phase 3: fixture byte pins (12) ---


@pytest.mark.order(12)
@pytest.mark.dependency(name="p12_pins", depends=["p11_schema"])
def test_12() -> None:
    """Pinned fragment bytes under seeds, veils, and amends remain unchanged."""
    for path_str, want in FRAGMENT_PINS.items():
        digest = hashlib.sha256(Path(path_str).read_bytes()).hexdigest()
        assert digest == want, f"fragment tampered: {path_str}"


# --- Phase 4: shipped tenant full rows (13-28) ---


@pytest.mark.order(13)
@pytest.mark.dependency(depends=["p12_pins"])
def test_13(closure_doc: dict[str, object]) -> None:
    """tenant_alpha full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_alpha"] == _expected_for_tenant("tenant_alpha")


@pytest.mark.order(14)
@pytest.mark.dependency(depends=["p12_pins"])
def test_14(closure_doc: dict[str, object]) -> None:
    """tenant_beta full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_beta"] == _expected_for_tenant("tenant_beta")


@pytest.mark.order(15)
@pytest.mark.dependency(depends=["p12_pins"])
def test_15(closure_doc: dict[str, object]) -> None:
    """tenant_gamma full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_gamma"] == _expected_for_tenant("tenant_gamma")


@pytest.mark.order(16)
@pytest.mark.dependency(depends=["p12_pins"])
def test_16(closure_doc: dict[str, object]) -> None:
    """tenant_delta full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_delta"] == _expected_for_tenant("tenant_delta")


@pytest.mark.order(17)
@pytest.mark.dependency(depends=["p12_pins"])
def test_17(closure_doc: dict[str, object]) -> None:
    """tenant_epsilon full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_epsilon"] == _expected_for_tenant("tenant_epsilon")


@pytest.mark.order(18)
@pytest.mark.dependency(depends=["p12_pins"])
def test_18(closure_doc: dict[str, object]) -> None:
    """tenant_zeta full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_zeta"] == _expected_for_tenant("tenant_zeta")


@pytest.mark.order(19)
@pytest.mark.dependency(depends=["p12_pins"])
def test_19(closure_doc: dict[str, object]) -> None:
    """tenant_iota full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_iota"] == _expected_for_tenant("tenant_iota")


@pytest.mark.order(20)
@pytest.mark.dependency(depends=["p12_pins"])
def test_20(closure_doc: dict[str, object]) -> None:
    """tenant_kappa full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_kappa"] == _expected_for_tenant("tenant_kappa")


@pytest.mark.order(21)
@pytest.mark.dependency(depends=["p12_pins"])
def test_21(closure_doc: dict[str, object]) -> None:
    """tenant_lambda full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_lambda"] == _expected_for_tenant("tenant_lambda")


@pytest.mark.order(22)
@pytest.mark.dependency(depends=["p12_pins"])
def test_22(closure_doc: dict[str, object]) -> None:
    """tenant_mu full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_mu"] == _expected_for_tenant("tenant_mu")


@pytest.mark.order(23)
@pytest.mark.dependency(depends=["p12_pins"])
def test_23(closure_doc: dict[str, object]) -> None:
    """tenant_nu full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_nu"] == _expected_for_tenant("tenant_nu")


@pytest.mark.order(24)
@pytest.mark.dependency(depends=["p12_pins"])
def test_24(closure_doc: dict[str, object]) -> None:
    """tenant_omicron full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_omicron"] == _expected_for_tenant("tenant_omicron")


@pytest.mark.order(25)
@pytest.mark.dependency(depends=["p12_pins"])
def test_25(closure_doc: dict[str, object]) -> None:
    """tenant_sigma full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_sigma"] == _expected_for_tenant("tenant_sigma")


@pytest.mark.order(26)
@pytest.mark.dependency(depends=["p12_pins"])
def test_26(closure_doc: dict[str, object]) -> None:
    """tenant_tau full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_tau"] == _expected_for_tenant("tenant_tau")


@pytest.mark.order(27)
@pytest.mark.dependency(depends=["p12_pins"])
def test_27(closure_doc: dict[str, object]) -> None:
    """tenant_upsilon full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_upsilon"] == _expected_for_tenant("tenant_upsilon")


@pytest.mark.order(28)
@pytest.mark.dependency(name="p28_shipped", depends=["p12_pins"])
def test_28(closure_doc: dict[str, object]) -> None:
    """tenant_phi full block matches the reference closure oracle."""
    assert closure_doc["tenants"]["tenant_phi"] == _expected_for_tenant("tenant_phi")


# --- Phase 5: behavioral probes (29-40) ---


@pytest.mark.order(29)
@pytest.mark.dependency(depends=["p28_shipped"])
def test_29() -> None:
    """Append list_mode keeps inherited order and appends unseen patch entries."""
    tenant_id = _scratch_tenant_id()
    base_path = Path(f"/app/data/seeds/{tenant_id}.json")
    row = {
        "id": tenant_id,
        "base": str(base_path),
        "list_mode": "append",
        "tenant_patches": {"rollout": {"kind": "list", "value": ["gamma", "shared"]}},
    }
    fragments = {
        base_path: json.dumps(
            {"rollout": {"kind": "list", "value": ["alpha", "shared"]}},
            indent=2,
        )
        + "\n",
    }
    with _probe_tenant(row, fragments=fragments) as report:
        assert report["tenants"][tenant_id] == _expected_tenant(row)


@pytest.mark.order(30)
@pytest.mark.dependency(depends=["p28_shipped"])
def test_30() -> None:
    """Patch-layer tombstones remove keys from layer index one onward."""
    tenant_id = _scratch_tenant_id()
    base_path = Path(f"/app/data/seeds/{tenant_id}.json")
    patch_path = Path(f"/app/data/amends/{tenant_id}.json")
    row = {"id": tenant_id, "base": str(base_path), "patches": [str(patch_path)]}
    fragments = {
        base_path: json.dumps({"drop_me": {"kind": "scalar", "value": "stay"}}, indent=2) + "\n",
        patch_path: json.dumps({"drop_me": {"kind": "tombstone", "value": True}}, indent=2) + "\n",
    }
    with _probe_tenant(row, fragments=fragments) as report:
        assert report["tenants"][tenant_id] == _expected_tenant(row)


@pytest.mark.order(31)
@pytest.mark.dependency(depends=["p28_shipped"])
def test_31() -> None:
    """Alias references resolve before the effective digest is computed."""
    tenant_id = _scratch_tenant_id()
    base_path = Path(f"/app/data/seeds/{tenant_id}.json")
    row = {"id": tenant_id, "base": str(base_path)}
    fragments = {
        base_path: json.dumps(
            {
                "target": {"kind": "scalar", "value": "resolved-value"},
                "alias": {"kind": "scalar", "value": "$ref:target"},
            },
            indent=2,
        )
        + "\n",
    }
    with _probe_tenant(row, fragments=fragments) as report:
        assert report["tenants"][tenant_id] == _expected_tenant(row)


@pytest.mark.order(32)
@pytest.mark.dependency(depends=["p28_shipped"])
def test_32() -> None:
    """Map merge recurses into nested dicts instead of replacing whole subtrees."""
    tenant_id = _scratch_tenant_id()
    base_path = Path(f"/app/data/seeds/{tenant_id}.json")
    row = {
        "id": tenant_id,
        "base": str(base_path),
        "tenant_patches": {
            "experiments": {"kind": "map", "value": {"nested": {"y": 9, "only_manifest": True}}}
        },
    }
    fragments = {
        base_path: json.dumps(
            {"experiments": {"kind": "map", "value": {"nested": {"x": 3, "keep": "bundle"}}}},
            indent=2,
        )
        + "\n",
    }
    with _probe_tenant(row, fragments=fragments) as report:
        assert report["tenants"][tenant_id] == _expected_tenant(row)


@pytest.mark.order(33)
@pytest.mark.dependency(depends=["p28_shipped"])
def test_33() -> None:
    """A patch layer that changes key kind replaces the entire entry."""
    tenant_id = _scratch_tenant_id()
    base_path = Path(f"/app/data/seeds/{tenant_id}.json")
    row = {
        "id": tenant_id,
        "base": str(base_path),
        "tenant_patches": {"mode_flag": {"kind": "list", "value": ["manifest-list"]}},
    }
    fragments = {
        base_path: json.dumps({"mode_flag": {"kind": "scalar", "value": "bundle-scalar"}}, indent=2) + "\n",
    }
    with _probe_tenant(row, fragments=fragments) as report:
        assert report["tenants"][tenant_id] == _expected_tenant(row)


@pytest.mark.order(34)
@pytest.mark.dependency(depends=["p28_shipped"])
def test_34() -> None:
    """Manifest file patches run before inline tenant_patches on the same row."""
    tenant_id = _scratch_tenant_id()
    base_path = Path(f"/app/data/seeds/{tenant_id}.json")
    patch_path = Path(f"/app/data/amends/{tenant_id}.json")
    row = {
        "id": tenant_id,
        "base": str(base_path),
        "patches": [str(patch_path)],
        "tenant_patches": {"winner": {"kind": "scalar", "value": "inline-layer"}},
    }
    fragments = {
        base_path: json.dumps({"winner": {"kind": "scalar", "value": "base"}}, indent=2) + "\n",
        patch_path: json.dumps({"winner": {"kind": "scalar", "value": "file-layer"}}, indent=2) + "\n",
    }
    with _probe_tenant(row, fragments=fragments) as report:
        want = _expected_tenant(row)
        assert report["tenants"][tenant_id] == want


@pytest.mark.order(35)
@pytest.mark.dependency(depends=["p28_shipped"])
def test_35() -> None:
    """List union keeps integer and string forms of the same digits as separate items."""
    tenant_id = _scratch_tenant_id()
    base_path = Path(f"/app/data/seeds/{tenant_id}.json")
    overlay_path = Path(f"/app/data/veils/{tenant_id}.json")
    row = {
        "id": tenant_id,
        "base": str(base_path),
        "overlay": str(overlay_path),
        "list_mode": "append",
    }
    fragments = {
        base_path: json.dumps({"codes": {"kind": "list", "value": [42, "alpha"]}}, indent=2) + "\n",
        overlay_path: json.dumps({"codes": {"kind": "list", "value": ["42", "beta"]}}, indent=2) + "\n",
    }
    with _probe_tenant(row, fragments=fragments) as report:
        assert report["tenants"][tenant_id] == _expected_tenant(row)


@pytest.mark.order(36)
@pytest.mark.dependency(depends=["p28_shipped"])
def test_36() -> None:
    """Digest rows preserve nested map insertion order inside value payloads."""
    tenant_id = _scratch_tenant_id()
    base_path = Path(f"/app/data/seeds/{tenant_id}.json")
    row = {"id": tenant_id, "base": str(base_path)}
    fragments = {
        base_path: json.dumps(
            {
                "ordered_map": {
                    "kind": "map",
                    "value": {"z_last": 1, "a_first": 2, "m_mid": 3},
                }
            },
            indent=2,
        )
        + "\n",
    }
    with _probe_tenant(row, fragments=fragments) as report:
        want = _expected_tenant(row)
        assert report["tenants"][tenant_id]["effective_digest_hex"] == want["effective_digest_hex"]


@pytest.mark.order(37)
@pytest.mark.dependency(depends=["p28_shipped"])
def test_37() -> None:
    """overlay_drifted compares effective digest against the pre-patch fused snapshot."""
    tenant_id = _scratch_tenant_id()
    base_path = Path(f"/app/data/seeds/{tenant_id}.json")
    overlay_path = Path(f"/app/data/veils/{tenant_id}.json")
    patch_path = Path(f"/app/data/amends/{tenant_id}.json")
    row = {
        "id": tenant_id,
        "base": str(base_path),
        "overlay": str(overlay_path),
        "patches": [str(patch_path)],
    }
    fragments = {
        base_path: json.dumps({"root": {"kind": "scalar", "value": "base"}}, indent=2) + "\n",
        overlay_path: json.dumps({"lane": {"kind": "scalar", "value": "overlay"}}, indent=2) + "\n",
        patch_path: json.dumps({"root": {"kind": "scalar", "value": "patch"}}, indent=2) + "\n",
    }
    with _probe_tenant(row, fragments=fragments) as report:
        assert report["tenants"][tenant_id] == _expected_tenant(row)


@pytest.mark.order(38)
@pytest.mark.dependency(depends=["p28_shipped"])
def test_38() -> None:
    """$ref paths with multiple dot segments walk nested map payloads."""
    tenant_id = _scratch_tenant_id()
    base_path = Path(f"/app/data/seeds/{tenant_id}.json")
    row = {"id": tenant_id, "base": str(base_path)}
    fragments = {
        base_path: json.dumps(
            {
                "nested": {"kind": "map", "value": {"leaf": {"inner": "probe-target"}}},
                "deep_alias": {"kind": "scalar", "value": "$ref:nested.leaf.inner"},
            },
            indent=2,
        )
        + "\n",
    }
    with _probe_tenant(row, fragments=fragments) as report:
        assert report["tenants"][tenant_id] == _expected_tenant(row)


@pytest.mark.order(39)
@pytest.mark.dependency(depends=["p28_shipped"])
def test_39() -> None:
    """Tombstone entries during overlay fuse are ignored without removing keys."""
    tenant_id = _scratch_tenant_id()
    base_path = Path(f"/app/data/seeds/{tenant_id}.json")
    overlay_path = Path(f"/app/data/veils/{tenant_id}.json")
    row = {"id": tenant_id, "base": str(base_path), "overlay": str(overlay_path)}
    fragments = {
        base_path: json.dumps({"keep": {"kind": "scalar", "value": "base"}}, indent=2) + "\n",
        overlay_path: json.dumps({"keep": {"kind": "tombstone", "value": True}}, indent=2) + "\n",
    }
    with _probe_tenant(row, fragments=fragments) as report:
        assert report["tenants"][tenant_id] == _expected_tenant(row)


@pytest.mark.order(40)
@pytest.mark.dependency(name="p40_probes", depends=["p28_shipped"])
def test_40() -> None:
    """Alias hops that reference other alias keys resolve through fixpoint materialization."""
    tenant_id = _scratch_tenant_id()
    base_path = Path(f"/app/data/seeds/{tenant_id}.json")
    row = {"id": tenant_id, "base": str(base_path)}
    fragments = {
        base_path: json.dumps(
            {
                "hop_a": {"kind": "scalar", "value": "$ref:hop_b"},
                "hop_b": {"kind": "scalar", "value": "$ref:hop_c"},
                "hop_c": {"kind": "scalar", "value": "chain-final"},
            },
            indent=2,
        )
        + "\n",
    }
    with _probe_tenant(row, fragments=fragments) as report:
        assert report["tenants"][tenant_id] == _expected_tenant(row)


# --- Phase 6: cross-field invariants (41-44) ---


@pytest.mark.order(41)
@pytest.mark.dependency(depends=["p40_probes"])
def test_41(closure_doc: dict[str, object]) -> None:
    """tenant_alpha shipped row matches the independent reference oracle."""
    block = closure_doc["tenants"]["tenant_alpha"]
    want = _expected_for_tenant("tenant_alpha")
    assert block == want


@pytest.mark.order(42)
@pytest.mark.dependency(depends=["p40_probes"])
def test_42(closure_doc: dict[str, object]) -> None:
    """tenant_beta shipped row matches the independent reference oracle."""
    block = closure_doc["tenants"]["tenant_beta"]
    want = _expected_for_tenant("tenant_beta")
    assert block == want


@pytest.mark.order(43)
@pytest.mark.dependency(depends=["p40_probes"])
def test_43(closure_doc: dict[str, object]) -> None:
    """resolved_key_count is a positive integer on every shipped tenant block."""
    for tenant_id in SHIPPED_TENANT_IDS:
        block = closure_doc["tenants"][tenant_id]
        count = block["resolved_key_count"]
        assert isinstance(count, int)
        assert count > 0
        assert count == _expected_for_tenant(tenant_id)["resolved_key_count"]


@pytest.mark.order(44)
@pytest.mark.dependency(name="p44_inv", depends=["p40_probes"])
def test_44(closure_doc: dict[str, object]) -> None:
    """effective digest and drift flag stay coupled on every shipped tenant."""
    for tenant_id in SHIPPED_TENANT_IDS:
        block = closure_doc["tenants"][tenant_id]
        want = _expected_for_tenant(tenant_id)
        assert block["effective_digest_hex"] == want["effective_digest_hex"]
        assert block["overlay_drifted"] == want["overlay_drifted"]


# --- Phase 7: runtime reload and stability (45-47) ---


@pytest.mark.order(45)
@pytest.mark.dependency(depends=["p44_inv"])
def test_45() -> None:
    """schema_mark tracks revision_stamp.txt across consecutive rebuild invocations."""
    original_stub = SCHEMA_STUB.read_text(encoding="utf-8")
    try:
        _rebuild()
        first = _doc()["schema_mark"]
        assert first == int(original_stub.strip())
        SCHEMA_STUB.write_text("8\n", encoding="utf-8")
        _rebuild()
        second = _doc()["schema_mark"]
        assert second == 8
    finally:
        SCHEMA_STUB.write_text(original_stub, encoding="utf-8")
        _rebuild()


@pytest.mark.order(46)
@pytest.mark.dependency(depends=["p44_inv"])
def test_46() -> None:
    """Appending a tenant to the registry exposes it on the next rebuild."""
    original_manifest = MANIFEST.read_text(encoding="utf-8")
    tenant_id = _scratch_tenant_id()
    base_path = Path(f"/app/data/seeds/{tenant_id}.json")
    row = {"id": tenant_id, "base": str(base_path)}
    try:
        base_path.write_text(
            json.dumps({"solo": {"kind": "scalar", "value": "only"}}, indent=2) + "\n",
            encoding="utf-8",
        )
        alpha_row = _manifest_row("tenant_alpha")
        MANIFEST.write_text(json.dumps({"tenants": [alpha_row]}, indent=2) + "\n", encoding="utf-8")
        _rebuild()
        first = _doc()
        assert set(first["tenants"]) == {"tenant_alpha"}
        MANIFEST.write_text(
            json.dumps({"tenants": [alpha_row, row]}, indent=2) + "\n",
            encoding="utf-8",
        )
        _rebuild()
        second = _doc()
        assert tenant_id in second["tenants"]
        assert second["tenants"][tenant_id] == _expected_tenant(row)
    finally:
        MANIFEST.write_text(original_manifest, encoding="utf-8")
        base_path.unlink(missing_ok=True)
        _rebuild()


@pytest.mark.order(47)
@pytest.mark.dependency(depends=["p44_inv"])
def test_47() -> None:
    """Back-to-back compile invocations emit identical closure reports."""
    _rebuild()
    first = _doc()
    _rebuild()
    second = _doc()
    assert first == second


# --- Phase 8: finale matrix (48-50) ---


@pytest.mark.order(48)
@pytest.mark.dependency(depends=["p44_inv"])
def test_48() -> None:
    """Full shipped tenant matrix matches the reference closure oracle."""
    _rebuild()
    report = _doc()
    expected = _expected_rows()
    for tenant_id in SHIPPED_TENANT_IDS:
        assert report["tenants"][tenant_id] == expected[tenant_id]


@pytest.mark.order(49)
@pytest.mark.dependency(depends=["p44_inv"])
def test_49() -> None:
    """Launcher and compile agree on a dynamic single-tenant probe."""
    tenant_id = _scratch_tenant_id()
    base_path = Path(f"/app/data/seeds/{tenant_id}.json")
    row = {"id": tenant_id, "base": str(base_path)}
    original_manifest = MANIFEST.read_text(encoding="utf-8")
    original_report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else None
    try:
        base_path.write_text(
            json.dumps({"dyn": {"kind": "scalar", "value": "probe"}}, indent=2) + "\n",
            encoding="utf-8",
        )
        MANIFEST.write_text(json.dumps({"tenants": [row]}, indent=2) + "\n", encoding="utf-8")
        _rebuild(COMPILE)
        via_compile = _doc()
        _rebuild(LAUNCHER)
        via_launcher = _doc()
        want = _expected_tenant(row)
        assert via_compile["tenants"][tenant_id] == want
        assert via_launcher == via_compile
    finally:
        MANIFEST.write_text(original_manifest, encoding="utf-8")
        base_path.unlink(missing_ok=True)
        if original_report is not None:
            REPORT.write_text(original_report, encoding="utf-8")
        elif REPORT.exists():
            REPORT.unlink(missing_ok=True)
        _rebuild()


@pytest.mark.order(50)
@pytest.mark.dependency(depends=["p44_inv"])
def test_50() -> None:
    """Every manifest tenant block matches the independent reference oracle."""
    _rebuild()
    report = _doc()
    for row in json.loads(MANIFEST.read_text(encoding="utf-8"))["tenants"]:
        tenant_id = str(row["id"])
        assert report["tenants"][tenant_id] == _expected_tenant(row)
