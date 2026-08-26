import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from reference_bottleplan import Instance, build_reference, local_reasons

APP = Path("/opt/bottleplan/app")
BIN = APP / "bin" / "bottleplan"
GO = "/usr/local/go/bin/go"
SCENARIO = Path("/srv/bottleplan")
CATALOG = SCENARIO / "catalog"
REQUEST = SCENARIO / "requests" / "public_request.json"
OUT = Path("/var/lib/bottleplan/out")
PROTECTED = [CATALOG, SCENARIO / "requests"]


def run(cmd, **kwargs):
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if root.is_file():
        digest.update(root.name.encode())
        digest.update(b"\0")
        digest.update(root.read_bytes())
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def build_tool():
    proc = run([GO, "build", "-o", str(BIN), "./cmd/bottleplan"], cwd=APP)
    assert proc.returncode == 0, proc.stderr


def run_cli(catalog_root=CATALOG, request_path=REQUEST, out_dir=OUT):
    return run([str(BIN), "plan", "--catalog-root", str(catalog_root), "--request", str(request_path), "--out", str(out_dir)])


def assert_outputs_match(catalog_root: Path, request_path: Path, out_dir: Path):
    expected = build_reference(catalog_root, request_path)
    for name, text in expected.items():
        assert (out_dir / name).read_text() == text


def clone_scenario(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    shutil.copytree(SCENARIO, root)
    return root


def write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload, indent=2) + "\n")


def test_public_outputs_match_reference_and_inputs_are_immutable():
    build_tool()
    before = {path: tree_hash(path) for path in PROTECTED}
    proc = run_cli()
    assert proc.returncode == 0, proc.stderr
    assert_outputs_match(CATALOG, REQUEST, OUT)
    after = {path: tree_hash(path) for path in PROTECTED}
    assert before == after


def test_usage_error_is_exact():
    build_tool()
    usage = "usage: bottleplan plan --catalog-root <abs-path> --request <abs-path> --out <abs-path>"
    bad_commands = [
        [],
        ["inspect", "--catalog-root", str(CATALOG), "--request", str(REQUEST), "--out", str(OUT)],
        ["plan", "--request", str(REQUEST), "--catalog-root", str(CATALOG), "--out", str(OUT)],
        ["plan", "--catalog-root", str(CATALOG), "--request", str(REQUEST)],
        ["plan", "--catalog-root", "srv", "--request", str(REQUEST), "--out", str(OUT)],
        ["plan", "--catalog-root", str(CATALOG), "--request", "request.json", "--out", str(OUT)],
        ["plan", "--catalog-root", str(CATALOG), "--request", str(REQUEST), "--out", "out"],
    ]
    for args in bad_commands:
        proc = run([str(BIN), *args])
        assert proc.returncode != 0
        assert proc.stderr.strip() == usage


def test_rerun_replaces_stale_outputs():
    build_tool()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stale.txt").write_text("stale\n")
    proc = run_cli()
    assert proc.returncode == 0, proc.stderr
    assert not (OUT / "stale.txt").exists()
    assert_outputs_match(CATALOG, REQUEST, OUT)


def test_rerun_is_byte_deterministic():
    build_tool()
    proc = run_cli()
    assert proc.returncode == 0, proc.stderr
    first = {name: (OUT / name).read_bytes() for name in ("promotion_plan.json", "mirror_fetch.tsv", "candidate_report.json")}
    proc = run_cli()
    assert proc.returncode == 0, proc.stderr
    second = {name: (OUT / name).read_bytes() for name in ("promotion_plan.json", "mirror_fetch.tsv", "candidate_report.json")}
    assert first == second


def test_public_plan_picks_older_roots_because_strict_relocation_blocks_libmesh_310():
    build_tool()
    proc = run_cli()
    assert proc.returncode == 0, proc.stderr
    plan = json.loads((OUT / "promotion_plan.json").read_text())
    roots = {row["name"]: row["selected_version"] for row in plan["root_selections"]}
    assert roots == {"warpctl": "2.1.0", "meshsync": "1.2.0"}
    selected = {row["name"]: row for row in plan["selected_formulae"]}
    assert selected["libmesh"]["version"] == "3.0.0"
    assert selected["warpctl"]["dependencies"] == [
        {"name": "libmesh", "version_range": ">=3.0.0 <3.2.0", "requires_features": []},
        {"name": "zstd", "version_range": ">=1.5.0 <2.0.0", "requires_features": []},
        {"name": "openssl", "version_range": ">=1.2.0 <2.0.0", "requires_features": ["tls"]},
        {"name": "readline", "version_range": ">=8.2.0 <9.0.0", "requires_features": ["cli"]},
    ]
    assert selected["libmesh"]["dependencies"] == []
    assert plan["unique_new_digest_count"] == 15
    assert plan["total_new_bytes"] == 244


def test_copied_root_policy_variant_selects_newer_roots(tmp_path: Path):
    build_tool()
    root = clone_scenario(tmp_path, "relaxed")
    request = json.loads((root / "requests" / "public_request.json").read_text())
    request["relocation_policy"] = "allow_cellar_specific"
    request["root_formulae"][0]["version_range"] = ">=2.2.0 <3.0.0"
    request["root_formulae"][1]["version_range"] = ">=1.3.0 <2.0.0"
    request["max_new_digests"] = 25
    request["max_new_bytes"] = 500
    write_json(root / "requests" / "public_request.json", request)
    policy = json.loads((root / "catalog" / "platform_policy.json").read_text())
    for row in policy["platforms"]:
        if row["platform"] == "linux_x86_64":
            row["minimum_runtime"] = "2.31"
    write_json(root / "catalog" / "platform_policy.json", policy)
    catalog = json.loads((root / "catalog" / "formula_catalog.json").read_text())
    catalog["formulas"] = list(reversed(catalog["formulas"]))
    write_json(root / "catalog" / "formula_catalog.json", catalog)
    out_dir = tmp_path / "out"
    proc = run_cli(root / "catalog", root / "requests" / "public_request.json", out_dir)
    assert proc.returncode == 0, proc.stderr
    assert_outputs_match(root / "catalog", root / "requests" / "public_request.json", out_dir)
    plan = json.loads((out_dir / "promotion_plan.json").read_text())
    roots = {row["name"]: row["selected_version"] for row in plan["root_selections"]}
    assert roots == {"warpctl": "2.2.0", "meshsync": "1.3.0"}


def test_all_mirrored_tie_uses_newer_root_versions(tmp_path: Path):
    build_tool()
    root = clone_scenario(tmp_path, "tie-break")
    request = json.loads((root / "requests" / "public_request.json").read_text())
    request["relocation_policy"] = "allow_cellar_specific"
    request["max_new_digests"] = 99
    request["max_new_bytes"] = 999
    write_json(root / "requests" / "public_request.json", request)
    policy = json.loads((root / "catalog" / "platform_policy.json").read_text())
    for row in policy["platforms"]:
        if row["platform"] == "linux_x86_64":
            row["minimum_runtime"] = "2.31"
    write_json(root / "catalog" / "platform_policy.json", policy)
    catalog = json.loads((root / "catalog" / "formula_catalog.json").read_text())
    all_digests = []
    for formula in catalog["formulas"]:
        for version in formula["versions"]:
            for bottle in version["bottles"]:
                all_digests.append(bottle["digest"])
    write_json(root / "catalog" / "mirror_inventory.json", {"mirrored_digests": sorted(all_digests)})
    out_dir = tmp_path / "out"
    proc = run_cli(root / "catalog", root / "requests" / "public_request.json", out_dir)
    assert proc.returncode == 0, proc.stderr
    assert_outputs_match(root / "catalog", root / "requests" / "public_request.json", out_dir)
    plan = json.loads((out_dir / "promotion_plan.json").read_text())
    roots = {row["name"]: row["selected_version"] for row in plan["root_selections"]}
    assert roots == {"warpctl": "2.2.0", "meshsync": "1.3.0"}
    assert plan["unique_new_digest_count"] == 0
    assert plan["total_new_bytes"] == 0


def test_shared_digest_variant_dedupes_fetch_rows_and_budget(tmp_path: Path):
    build_tool()
    root = clone_scenario(tmp_path, "shared-digest")
    catalog = json.loads((root / "catalog" / "formula_catalog.json").read_text())
    for formula in catalog["formulas"]:
        if formula["name"] == "readline":
            bottles = catalog["formulas"][catalog["formulas"].index(formula)]["versions"][0]["bottles"]
            for bottle in bottles:
                if bottle["platform"] in {"darwin_arm64", "darwin_x86_64"}:
                    bottle["digest"] = "sha256:readline-8.2.0-darwin-universal"
                    bottle["bytes"] = 10
    write_json(root / "catalog" / "formula_catalog.json", catalog)
    out_dir = tmp_path / "out"
    proc = run_cli(root / "catalog", root / "requests" / "public_request.json", out_dir)
    assert proc.returncode == 0, proc.stderr
    assert_outputs_match(root / "catalog", root / "requests" / "public_request.json", out_dir)
    plan = json.loads((out_dir / "promotion_plan.json").read_text())
    assert plan["unique_new_digest_count"] == 14
    assert plan["total_new_bytes"] == 234
    lines = (out_dir / "mirror_fetch.tsv").read_text().splitlines()
    shared = [line for line in lines if "sha256:readline-8.2.0-darwin-universal" in line]
    assert len(shared) == 1
    assert shared[0].endswith("readline@darwin_arm64,readline@darwin_x86_64")


def test_no_feasible_variant_emits_exact_error_and_no_partial_outputs(tmp_path: Path):
    build_tool()
    root = clone_scenario(tmp_path, "no-feasible")
    request = json.loads((root / "requests" / "public_request.json").read_text())
    request["max_new_bytes"] = 200
    write_json(root / "requests" / "public_request.json", request)
    out_dir = tmp_path / "out"
    proc = run_cli(root / "catalog", root / "requests" / "public_request.json", out_dir)
    assert proc.returncode != 0
    assert proc.stderr.strip() == "bottleplan: no feasible promotion plan"
    assert not out_dir.exists() or list(out_dir.iterdir()) == []


def test_candidate_report_keeps_rejected_candidates_and_reason_order():
    build_tool()
    proc = run_cli()
    assert proc.returncode == 0, proc.stderr
    report = json.loads((OUT / "candidate_report.json").read_text())
    warp = next(row for row in report["instances"] if row["instance_ref"] == "root.warpctl")
    statuses = {row["version"]: (row["status"], row["reasons"]) for row in warp["candidate_versions"]}
    assert statuses["2.4.0"] == ("rejected_gate", ["platform_unavailable"])
    assert statuses["2.3.0-rc1"] == ("rejected_gate", ["prerelease_blocked"])
    assert statuses["2.2.0"][0] == "eligible_not_chosen"
    assert statuses["2.1.0"][0] == "selected"
    assert statuses["2.0.0"] == ("rejected_gate", ["keg_only_blocked"])

    libmesh = next(row for row in report["instances"] if row["instance_ref"] == "root.warpctl->libmesh")
    libmesh_status = {row["version"]: (row["status"], row["reasons"]) for row in libmesh["candidate_versions"]}
    assert libmesh_status["3.1.0"] == ("rejected_gate", ["runtime_floor_conflict", "relocation_conflict"])
    assert libmesh_status["3.0.0"][0] == "selected"

    sqlite = next(row for row in report["instances"] if row["instance_ref"] == "root.meshsync->sqlite")
    sqlite_status = {row["version"]: row["reasons"] for row in sqlite["candidate_versions"]}
    assert sqlite_status["3.46.0"] == ["runtime_floor_conflict"]


def test_documented_local_reasons_are_exercised():
    request = json.loads(REQUEST.read_text())
    policies = {row["platform"]: row for row in json.loads((CATALOG / "platform_policy.json").read_text())["platforms"]}

    root_inst = Instance("root.demo", "NONE", "demo", ">=1.0.0 <2.0.0", tuple(), True, False)
    assert local_reasons(
        root_inst,
        {
            "version": "1.0.0",
            "revision": 1,
            "prerelease": False,
            "keg_only": True,
            "dependencies": [],
            "bottles": [],
        },
        request,
        policies,
    ) == ["keg_only_blocked"]

    dep_inst = Instance("root.demo->libmesh", "root.demo", "libmesh", ">=3.0.0 <4.0.0", tuple(), False, True)
    assert local_reasons(
        dep_inst,
        {
            "version": "3.1.0",
            "revision": 1,
            "prerelease": False,
            "keg_only": False,
            "dependencies": [],
            "bottles": [
                {
                    "platform": "darwin_arm64",
                    "digest": "a",
                    "bytes": 1,
                    "cellar": "/opt",
                    "rebuild": 1,
                    "relocatable": True,
                    "codesigned": True,
                    "runtime_floor": "13.0",
                },
                {
                    "platform": "darwin_x86_64",
                    "digest": "b",
                    "bytes": 1,
                    "cellar": "/usr",
                    "rebuild": 1,
                    "relocatable": True,
                    "codesigned": True,
                    "runtime_floor": "12.0",
                },
                {
                    "platform": "linux_x86_64",
                    "digest": "c",
                    "bytes": 1,
                    "cellar": "/home",
                    "rebuild": 1,
                    "relocatable": False,
                    "codesigned": False,
                    "runtime_floor": "2.31",
                },
            ],
        },
        request,
        policies,
    ) == ["runtime_floor_conflict", "relocation_conflict"]

    mesh_inst = Instance("root.meshsync", "NONE", "meshsync", ">=1.0.0 <2.0.0", tuple(), True, False)
    assert local_reasons(
        mesh_inst,
        {
            "version": "1.1.0",
            "revision": 1,
            "prerelease": False,
            "keg_only": False,
            "dependencies": [],
            "bottles": [
                {
                    "platform": "darwin_arm64",
                    "digest": "a",
                    "bytes": 1,
                    "cellar": "/opt",
                    "rebuild": 1,
                    "relocatable": True,
                    "codesigned": True,
                    "runtime_floor": "13.0",
                },
                {
                    "platform": "darwin_x86_64",
                    "digest": "b",
                    "bytes": 1,
                    "cellar": "/usr",
                    "rebuild": 1,
                    "relocatable": True,
                    "codesigned": False,
                    "runtime_floor": "12.0",
                },
                {
                    "platform": "linux_x86_64",
                    "digest": "c",
                    "bytes": 1,
                    "cellar": "/home",
                    "rebuild": 1,
                    "relocatable": True,
                    "codesigned": False,
                    "runtime_floor": "2.28",
                },
            ],
        },
        request,
        policies,
    ) == ["codesign_missing"]
