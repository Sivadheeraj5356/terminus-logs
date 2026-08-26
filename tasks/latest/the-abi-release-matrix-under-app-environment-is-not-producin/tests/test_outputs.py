import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

APP = Path(os.environ.get("APP_ROOT", "/app"))
ENV = APP / "environment"
RELEASE_PASS = ENV / "runbook" / "release_pass.sh"
PUBLIC_MATRIX = ENV / "profiles" / "public.matrix"
BUILD_ROOT = APP / "build" / "sdk-abi-index"
OUTPUT_ROOT = APP / "output" / "sdk-abi-index"

PUBLIC_LANES = ["core", "telemetry", "recovery", "release"]

LEGACY_PREFIX = [
    "abi_version",
    "name",
    "checksum",
    "dispatch",
    "reserved",
    "capability_mask",
    "lifecycle_epoch",
    "allocator_cookie",
    "config_crc",
    "telemetry_sink",
    "quarantine_tag",
    "runtime_flags",
]


def runner_env():
    env = os.environ.copy()
    env["SDK_ENV_ROOT"] = str(ENV)
    env["SDK_BUILD_ROOT"] = str(BUILD_ROOT)
    return env


def invoke(matrix, out):
    out_path = Path(out)
    if out_path.exists():
        shutil.rmtree(out_path)
    subprocess.run(
        ["bash", str(RELEASE_PASS), str(matrix), str(out)],
        check=True,
        text=True,
        capture_output=True,
        env=runner_env(),
    )
    return out_path


def fresh_out(prefix):
    parent = OUTPUT_ROOT.parent / "runs"
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{prefix}-", dir=parent))


def tmp_file(prefix, suffix):
    fd, path = tempfile.mkstemp(prefix=f"{prefix}-", suffix=suffix, dir="/tmp")
    os.close(fd)
    return Path(path)


def manifest_of(out):
    return json.loads((Path(out) / "manifest.json").read_text())


def journal_of(lane):
    return json.loads((BUILD_ROOT / lane / ".sdk-lane.journal").read_text())


def rows_of(out):
    return manifest_of(out)["records"]


def row_for(out, lane):
    return next(r for r in rows_of(out) if r["lane"] == lane)


def sha(path):
    return subprocess.run(
        ["sha256sum", str(path)], check=True, text=True, capture_output=True
    ).stdout.split()[0]


def read_tsv(path):
    lines = Path(path).read_text().splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"))) for line in lines[1:] if line.strip()]


def layout_view(side):
    return {
        "lane": side["lane"],
        "record_size": side["record_size"],
        "align": side["align"],
        "field_count": side["field_count"],
        "fields": side["fields"],
    }


def assert_match(record):
    """The generated view and the compiled probe must agree completely."""
    assert record["status"] == "match", record
    assert layout_view(record["generated"]) == layout_view(record["compiled"]), record["lane"]
    fields = record["compiled"]["fields"]
    assert record["compiled"]["field_count"] == len(fields)
    slots = [f["slot"] for f in fields]
    assert slots == list(range(len(fields))), "slots must be contiguous from 0"


def prefix_map(record):
    out = {}
    for field in record["compiled"]["fields"]:
        if field["name"] in LEGACY_PREFIX:
            out[field["name"]] = field
    return out


def phases(out, lane):
    seq = []
    for row in read_tsv(Path(out) / "trace.tsv"):
        if row["lane"] == lane:
            seq.append(row["phase"])
    return seq


def test_release_runner_literal_command_shape():
    """The documented command produces a four-record manifest in lane order."""
    out = fresh_out("literal")
    invoke(PUBLIC_MATRIX, out)
    manifest = manifest_of(out)
    assert manifest["schema_version"] == 1
    assert manifest["record_count"] == 4
    assert [r["lane"] for r in manifest["records"]] == PUBLIC_LANES


def test_public_matrix_lineage_and_output_replay():
    """A pure output wipe replays byte-identically and leaves epochs untouched."""
    out = OUTPUT_ROOT
    invoke(PUBLIC_MATRIX, out)
    for name in ("manifest.json", "provenance.json", "probe.jsonl", "loader_journal.tsv", "trace.tsv"):
        p = Path(out) / name
        assert p.is_file() and p.stat().st_size > 0, name
    for record in rows_of(out):
        assert_match(record)
        assert record["configure_epoch"] >= 1
        assert record["generation_lineage"] >= 1
    probe_lines = (Path(out) / "probe.jsonl").read_text().strip().splitlines()
    assert len(probe_lines) == 4
    provenance = json.loads((Path(out) / "provenance.json").read_text())
    assert provenance["schema_version"] == 1
    assert [lane["lane"] for lane in provenance["lanes"]] == PUBLIC_LANES
    for lane in provenance["lanes"]:
        assert len(lane["sha256"]) == 64

    first_manifest = sha(Path(out) / "manifest.json")
    first_probe = sha(Path(out) / "probe.jsonl")
    epochs = {r["lane"]: r["configure_epoch"] for r in rows_of(out)}
    lineages = {r["lane"]: r["generation_lineage"] for r in rows_of(out)}

    sentinel = BUILD_ROOT / "release" / ".warm-hold"
    sentinel.write_text("warm\n")
    invoke(PUBLIC_MATRIX, out)
    assert sentinel.is_file(), "output-only wipe must retain the build tree"
    assert sha(Path(out) / "manifest.json") == first_manifest
    assert sha(Path(out) / "probe.jsonl") == first_probe
    for record in rows_of(out):
        assert record["configure_epoch"] == epochs[record["lane"]]
        assert record["generation_lineage"] == lineages[record["lane"]]


def test_idl_pack_touch_advances_configure_epoch():
    """Editing the physical fragment order invalidates warm lanes."""
    invoke(PUBLIC_MATRIX, fresh_out("pack-warm"))
    before = journal_of("release")["configure_epoch"]
    pack = ENV / "idl" / "pack.order"
    original = pack.read_text()
    try:
        pack.write_text(original.rstrip("\n") + "\n# revision marker\n")
        out = fresh_out("pack-touch")
        invoke(PUBLIC_MATRIX, out)
        after = journal_of("release")["configure_epoch"]
        assert after > before
        for record in rows_of(out):
            assert_match(record)
    finally:
        pack.write_text(original)


def test_truncated_lane_journal_forces_recovery():
    """A journal that lost its integrity fingerprints must be rebuilt, not trusted."""
    lane = "recovery"
    invoke(PUBLIC_MATRIX, fresh_out("journal-warm"))
    journal_path = BUILD_ROOT / lane / ".sdk-lane.journal"
    warm = json.loads(journal_path.read_text())
    torn = {
        "schema_version": 1,
        "lane": lane,
        "last_matrix_sha256": warm["last_matrix_sha256"],
        "configure_epoch": warm["configure_epoch"],
        "generation_lineage": warm["generation_lineage"],
    }
    journal_path.write_text(json.dumps(torn))
    out = fresh_out("journal-recover")
    invoke(PUBLIC_MATRIX, out)
    record = row_for(out, lane)
    assert_match(record)
    assert record["configure_epoch"] > warm["configure_epoch"]
    assert record["generation_lineage"] > warm["generation_lineage"]
    rebuilt = journal_of(lane)
    assert len(rebuilt["idl_digest"]) == 16
    assert len(rebuilt["tool_digest"]) == 64
    assert len(rebuilt["profile_sha256"]) == 64


def test_lane_rebind_without_tree_reset():
    """Editing a lane profile in place must reconfigure and re-lay-out the record."""
    lane = "rebind_scope"
    profile = tmp_file("rebind", ".lane")
    matrix = tmp_file("rebind", ".matrix")
    profile.write_text("name=rebind\nfragments=00_core.sdk,10_runtime.sdk,15_lifecycle.sdk\n")
    matrix.write_text(f"{lane} {profile}\n")
    out_a = fresh_out("rebind-a")
    invoke(matrix, out_a)
    record_a = row_for(out_a, lane)
    assert_match(record_a)
    assert record_a["compiled"]["field_count"] == 12

    profile.write_text(
        "name=rebind\nfragments=00_core.sdk,10_runtime.sdk,15_lifecycle.sdk,18_observability.sdk\n"
    )
    out_b = fresh_out("rebind-b")
    invoke(matrix, out_b)
    record_b = row_for(out_b, lane)
    assert_match(record_b)
    assert record_b["compiled"]["field_count"] > record_a["compiled"]["field_count"]
    assert record_b["configure_epoch"] > record_a["configure_epoch"]
    assert record_b["generation_lineage"] > record_a["generation_lineage"]


def test_preview_header_non_authoritative_with_warm_journal():
    """A poisoned checked-in preview header must not steer any lane's result."""
    invoke(PUBLIC_MATRIX, fresh_out("preview-warm"))
    preview = ENV / "include" / "generated" / "sdk.hpp"
    original = preview.read_text()
    try:
        preview.write_text(
            "#ifndef SDK_ABI_SHAPE_HPP\n#define SDK_ABI_SHAPE_HPP\n"
            '#define SDK_LANE "poison"\n'
            "#define SDK_HAS_OBSERVABILITY 1\n"
            "#define SDK_HAS_DIAGNOSTICS 1\n"
            "#define SDK_HAS_RECOVERY 1\n"
            "#define SDK_FIELD_COUNT 3\n"
            "#define SDK_RECORD_SIZE 8\n"
            "#define SDK_RECORD_ALIGN 4\n"
            '#define SDK_IDL_DIGEST "poison"\n#endif\n'
        )
        out = fresh_out("preview-check")
        invoke(PUBLIC_MATRIX, out)
        for record in rows_of(out):
            assert record["compiled"]["lane"] != "poison"
            assert_match(record)
    finally:
        preview.write_text(original)


def test_missing_generated_header_reconcile_heals():
    """Deleting a lane's generated header must trigger a traced reconcile and heal."""
    lane = "release"
    invoke(PUBLIC_MATRIX, fresh_out("reconcile-warm"))
    before = journal_of(lane)["generation_lineage"]
    header = BUILD_ROOT / lane / "generated" / "include" / "generated" / "sdk.hpp"
    assert header.is_file()
    header.unlink()
    out = fresh_out("reconcile-heal")
    invoke(PUBLIC_MATRIX, out)
    assert phases(out, lane) == ["configure", "reconcile", "build", "header", "probe"]
    for other in ("core", "telemetry", "recovery"):
        assert phases(out, other) == ["configure", "build", "header", "probe"]
    record = row_for(out, lane)
    assert_match(record)
    assert record["generation_lineage"] > before
    assert header.is_file()


def test_partial_lane_prime_then_public_matrix():
    """A single-lane prime must not leave later full-matrix lanes stale."""
    matrix = tmp_file("prime", ".matrix")
    matrix.write_text("release profiles/release.lane\n")
    invoke(matrix, fresh_out("prime-only"))
    out = fresh_out("prime-pub")
    invoke(PUBLIC_MATRIX, out)
    manifest = manifest_of(out)
    assert [r["lane"] for r in manifest["records"]] == PUBLIC_LANES
    for record in manifest["records"]:
        assert_match(record)


def test_reordered_external_matrix_preserves_order():
    """An external matrix keeps its declared row order and per-lane coherence."""
    matrix = tmp_file("reorder", ".matrix")
    matrix.write_text(
        "release profiles/release.lane\n"
        "core profiles/core.lane\n"
        "recovery profiles/recovery.lane\n"
    )
    out = fresh_out("reorder")
    invoke(matrix, out)
    manifest = manifest_of(out)
    assert [r["lane"] for r in manifest["records"]] == ["release", "core", "recovery"]
    for record in manifest["records"]:
        assert_match(record)


def test_cross_lane_isolation_after_profile_edit():
    """Editing one lane's profile must not perturb another lane's compiled layout."""
    lane_a = "iso_a"
    lane_b = "iso_b"
    profile_a = tmp_file("iso-a", ".lane")
    profile_b = tmp_file("iso-b", ".lane")
    matrix = tmp_file("iso", ".matrix")
    profile_a.write_text("name=a\nfragments=00_core.sdk,10_runtime.sdk,15_lifecycle.sdk\n")
    profile_b.write_text(
        "name=b\nfragments=00_core.sdk,10_runtime.sdk,15_lifecycle.sdk,"
        "18_observability.sdk,20_diagnostics.sdk,30_recovery.sdk\n"
    )
    matrix.write_text(f"{lane_a} {profile_a}\n{lane_b} {profile_b}\n")
    out1 = fresh_out("iso-1")
    invoke(matrix, out1)
    b_before = row_for(out1, lane_b)["compiled"]
    b_sha_before = journal_of(lane_b)["profile_sha256"]
    assert row_for(out1, lane_a)["compiled"]["record_size"] < b_before["record_size"]

    profile_a.write_text(
        "name=a\nfragments=00_core.sdk,10_runtime.sdk,15_lifecycle.sdk,18_observability.sdk\n"
    )
    out2 = fresh_out("iso-2")
    invoke(matrix, out2)
    a_after = row_for(out2, lane_a)
    b_after = row_for(out2, lane_b)
    assert_match(a_after)
    assert_match(b_after)
    assert a_after["compiled"]["field_count"] > 12
    assert layout_view(b_after["compiled"]) == layout_view(b_before)
    assert journal_of(lane_b)["profile_sha256"] == b_sha_before


def test_double_output_wipe_idempotent_manifest():
    """Two consecutive output wipes keep the manifest and probe byte-identical."""
    out = fresh_out("double-wipe")
    invoke(PUBLIC_MATRIX, out)
    m1 = sha(Path(out) / "manifest.json")
    p1 = sha(Path(out) / "probe.jsonl")
    invoke(PUBLIC_MATRIX, out)
    m2 = sha(Path(out) / "manifest.json")
    p2 = sha(Path(out) / "probe.jsonl")
    invoke(PUBLIC_MATRIX, out)
    assert sha(Path(out) / "manifest.json") == m1 == m2
    assert sha(Path(out) / "probe.jsonl") == p1 == p2
    for record in rows_of(out):
        assert_match(record)


def test_loader_journal_accepts_legacy_prefix_all_lanes():
    """Every lane's loader journal must accept all twelve frozen prefix fields."""
    out = fresh_out("loader")
    invoke(PUBLIC_MATRIX, out)
    journal = read_tsv(Path(out) / "loader_journal.tsv")
    assert {"lane", "phase", "field", "status", "detail"} <= set(journal[0].keys())
    assert not [r for r in journal if r["status"] == "rejected"], "no rejected loader rows"
    for lane in PUBLIC_LANES:
        accepted = {
            r["field"]
            for r in journal
            if r["lane"] == lane and r["status"] == "accepted" and r["phase"] == "legacy"
        }
        for field in LEGACY_PREFIX:
            assert field in accepted, f"{lane} rejected legacy field {field}"

    # frozen prefix: identical slot/offset/size/ctype in every lane
    baseline = prefix_map(row_for(out, "core"))
    for lane in PUBLIC_LANES:
        current = prefix_map(row_for(out, lane))
        for name in LEGACY_PREFIX:
            for key in ("slot", "offset", "size", "ctype"):
                assert current[name][key] == baseline[name][key], (lane, name, key)
        assert current["abi_version"]["slot"] == 0
