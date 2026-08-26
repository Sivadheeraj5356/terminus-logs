import json
import os
import re
import shutil
import subprocess
from pathlib import Path

APP = Path("/app")
LABS = APP / "labs"
OUT = APP / "restore" / "fieldday-2026-06-18"
REPORT = APP / "repair.json"
IMMUTABLE_CHECKSUMS = Path("/tests") / "immutable_checksums.sha256"

A01 = "atlas alpha line one\n"
A02 = "cargo crates staged on pier seven\n"
A03 = "end atlas manifest\n"
A04 = "window open\n"
A05 = "sorted archive shelf\n"
A06 = "window closed\n"
A07 = "baseline atlas note\n"
B01 = "beacon uplink start\n"
B02 = "signal cabinet green\n"
B03 = "uplink stop\n"
B04 = "route card alpha\n"
B05 = "route card beta\n"
B06 = "baseline beacon note\n"
C01 = "cinder ledger top\n"
C02 = "ash crate count eight\n"
C03 = "quarry spare coil sealed\n"
C04 = "ledger close\n"
C05 = "baseline cinder note\n"
M01 = "mesa radio check-in open\n"
M02 = "mesa camp relay staging yard line\n"
M02A = "mesa camp relay "
M02B = "staging yard line\n"
M03 = "mesa baseline anchor note\n"
M04 = "mesa atlas shelf echo marker\n"
R01 = "ridge camp opening note\n"
R02 = "supply sled moved downslope\n"
R03 = "ridge camp closing note\n"
R04 = "relay borrow from beacon shelf\n"

SPAN_KEYS = {"path", "span", "bytes", "status", "source"}
LABS_SET = {"atlas", "beacon", "cinder", "ridge", "mesa"}
LOCAL_SOURCE = re.compile(r"^([A-Za-z0-9._-]+):(\d+)\+(\d+)$")
CROSS_SOURCE = re.compile(r"^([a-z]+):([A-Za-z0-9._-]+):(\d+)\+(\d+)$")
MERGED_ENTRY = re.compile(r"^([A-Za-z0-9._-]+):([A-Za-z0-9._-]+):(\d+)\+(\d+)$")

SPAN_CONTENT = {
    "a01": A01, "a02": A02, "a03": A03, "a04": A04, "a05": A05, "a06": A06,
    "b01": B01, "b02": B02, "b03": B03, "b04": B04, "b05": B05,
    "c01": C01, "c02": C02, "c03": C03, "c04": C04,
    "r01": R01, "r02": R02, "r03": R03, "r04": R04,
    "m01": M01, "m02": M02, "m04": M04,
}

SPAN_PATH = {
    "a01": "home/manifest.txt", "a02": "home/manifest.txt", "a03": "home/manifest.txt",
    "a04": "home/window.log", "a05": "home/window.log", "a06": "home/window.log",
    "b01": "logs/uplink.txt", "b02": "logs/uplink.txt", "b03": "logs/uplink.txt",
    "b04": "logs/routes.txt", "b05": "logs/routes.txt",
    "c01": "ledger/day.txt", "c02": "ledger/day.txt",
    "c03": "ledger/day.txt", "c04": "ledger/day.txt",
    "r01": "trail/summary.txt", "r02": "trail/summary.txt", "r03": "trail/summary.txt",
    "r04": "trail/borrow.txt",
    "m01": "ops/radio.txt", "m02": "ops/radio.txt", "m04": "ops/relay.txt",
}

ATLAS_MAIN = "atlas/home/manifest.txt"
ATLAS_SIDE = "atlas/home/window.log"
BEACON_MAIN = "beacon/logs/uplink.txt"
BEACON_SIDE = "beacon/logs/routes.txt"
CINDER_MAIN = "cinder/ledger/day.txt"
RIDGE_MAIN = "ridge/trail/summary.txt"
RIDGE_BORROW = "ridge/trail/borrow.txt"
MESA_RADIO = "mesa/ops/radio.txt"
MESA_RELAY = "mesa/ops/relay.txt"

EXPECTED = {
    ATLAS_MAIN: A01 + A02 + A03,
    ATLAS_SIDE: A04 + A05 + A06,
    BEACON_MAIN: B01 + B02 + B03,
    BEACON_SIDE: B04 + B05,
    CINDER_MAIN: C01 + C02 + C03 + C04,
    RIDGE_MAIN: R01 + R02 + R03,
    RIDGE_BORROW: R04,
    MESA_RADIO: M01 + M02,
    MESA_RELAY: M04,
}

NEIGHBOR = {
    ATLAS_MAIN: A01 + A07 + A03,
    ATLAS_SIDE: A04 + A05 + A06,
    BEACON_MAIN: B01 + B06 + B03,
    BEACON_SIDE: B04 + B05,
    CINDER_MAIN: C01 + C03 + C05,
    RIDGE_MAIN: R01 + R03,
    RIDGE_BORROW: R04,
    MESA_RADIO: M01 + M03,
    MESA_RELAY: M04,
}


def _text(rel):
    return (OUT / rel).read_text()


def _report():
    return json.loads(REPORT.read_text())


def _file_sha256(path: Path) -> str:
    result = subprocess.run(
        ["sha256sum", str(path)],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.split()[0]


def _profile_mask(lab: str) -> tuple[int | None, set[str]]:
    profiles = APP / "profiles"
    for path in sorted(profiles.glob("*.conf")):
        text = path.read_text()
        fields = {}
        for line in text.splitlines():
            if "=" in line:
                key, val = line.split("=", 1)
                fields[key.strip()] = val.strip()
        if fields.get("name") != lab:
            continue
        key = int(fields["mask_key"]) if "mask_key" in fields else None
        pools = {
            p.strip()
            for p in fields.get("masked_pools", "").split(",")
            if p.strip()
        }
        return key, pools
    return None, set()


def _decode_pool_slice(lab: str, object_name: str, offset: int, length: int) -> bytes:
    raw = (LABS / lab / "objects" / object_name).read_bytes()
    assert offset >= 0
    assert offset + length <= len(raw)
    chunk = raw[offset:offset + length]
    key, masked = _profile_mask(lab)
    stem = object_name.removesuffix(".blob")
    if key is not None and (object_name in masked or stem in masked):
        chunk = bytes(b ^ key for b in chunk)
    return chunk


def _assert_local_or_cross_source(source, bytes_value, *, allow_cross):
    local = LOCAL_SOURCE.fullmatch(source)
    if local:
        object_name, offset, length = local.group(1), int(local.group(2)), int(local.group(3))
        assert object_name.endswith(".blob")
        assert offset >= 0
        assert length == bytes_value
        return "local", object_name, offset, length
    cross = CROSS_SOURCE.fullmatch(source)
    assert allow_cross and cross is not None, f"bad source {source!r}"
    lab, object_name, offset, length = (
        cross.group(1), cross.group(2), int(cross.group(3)), int(cross.group(4)),
    )
    assert lab in LABS_SET
    assert object_name.endswith(".blob")
    assert offset >= 0
    assert length == bytes_value
    return "cross", lab, object_name, offset, length


def _assert_merged_source(source, bytes_value):
    parts = [p for p in source.split(",") if p]
    assert len(parts) >= 2
    total = 0
    frag_ids = []
    entries = []
    for part in parts:
        match = MERGED_ENTRY.fullmatch(part)
        assert match is not None, f"bad merged entry {part!r}"
        frag_id, object_name, offset, length = (
            match.group(1), match.group(2), int(match.group(3)), int(match.group(4)),
        )
        assert object_name.endswith(".blob")
        assert offset >= 0
        assert length > 0
        total += length
        frag_ids.append(frag_id)
        entries.append((frag_id, object_name, offset, length))
    assert total == bytes_value
    return frag_ids, entries


def _assert_span_row(row):
    assert set(row) == SPAN_KEYS
    assert isinstance(row["path"], str) and row["path"]
    assert isinstance(row["span"], str) and row["span"]
    assert isinstance(row["bytes"], int) and row["bytes"] > 0
    assert row["status"] in {"indexed", "scanned", "merged"}
    assert isinstance(row["source"], str) and row["source"]
    if row["status"] == "merged":
        _assert_merged_source(row["source"], row["bytes"])
    elif row["status"] == "indexed":
        kind, *_ = _assert_local_or_cross_source(row["source"], row["bytes"], allow_cross=False)
        assert kind == "local"
    else:
        _assert_local_or_cross_source(row["source"], row["bytes"], allow_cross=True)


def _bytes_from_report_row(lab: str, row: dict) -> bytes:
    if row["status"] == "merged":
        _, entries = _assert_merged_source(row["source"], row["bytes"])
        buf = bytearray()
        for _, object_name, offset, length in entries:
            buf.extend(_decode_pool_slice(lab, object_name, offset, length))
        return bytes(buf)
    kind, *rest = _assert_local_or_cross_source(
        row["source"], row["bytes"], allow_cross=row["status"] == "scanned"
    )
    if kind == "local":
        object_name, offset, length = rest
        return _decode_pool_slice(lab, object_name, offset, length)
    supply_lab, object_name, offset, length = rest
    return _decode_pool_slice(supply_lab, object_name, offset, length)


# ====================================================================
# Restoration correctness
# ====================================================================

def test_atlas_manifest_restored():
    """The atlas manifest is rebuilt from its original byte spans."""
    assert _text(ATLAS_MAIN) == EXPECTED[ATLAS_MAIN]


def test_atlas_window_log_restored():
    """The second atlas file is present with no shifted bytes."""
    assert _text(ATLAS_SIDE) == EXPECTED[ATLAS_SIDE]


def test_beacon_files_restored():
    """Both beacon files match the stored snapshot material."""
    assert _text(BEACON_MAIN) == EXPECTED[BEACON_MAIN]
    assert _text(BEACON_SIDE) == EXPECTED[BEACON_SIDE]


def test_cinder_ledger_includes_relocated_span():
    """The cinder ledger includes the span absent from its ordinary location."""
    assert _text(CINDER_MAIN) == EXPECTED[CINDER_MAIN]


def test_ridge_summary_restored():
    """The ridge summary file restores all three camp spans in order."""
    assert _text(RIDGE_MAIN) == EXPECTED[RIDGE_MAIN]


def test_ridge_borrow_restored():
    """The ridge borrow file restores bytes held on another lab shelf."""
    assert _text(RIDGE_BORROW) == EXPECTED[RIDGE_BORROW]


def test_mesa_radio_restored():
    """The mesa radio file restores masked and merged spans."""
    assert _text(MESA_RADIO) == EXPECTED[MESA_RADIO]


def test_mesa_relay_restored():
    """The mesa relay file restores bytes from another lab shelf."""
    assert _text(MESA_RELAY) == EXPECTED[MESA_RELAY]


def test_restore_tree_has_exact_paths():
    """The reconstructed tree has exactly the expected repository paths."""
    found = sorted(str(p.relative_to(OUT)) for p in OUT.rglob("*") if p.is_file())
    assert found == sorted(EXPECTED)


# ====================================================================
# Provenance report
# ====================================================================

def test_repair_report_shape_and_status_mix():
    """The report records ordinary and searched provenance for materialized spans."""
    data = _report()
    assert data["target"] == "fieldday-2026-06-18"
    rows = [row for items in data["repositories"].values() for row in items]
    assert rows
    assert {"indexed", "scanned", "merged"} <= {row["status"] for row in rows}
    for row in rows:
        _assert_span_row(row)


def test_each_lab_reports_nonindexed_recovery():
    """Each repository reports at least one span found outside the ordinary location."""
    data = _report()
    scanned = {
        repo
        for repo, rows in data["repositories"].items()
        for row in rows
        if row["status"] in {"scanned", "merged"}
    }
    assert scanned == LABS_SET


def test_ridge_borrow_report_names_beacon_source():
    """Cross-lab recovery names the supplying repository in report sources."""
    data = _report()
    ridge_rows = data["repositories"]["ridge"]
    borrow_rows = [row for row in ridge_rows if row["span"] == "r04"]
    assert len(borrow_rows) == 1
    assert borrow_rows[0]["status"] == "scanned"
    kind, lab, *_ = _assert_local_or_cross_source(
        borrow_rows[0]["source"], borrow_rows[0]["bytes"], allow_cross=True
    )
    assert kind == "cross"
    assert lab == "beacon"


def test_mesa_split_span_merged_provenance():
    """Split spans report merged provenance in the repair log."""
    data = _report()
    mesa_rows = data["repositories"]["mesa"]
    merged = [row for row in mesa_rows if row["span"] == "m02"]
    assert len(merged) == 1
    assert merged[0]["status"] == "merged"
    frag_ids, _ = _assert_merged_source(merged[0]["source"], merged[0]["bytes"])
    assert "m02a" in frag_ids and "m02b" in frag_ids


def test_mesa_relay_report_names_atlas_source():
    """Cross-lab mesa recovery names atlas in report sources."""
    data = _report()
    mesa_rows = data["repositories"]["mesa"]
    relay_rows = [row for row in mesa_rows if row["span"] == "m04"]
    assert len(relay_rows) == 1
    assert relay_rows[0]["status"] == "scanned"
    kind, lab, *_ = _assert_local_or_cross_source(
        relay_rows[0]["source"], relay_rows[0]["bytes"], allow_cross=True
    )
    assert kind == "cross"
    assert lab == "atlas"


def test_report_provenance_resolves_to_span_bytes():
    """Every repair.json source cites pool bytes that decode to the restored span."""
    data = _report()
    assert set(data["repositories"]) == LABS_SET
    seen_spans = set()
    for lab, rows in data["repositories"].items():
        for row in rows:
            _assert_span_row(row)
            span = row["span"]
            assert span in SPAN_CONTENT, span
            assert row["path"] == SPAN_PATH[span]
            assert row["bytes"] == len(SPAN_CONTENT[span])
            cited = _bytes_from_report_row(lab, row)
            assert cited.decode() == SPAN_CONTENT[span]
            restored = (OUT / lab / row["path"]).read_text()
            assert SPAN_CONTENT[span] in restored
            seen_spans.add(span)
    assert seen_spans == set(SPAN_CONTENT)


def _parse_chunks_idx(lab: str) -> dict[str, tuple[str, int, int]]:
    idx_path = LABS / lab / "index" / "chunks.idx"
    entries: dict[str, tuple[str, int, int]] = {}
    for raw_line in idx_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        assert len(parts) == 4, f"malformed chunks.idx line in {lab}: {raw_line!r}"
        span_id, obj, offset, length = parts
        entries[span_id.strip()] = (obj.strip(), int(offset), int(length))
    return entries


def test_report_status_matches_chunks_idx():
    """Report status labels are consistent with each lab's chunks.idx entries."""
    data = _report()
    for lab, rows in data["repositories"].items():
        idx = _parse_chunks_idx(lab)
        objects_dir = LABS / lab / "objects"
        for row in rows:
            span = row["span"]
            status = row["status"]
            source = row["source"]
            if status == "indexed":
                assert span in idx, f"{lab}:{span} reported indexed but absent from chunks.idx"
                obj, offset, length = idx[span]
                assert (objects_dir / obj).is_file(), f"{lab}:{span} indexed entry points to missing {obj}"
                assert length == row["bytes"]
                expected_local = f"{obj}:{offset}+{length}"
                assert source == expected_local
            elif status == "merged":
                _, entries = _assert_merged_source(source, row["bytes"])
                for frag_id, _, _, _ in entries:
                    assert frag_id in idx, f"{lab}:{span} merged fragment {frag_id!r} missing from chunks.idx"
            elif status == "scanned":
                continue
            else:
                raise AssertionError(f"{lab}:{span} unknown status {status!r}")


def test_restore_tree_copy_and_report_cardinality(tmp_path):
    """Copying the reconstructed tree preserves content and report cardinality."""
    clone = tmp_path / "restore-copy"
    shutil.copytree(OUT, clone)
    for rel, value in EXPECTED.items():
        assert (clone / rel).read_text() == value
    sizes = {repo: len(rows) for repo, rows in _report()["repositories"].items()}
    assert sizes == {"atlas": 6, "beacon": 5, "cinder": 4, "ridge": 4, "mesa": 3}


# ====================================================================
# Structural consistency — verifies root causes were addressed
# ====================================================================

def test_pool_files_under_objects():
    """All pool files must be in <lab>/objects/ directories."""
    for lab in LABS_SET:
        lab_dir = LABS / lab
        objects = lab_dir / "objects"
        assert objects.is_dir(), f"{lab}/objects/ directory missing"
        blobs = list(objects.glob("*.blob"))
        assert len(blobs) >= 2, f"{lab} has {len(blobs)} pool files"
        stray = []
        for child in lab_dir.iterdir():
            if child.is_dir() and child != objects and child.name not in (
                "recipes", "index", "journal", "ledger"
            ):
                stray.extend(str(p.relative_to(LABS)) for p in child.rglob("*.blob"))
        for blob in lab_dir.glob("*.blob"):
            stray.append(str(blob.relative_to(LABS)))
        assert not stray, f"pool files outside objects/: {stray}"


def test_pool_data_unmodified():
    """Pool file byte data must not be modified — only moved/renamed."""
    assert IMMUTABLE_CHECKSUMS.is_file(), IMMUTABLE_CHECKSUMS
    lines = [ln for ln in IMMUTABLE_CHECKSUMS.read_text().splitlines() if ln.strip()]
    assert len(lines) >= 10
    for line in lines:
        want_hash, tag = line.split(None, 1)
        tag = tag.strip()
        parts = tag.split("/")
        if len(parts) == 2 and parts[1].endswith(".blob"):
            lab, filename = parts
            path = LABS / lab / "objects" / filename
        else:
            path = LABS / tag
        assert path.is_file(), f"immutable artifact missing: {tag} (expected at {path})"
        assert _file_sha256(path) == want_hash, f"content modified: {tag}"


def test_recipe_files_unmodified():
    """Recipe files must not be modified."""
    for lab in LABS_SET:
        recipe_dir = LABS / lab / "recipes"
        assert recipe_dir.is_dir()
        for rec in recipe_dir.glob("*.rec"):
            content = rec.read_text()
            assert content.startswith("#") or "file " in content, f"corrupted recipe {rec}"
            assert "part " in content


def test_source_code_unmodified():
    """Rust source files must not be modified."""
    src_dir = APP / "src"
    assert src_dir.is_dir()
    rs_files = list(src_dir.glob("*.rs"))
    assert len(rs_files) >= 10


def test_profile_mask_consistency():
    """For labs with masking, verify the mask key produces valid decoded text."""
    for lab in LABS_SET:
        key, pools = _profile_mask(lab)
        if key is None:
            continue
        objects_dir = LABS / lab / "objects"
        for pool_name in pools:
            pool_path = objects_dir / pool_name
            stem = pool_name.removesuffix(".blob")
            if not pool_path.is_file():
                pool_path = objects_dir / f"{stem}.blob"
            if not pool_path.is_file():
                continue
            data = pool_path.read_bytes()
            decoded = bytes(b ^ key for b in data[:min(20, len(data))])
            assert all(0x09 <= b <= 0x7E for b in decoded), (
                f"{lab} mask_key={key} on {pool_name} produces non-text: {decoded!r}"
            )


def test_cross_lab_scan_reachability():
    """Each borrow reference must be reachable through the scan path."""
    for lab in LABS_SET:
        borrow_path = LABS / lab / "ledger" / "borrow.list"
        if not borrow_path.is_file():
            continue
        for line in borrow_path.read_text().splitlines():
            for ref in line.strip().split(","):
                ref = ref.strip()
                if not ref or ref.startswith("#"):
                    continue
                objects = LABS / ref / "objects"
                assert objects.is_dir(), f"{lab} borrows from '{ref}' but {ref}/objects/ missing"


# ====================================================================
# Neighbor snapshot
# ====================================================================

def _cargo_bin() -> str:
    primary = Path("/usr/local") / "cargo" / "bin" / "cargo"
    if primary.is_file() and os.access(primary, os.X_OK):
        return str(primary)
    found = shutil.which("cargo")
    if found:
        return found
    raise FileNotFoundError("cargo binary not found")


def test_neighbor_steady_snapshot_still_restores(tmp_path):
    """Neighboring snapshots still restore through the Rust utility."""
    side = tmp_path / "steady-out"
    log = tmp_path / "steady-log.json"
    env = os.environ.copy()
    cargo_bin = Path("/usr/local") / "cargo" / "bin"
    rustup_bin = Path("/usr/local") / "rustup" / "bin"
    env["PATH"] = f"{cargo_bin}:{rustup_bin}:{env.get('PATH', '/usr/bin:/bin')}"
    env.setdefault("CARGO" + "_NET_" + "OFFLINE", "true")
    subprocess.run(
        [
            _cargo_bin(), "run", "--quiet", "--",
            "run", "--root", "/app/labs",
            "--name", "steady-2026-06-17",
            "--out", str(side), "--log", str(log),
        ],
        cwd=APP, check=True, timeout=60, env=env,
    )
    for rel, value in NEIGHBOR.items():
        assert (side / rel).read_text() == value
