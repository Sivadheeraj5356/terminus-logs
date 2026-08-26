import hashlib
import json
import random
import string
import subprocess
from pathlib import Path

from reference_helmvals import reference_manifest_hash, reference_resolve

APP = Path("/app")
BIN = APP / "bin" / "helmvals"
FIXTURES = Path("/opt/verifier-fixtures/helmvals")


def suffix():
    return "".join(random.SystemRandom().choice(string.ascii_lowercase) for _ in range(7))


def run_resolve(chart_dir, out_path, values=(), set_args=()):
    cmd = [str(BIN), "resolve", "--chart", str(chart_dir), "--out", str(out_path)]
    for vf in values:
        cmd.extend(["--values", str(vf)])
    for s in set_args:
        cmd.extend(["--set", s])
    proc = subprocess.run(cmd, cwd=APP, text=True, capture_output=True)
    return proc


def resolve_ok(tmp_path, tag, chart_dir, values=(), set_args=()):
    out = tmp_path / f"out-{tag}.json"
    proc = run_resolve(chart_dir, out, values=values, set_args=set_args)
    assert proc.returncode == 0, proc.stderr
    return json.loads(out.read_text())


def canonical_json_bytes(obj):
    if isinstance(obj, dict):
        parts = []
        for key in sorted(obj.keys()):
            parts.append(json.dumps(key) + ":" + canonical_json_bytes(obj[key]))
        return "{" + ",".join(parts) + "}"
    if isinstance(obj, list):
        return "[" + ",".join(canonical_json_bytes(x) for x in obj) + "]"
    return json.dumps(obj)


def manifest_hash(manifest):
    payload = {k: v for k, v in manifest.items() if k != "manifest_hash"}
    data = canonical_json_bytes(payload).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def write_chart(tmp, name, chart_yaml, values_yaml, subcharts=None):
    root = tmp / name
    root.mkdir(parents=True, exist_ok=True)
    (root / "Chart.yaml").write_text(chart_yaml.strip() + "\n")
    (root / "values.yaml").write_text(values_yaml.strip() + "\n")
    if subcharts:
        for sub_name, files in subcharts.items():
            sub = root / "charts" / sub_name
            sub.mkdir(parents=True, exist_ok=True)
            (sub / "Chart.yaml").write_text(files["Chart.yaml"].strip() + "\n")
            (sub / "values.yaml").write_text(files["values.yaml"].strip() + "\n")
    return root


def test_basic_fixture_matches_reference(tmp_path):
    """Bundled basic chart must match the independent reference resolver."""
    tag = suffix()
    chart = APP / "fixtures" / "charts" / "basic"
    got = resolve_ok(tmp_path, tag, chart)
    expect = reference_resolve(chart)
    assert got == expect
    assert got["active_charts"] == ["cache", "umbrella"]


def test_global_propagates_to_active_subchart(tmp_path):
    """Global blocks from parent values must deep-merge into subchart global."""
    tag = suffix()
    chart = write_chart(
        tmp_path,
        f"global-{tag}",
        """
name: root
version: "1"
dependencies:
  - name: child
    version: "1"
    alias: kid
""",
        """
global:
  env: prod
kid:
  replicas: 1
""",
        subcharts={
            "child": {
                "Chart.yaml": "name: child\nversion: \"1\"",
                "values.yaml": "global:\n  region: west\nreplicas: 3",
            }
        },
    )
    got = resolve_ok(tmp_path, tag, chart)
    expect = reference_resolve(chart)
    assert got["values"]["kid"]["global"] == expect["values"]["kid"]["global"]


def test_condition_false_excludes_subchart(tmp_path):
    """Disabled condition must omit subchart from active_charts and values."""
    tag = suffix()
    chart = write_chart(
        tmp_path,
        f"cond-{tag}",
        """
name: root
version: "1"
dependencies:
  - name: metrics
    version: "1"
    condition: metrics.enabled
""",
        """
metrics:
  enabled: false
""",
        subcharts={
            "metrics": {
                "Chart.yaml": "name: metrics\nversion: \"1\"",
                "values.yaml": "scrape: 15s",
            }
        },
    )
    got = resolve_ok(tmp_path, tag, chart)
    assert got["active_charts"] == ["root"]
    assert "metrics" not in got["values"]


def test_values_file_scalar_overrides_defaults(tmp_path):
    """Later --values file must override scalar leaves."""
    tag = suffix()
    chart = write_chart(
        tmp_path,
        f"vals-{tag}",
        "name: solo\nversion: \"1\"",
        "replicas: 1",
    )
    overlay = tmp_path / f"overlay-{tag}.yaml"
    overlay.write_text("replicas: 9\n")
    got = resolve_ok(tmp_path, tag, chart, values=[overlay])
    assert got["values"]["solo"]["replicas"] == 9


def test_deep_map_merge_preserves_sibling_keys(tmp_path):
    """Map coalesce must deep-merge nested maps instead of replacing them."""
    tag = suffix()
    chart = write_chart(
        tmp_path,
        f"deep-{tag}",
        "name: solo\nversion: \"1\"",
        """
service:
  port: 80
  labels:
    app: api
""",
    )
    overlay = tmp_path / f"deep-overlay-{tag}.yaml"
    overlay.write_text(
        """
service:
  labels:
    tier: gold
"""
    )
    got = resolve_ok(tmp_path, tag, chart, values=[overlay])
    svc = got["values"]["solo"]["service"]
    assert svc["port"] == 80
    assert svc["labels"]["app"] == "api"
    assert svc["labels"]["tier"] == "gold"


def test_set_targets_subchart_by_prefix(tmp_path):
    """--set cache.replicas must update aliased subchart values."""
    tag = suffix()
    chart = write_chart(
        tmp_path,
        f"setsub-{tag}",
        """
name: root
version: "1"
dependencies:
  - name: redis
    version: "1"
    alias: cache
    condition: cache.enabled
""",
        "cache:\n  enabled: true",
        subcharts={
            "redis": {
                "Chart.yaml": "name: redis\nversion: \"1\"",
                "values.yaml": "replicas: 2",
            }
        },
    )
    got = resolve_ok(tmp_path, tag, chart, set_args=["cache.replicas=5"])
    assert got["values"]["cache"]["replicas"] == 5


def test_set_escape_literal_dot_key(tmp_path):
    """Escaped dotted --set keys must create a literal segment."""
    tag = suffix()
    chart = write_chart(
        tmp_path,
        f"esc-{tag}",
        "name: solo\nversion: \"1\"",
        "replicas: 1",
    )
    got = resolve_ok(tmp_path, tag, chart, set_args=[r"outer\.inner=7"])
    expect = reference_resolve(chart, set_args=[r"outer\.inner=7"])
    assert got["values"]["solo"] == expect["values"]["solo"]


def test_manifest_hash_includes_precedence_trail(tmp_path):
    """manifest_hash must change when precedence_trail changes."""
    tag = suffix()
    chart = write_chart(
        tmp_path,
        f"hash-{tag}",
        "name: solo\nversion: \"1\"",
        "replicas: 1",
    )
    first = resolve_ok(tmp_path, f"{tag}-a", chart)
    second = resolve_ok(tmp_path, f"{tag}-b", chart, set_args=["replicas=2"])
    assert first["manifest_hash"] != second["manifest_hash"]
    assert first["manifest_hash"] == reference_manifest_hash(first)
    assert second["manifest_hash"] == reference_manifest_hash(second)


def test_active_charts_sorted_lexicographically(tmp_path):
    """active_charts must be lexicographically sorted."""
    tag = suffix()
    got = resolve_ok(tmp_path, tag, APP / "fixtures" / "charts" / "basic")
    assert got["active_charts"] == sorted(got["active_charts"])


def test_precedence_trail_sorted(tmp_path):
    """precedence_trail rows must sort by chart, path, ordinal."""
    tag = suffix()
    got = resolve_ok(tmp_path, tag, APP / "fixtures" / "charts" / "basic")
    rows = got["precedence_trail"]
    pairs = [(r["chart"], r["path"], r["ordinal"]) for r in rows]
    assert pairs == sorted(pairs)


def test_missing_subchart_fails_without_output(tmp_path):
    """Missing charts/<name> directory must fail without writing output."""
    tag = suffix()
    chart = write_chart(
        tmp_path,
        f"missing-{tag}",
        """
name: root
version: "1"
dependencies:
  - name: ghost
    version: "1"
""",
        "ghost:\n  enabled: true",
    )
    out = tmp_path / "bad.json"
    proc = run_resolve(chart, out)
    assert proc.returncode != 0
    assert not out.exists()


def test_missing_required_flags_returns_usage():
    """Missing --chart or --out must exit non-zero with usage error."""
    proc = subprocess.run([str(BIN), "resolve"], cwd=APP, text=True, capture_output=True)
    assert proc.returncode != 0
    assert "usage:" in proc.stderr


def test_unknown_command_returns_nonzero():
    """Unknown subcommands must exit non-zero."""
    proc = subprocess.run([str(BIN), "lint"], cwd=APP, text=True, capture_output=True)
    assert proc.returncode != 0
    assert "unknown command" in proc.stderr


def test_values_cli_order_controls_scalar_winner(tmp_path):
    """--values files must apply in CLI order with last scalar winning."""
    tag = suffix()
    chart = write_chart(
        tmp_path,
        f"order-{tag}",
        "name: solo\nversion: \"1\"",
        "replicas: 0",
    )
    v1 = tmp_path / f"o1-{tag}.yaml"
    v2 = tmp_path / f"o2-{tag}.yaml"
    v1.write_text("replicas: 1\n")
    v2.write_text("replicas: 2\n")
    first = resolve_ok(tmp_path, f"{tag}-1", chart, values=[v1, v2])
    second = resolve_ok(tmp_path, f"{tag}-2", chart, values=[v2, v1])
    assert first["values"]["solo"]["replicas"] == 2
    assert second["values"]["solo"]["replicas"] == 1


def test_shuffled_values_file_order_same_manifest(tmp_path):
    """Deep-merged nested maps must be stable when sibling keys come from different files."""
    tag = suffix()
    chart = write_chart(
        tmp_path,
        f"shuffle-{tag}",
        "name: solo\nversion: \"1\"",
        "a: 1",
    )
    v1 = tmp_path / f"v1-{tag}.yaml"
    v2 = tmp_path / f"v2-{tag}.yaml"
    v1.write_text("nested:\n  x: 1\n")
    v2.write_text("nested:\n  y: 2\n")
    first = resolve_ok(tmp_path, f"{tag}-1", chart, values=[v1, v2])
    second = resolve_ok(tmp_path, f"{tag}-2", chart, values=[v2, v1])
    assert first["values"]["solo"]["nested"] == {"x": 1, "y": 2}
    assert second["values"]["solo"]["nested"] == first["values"]["solo"]["nested"]


def test_staging_resolve_snapshot_published_after_ingest_export(tmp_path):
    """resolve ingest/export publishes /app/state/helmvals-resolve-snapshot.json staging artifact."""
    snap = Path("/app/state/helmvals-resolve-snapshot.json")
    if snap.exists():
        snap.unlink()
    tag = suffix()
    out = tmp_path / f"snap-{tag}.json"
    proc = run_resolve(APP / "fixtures" / "charts" / "basic", out)
    assert proc.returncode == 0
    assert snap.is_file()
    assert json.loads(snap.read_text()) == json.loads(out.read_text())


def test_export_json_shape_has_required_keys(tmp_path):
    """Manifest must expose active_charts, values, precedence_trail, manifest_hash."""
    tag = suffix()
    got = resolve_ok(tmp_path, tag, APP / "fixtures" / "charts" / "basic")
    assert set(got.keys()) == {"active_charts", "values", "precedence_trail", "manifest_hash"}


def test_alias_parent_values_key_not_chart_name(tmp_path):
    """Parent values must pass subchart subtree under alias key, not dependency name."""
    tag = suffix()
    chart = write_chart(
        tmp_path,
        f"alias-{tag}",
        """
name: root
version: "1"
dependencies:
  - name: redis
    version: "1"
    alias: cache
    condition: cache.enabled
""",
        """
cache:
  enabled: true
  image: parent-redis
""",
        subcharts={
            "redis": {
                "Chart.yaml": "name: redis\nversion: \"1\"",
                "values.yaml": "image: child-redis",
            }
        },
    )
    got = resolve_ok(tmp_path, tag, chart)
    assert got["values"]["cache"]["image"] == "parent-redis"


def test_verifier_rebuild_required():
    """helmvals binary must exist after verifier rebuild."""
    assert BIN.is_file()
