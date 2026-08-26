import hashlib
import json
import subprocess
import uuid
from pathlib import Path


BIN = Path("/usr/local/bin/blendprofile")


def stable_json_sha(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def addon_content_sha(files):
    digest = hashlib.sha256()
    for name, content in sorted(files.items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def run(args, ok=True):
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    if ok:
        assert proc.returncode == 0, proc.stderr + proc.stdout
    else:
        assert proc.returncode != 0
    return proc


def manifest(tmp_path, marker, addons):
    data = {
        "blender_version": "4.3-addon",
        "python_expr": "print('addons')",
        "env": {"PROFILE_MARKER": marker},
        "profile_settings": {"theme": "dark"},
        "addons": addons,
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


def dependency_addons(marker):
    core = f"a_core_tools_{marker}"
    color = f"b_color_math_{marker}"
    paint = f"c_paint_stack_{marker}"
    render = f"d_render_bridge_{marker}"
    final = f"e_finalizer_{marker}"
    legacy = f"z_legacy_tools_{marker}"
    addons = [
        {
            "id": f"core-{marker}",
            "module": core,
            "enabled": True,
            "version": "1.10.0",
            "files": {"__init__.py": "CORE = True\n"},
            "preferences": {"tier": "core"},
        },
        {
            "id": f"color-{marker}",
            "module": color,
            "enabled": True,
            "version": "1.10.0",
            "files": {"__init__.py": "COLOR = True\n"},
            "preferences": {"tier": "math"},
        },
        {
            "id": f"paint-{marker}",
            "module": paint,
            "enabled": True,
            "version": "2.0.0",
            "requires": [
                {"module": core, "min_version": "1.9.0"},
                {"module": color, "min_version": "1.10.0"},
            ],
            "files": {"__init__.py": "PAINT = True\n"},
            "preferences": {"tier": "tool"},
        },
        {
            "id": f"render-{marker}",
            "module": render,
            "enabled": True,
            "version": "3.0.0",
            "requires": [{"module": paint, "min_version": "2.0.0"}],
            "load_before": [final],
            "files": {"__init__.py": "RENDER = True\n"},
            "preferences": {"tier": "bridge"},
        },
        {
            "id": f"final-{marker}",
            "module": final,
            "enabled": True,
            "version": "1.0.0",
            "load_after": [render],
            "files": {"__init__.py": "FINAL = True\n"},
            "preferences": {"tier": "final"},
        },
        {
            "id": f"legacy-{marker}",
            "module": legacy,
            "enabled": False,
            "version": "9.9.9",
            "conflicts": [paint],
            "files": {"__init__.py": "LEGACY = True\n"},
            "preferences": {"tier": "legacy"},
        },
    ]
    expected_order = [core, color, paint, render, final]
    expected_edges = sorted([f"{core}->{paint}", f"{color}->{paint}", f"{paint}->{render}", f"{render}->{final}"])
    return addons, expected_order, expected_edges


def assert_no_addon_state(root, profile):
    profile_dir = root / profile
    assert not (profile_dir / "config" / "enabled_addons.json").exists()
    assert not (profile_dir / "config" / "addons.lock.json").exists()
    addon_dir = profile_dir / "scripts" / "addons"
    if addon_dir.exists():
        assert not any(addon_dir.rglob("addon_manifest.json"))


def file_snapshot(profile_root):
    return {str(path.relative_to(profile_root)): path.read_bytes() for path in profile_root.rglob("*") if path.is_file()}


class TestAddonContract:
    def test_create_installs_addon_manifests_files_and_enabled_metadata(self, tmp_path):
        """Enabled and disabled add-ons must be installed from runtime manifest rows."""
        marker = uuid.uuid4().hex[:8]
        addons = [
            {
                "id": f"paint-{marker}",
                "module": f"zpaint_tools_{marker}",
                "enabled": True,
                "version": "1.2.0",
                "files": {"ops/tool.py": "VALUE = 7\n", "__init__.py": f"bl_info = {{'name': 'Paint {marker}'}}\n"},
                "preferences": {"panel": "TOOLS", "quality": "high"},
            },
            {
                "id": f"rig-{marker}",
                "module": f"arig_tools_{marker}",
                "enabled": True,
                "version": "3.1.4",
                "files": {"__init__.py": "REGISTER = True\n"},
                "preferences": {"panel": "RIG"},
            },
            {
                "id": f"mesh-{marker}",
                "module": f"mesh_pack_{marker}",
                "enabled": False,
                "version": "0.9.1",
                "files": {"__init__.py": "# disabled\n"},
                "preferences": {"panel": "MESH"},
            },
        ]
        manifest_path, _ = manifest(tmp_path, marker, addons)
        root = tmp_path / "profiles"
        profile = f"addon_{marker}"
        out = tmp_path / "report.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        profile_root = root / profile
        manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        enabled_path = profile_root / "config" / "enabled_addons.json"
        enabled = json.loads(enabled_path.read_text())
        assert enabled["generated_by"] == "blendprofile"
        assert enabled["profile"] == profile
        assert enabled["enabled_modules"] == [f"arig_tools_{marker}", f"zpaint_tools_{marker}"]
        assert [a["module"] for a in enabled["addons"]] == [f"arig_tools_{marker}", f"zpaint_tools_{marker}"]
        enabled_by_module = {row["module"]: row for row in enabled["addons"]}
        for addon in [row for row in addons if row["enabled"]]:
            entry = enabled_by_module[addon["module"]]
            addon_dir = profile_root / "scripts" / "addons" / addon["module"]
            assert entry["id"] == addon["id"]
            assert entry["version"] == addon["version"]
            assert entry["enabled"] is True
            assert entry["preferences"] == addon["preferences"]
            assert entry["install_path"] == str(addon_dir.resolve())
            assert entry["files"] == sorted(addon["files"].keys())
        for addon in addons:
            addon_dir = profile_root / "scripts" / "addons" / addon["module"]
            assert addon_dir.is_dir()
            meta = json.loads((addon_dir / "addon_manifest.json").read_text())
            assert meta["id"] == addon["id"]
            assert meta["module"] == addon["module"]
            assert meta["version"] == addon["version"]
            assert meta["enabled"] is addon["enabled"]
            assert meta["preferences"] == addon["preferences"]
            assert meta["install_path"] == str(addon_dir.resolve())
            assert meta["files"] == sorted(addon["files"].keys())
            for fname, content in addon["files"].items():
                assert (addon_dir / fname).read_text() == content
        lock_path = profile_root / "config" / "addons.lock.json"
        lock = json.loads(lock_path.read_text())
        assert lock["generated_by"] == "blendprofile"
        assert lock["profile"] == profile
        assert lock["manifest_sha256"] == manifest_sha
        assert lock["addon_count"] == 3
        assert lock["addon_file_count"] == 4
        assert [row["module"] for row in lock["addons"]] == sorted(addon["module"] for addon in addons)
        by_module = {addon["module"]: addon for addon in addons}
        for row in lock["addons"]:
            addon = by_module[row["module"]]
            assert row["id"] == addon["id"]
            assert row["version"] == addon["version"]
            assert row["enabled"] is addon["enabled"]
            assert row["file_count"] == len(addon["files"])
            assert row["content_sha256"] == addon_content_sha(addon["files"])
            assert row["preferences_sha256"] == stable_json_sha(addon["preferences"])
        managed_path = profile_root / "config" / "managed_files.json"
        managed = json.loads(managed_path.read_text())
        expected_kinds = {
            f"bin/blender-{profile}": "wrapper",
            "startup/bootstrap.py": "bootstrap",
            "config/enabled_addons.json": "enabled_metadata",
            "config/addons.lock.json": "addon_lock",
        }
        for addon in addons:
            base = f"scripts/addons/{addon['module']}"
            expected_kinds[f"{base}/addon_manifest.json"] = "addon_manifest"
            for fname in addon["files"]:
                expected_kinds[f"{base}/{fname}"] = "addon_file"
        assert managed["generated_by"] == "blendprofile"
        assert managed["profile"] == profile
        assert managed["manifest_sha256"] == manifest_sha
        assert managed["file_count"] == len(expected_kinds)
        assert [row["path"] for row in managed["files"]] == sorted(expected_kinds)
        for row in managed["files"]:
            target = profile_root / row["path"]
            assert row["kind"] == expected_kinds[row["path"]]
            assert row["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
        payload = json.loads(out.read_text())
        assert payload["manifest_sha256"] == manifest_sha
        assert payload["addon_count"] == 3
        assert payload["addon_file_count"] == 4
        assert payload["enabled_addons"] == [f"arig_tools_{marker}", f"zpaint_tools_{marker}"]
        assert payload["addon_manifests"] == sorted(
            str((profile_root / "scripts" / "addons" / addon["module"] / "addon_manifest.json").resolve()) for addon in addons
        )
        assert payload["addon_lock_path"] == str(lock_path.resolve())
        assert payload["managed_files_path"] == str(managed_path.resolve())
        assert payload["managed_file_count"] == len(expected_kinds)
        before = out.read_text()
        lock_before = lock_path.read_text()
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        assert out.read_text() == before
        assert lock_path.read_text() == lock_before

    def test_create_resolves_dependency_versions_edges_and_load_order(self, tmp_path):
        """Dependency graph output must use numeric versions and deterministic topological order."""
        marker = uuid.uuid4().hex[:8]
        addons, expected_order, expected_edges = dependency_addons(marker)
        manifest_path, _ = manifest(tmp_path, marker, addons)
        root = tmp_path / "profiles"
        profile = f"graph_{marker}"
        out = tmp_path / "report.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        profile_root = root / profile
        payload = json.loads(out.read_text())
        enabled = json.loads((profile_root / "config" / "enabled_addons.json").read_text())
        lock = json.loads((profile_root / "config" / "addons.lock.json").read_text())
        assert payload["addon_load_order"] == expected_order
        assert payload["dependency_edges"] == expected_edges
        assert enabled["addon_load_order"] == expected_order
        assert enabled["dependency_edges"] == expected_edges
        assert lock["addon_load_order"] == expected_order
        assert lock["dependency_edges"] == expected_edges
        assert payload["enabled_addons"] == sorted(expected_order)
        paint_module = expected_order[2]
        paint_meta = json.loads((profile_root / "scripts" / "addons" / paint_module / "addon_manifest.json").read_text())
        assert paint_meta["requires"] == sorted(addons[2]["requires"], key=lambda row: (row["module"], row["min_version"]))
        assert paint_meta["load_after"] == []
        assert paint_meta["conflicts"] == []
        render_meta = json.loads((profile_root / "scripts" / "addons" / expected_order[3] / "addon_manifest.json").read_text())
        assert render_meta["load_before"] == [expected_order[4]]
        legacy_meta = json.loads((profile_root / "scripts" / "addons" / addons[-1]["module"] / "addon_manifest.json").read_text())
        assert legacy_meta["enabled"] is False
        assert legacy_meta["conflicts"] == [paint_module]

        tie_addons = [
            {
                "id": f"z-tie-{marker}",
                "module": f"z_tie_tools_{marker}",
                "enabled": True,
                "version": "1.0.0",
                "files": {"__init__.py": "Z_TIE = True\n"},
                "preferences": {},
            },
            {
                "id": f"a-tie-{marker}",
                "module": f"a_tie_tools_{marker}",
                "enabled": True,
                "version": "1.0.0",
                "files": {"__init__.py": "A_TIE = True\n"},
                "preferences": {},
            },
        ]
        tie_manifest, _ = manifest(tmp_path, f"{marker}_tie", tie_addons)
        tie_out = tmp_path / "tie_report.json"
        tie_profile = f"tie_{marker}"
        run([str(BIN), "create", "--manifest", str(tie_manifest), "--root", str(root), "--profile", tie_profile, "--out", str(tie_out)])
        tie_payload = json.loads(tie_out.read_text())
        assert tie_payload["addon_load_order"] == [f"a_tie_tools_{marker}", f"z_tie_tools_{marker}"]
        assert tie_payload["dependency_edges"] == []

    def test_create_rejects_dependency_graph_errors_without_profile_mutation(self, tmp_path):
        """Bad dependency graphs must fail before writing profile state."""
        marker = uuid.uuid4().hex[:8]
        root = tmp_path / "profiles"
        out = tmp_path / "report.json"

        addons, _, _ = dependency_addons(marker)
        version_bad = json.loads(json.dumps(addons))
        version_bad[0]["version"] = "1.9.0"
        version_bad[2]["requires"][0]["min_version"] = "1.10.0"
        bad_path, _ = manifest(tmp_path, marker, version_bad)
        profile = f"badversion_{marker}"
        proc = run([str(BIN), "create", "--manifest", str(bad_path), "--root", str(root), "--profile", profile, "--out", str(out)], ok=False)
        combined = proc.stderr + proc.stdout
        assert "1.10.0" in combined
        assert version_bad[2]["module"] in combined
        assert not out.exists()
        assert_no_addon_state(root, profile)

        addons, _, _ = dependency_addons(marker)
        missing_dep = [row for row in addons if not row["module"].startswith("b_color_math_")]
        missing_path, _ = manifest(tmp_path, marker, missing_dep)
        profile = f"missingdep_{marker}"
        proc = run([str(BIN), "create", "--manifest", str(missing_path), "--root", str(root), "--profile", profile, "--out", str(out)], ok=False)
        assert "requires" in proc.stderr + proc.stdout
        assert not out.exists()
        assert_no_addon_state(root, profile)

        addons, _, _ = dependency_addons(marker)
        disabled_dep = json.loads(json.dumps(addons))
        disabled_dep[1]["enabled"] = False
        disabled_path, _ = manifest(tmp_path, marker, disabled_dep)
        profile = f"disableddep_{marker}"
        proc = run([str(BIN), "create", "--manifest", str(disabled_path), "--root", str(root), "--profile", profile, "--out", str(out)], ok=False)
        combined = proc.stderr + proc.stdout
        assert disabled_dep[1]["module"] in combined
        assert "requires" in combined
        assert not out.exists()
        assert_no_addon_state(root, profile)

        addons, _, _ = dependency_addons(marker)
        cycle = json.loads(json.dumps(addons))
        cycle[0]["load_after"] = [cycle[4]["module"]]
        cycle_path, _ = manifest(tmp_path, marker, cycle)
        profile = f"cycle_{marker}"
        proc = run([str(BIN), "create", "--manifest", str(cycle_path), "--root", str(root), "--profile", profile, "--out", str(out)], ok=False)
        assert "cycle" in (proc.stderr + proc.stdout).lower()
        assert not out.exists()
        assert_no_addon_state(root, profile)

        addons, _, _ = dependency_addons(marker)
        conflict = json.loads(json.dumps(addons))
        conflict[-1]["enabled"] = True
        conflict_path, _ = manifest(tmp_path, marker, conflict)
        profile = f"conflict_{marker}"
        proc = run([str(BIN), "create", "--manifest", str(conflict_path), "--root", str(root), "--profile", profile, "--out", str(out)], ok=False)
        assert "conflict" in (proc.stderr + proc.stdout).lower()
        assert not out.exists()
        assert_no_addon_state(root, profile)

    def test_create_reconciles_changed_manifest_and_removes_stale_addon_state(self, tmp_path):
        """A changed manifest must prune stale managed add-ons and rewrite derived metadata."""
        marker = uuid.uuid4().hex[:8]
        keep_module = f"keep_tools_{marker}"
        stale_module = f"stale_tools_{marker}"
        new_module = f"bake_tools_{marker}"
        first_addons = [
            {
                "id": f"keep-{marker}",
                "module": keep_module,
                "enabled": True,
                "version": "1.0.0",
                "files": {"__init__.py": "KEEP = 1\n", "old_only.py": "REMOVE_ME = True\n"},
                "preferences": {"panel": "KEEP", "quality": "draft"},
            },
            {
                "id": f"stale-{marker}",
                "module": stale_module,
                "enabled": True,
                "version": "1.0.0",
                "files": {"__init__.py": "STALE = True\n"},
                "preferences": {"panel": "STALE"},
            },
        ]
        manifest_path, first_manifest = manifest(tmp_path, marker, first_addons)
        root = tmp_path / "profiles"
        profile = f"reconcile_{marker}"
        out = tmp_path / "report.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        profile_root = root / profile
        assert (profile_root / "scripts" / "addons" / stale_module / "addon_manifest.json").exists()
        assert (profile_root / "scripts" / "addons" / keep_module / "old_only.py").exists()

        second_addons = [
            {
                "id": f"keep-{marker}",
                "module": keep_module,
                "enabled": False,
                "version": "2.0.0",
                "files": {"__init__.py": "KEEP = 2\n", "nested/new.py": "NEW_FILE = True\n"},
                "preferences": {"panel": "KEEP", "quality": "final"},
            },
            {
                "id": f"bake-{marker}",
                "module": new_module,
                "enabled": True,
                "version": "0.5.0",
                "files": {"__init__.py": "BAKE = True\n"},
                "preferences": {"panel": "BAKE"},
            },
        ]
        second_manifest = {
            **first_manifest,
            "blender_version": "4.3-addon-updated",
            "addons": second_addons,
        }
        manifest_path.write_text(json.dumps(second_manifest), encoding="utf-8")
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])

        keep_dir = profile_root / "scripts" / "addons" / keep_module
        new_dir = profile_root / "scripts" / "addons" / new_module
        assert not (profile_root / "scripts" / "addons" / stale_module).exists()
        assert not (keep_dir / "old_only.py").exists()
        assert (keep_dir / "nested" / "new.py").read_text() == "NEW_FILE = True\n"
        keep_meta = json.loads((keep_dir / "addon_manifest.json").read_text())
        assert keep_meta["version"] == "2.0.0"
        assert keep_meta["enabled"] is False
        assert keep_meta["preferences"] == {"panel": "KEEP", "quality": "final"}
        assert keep_meta["files"] == ["__init__.py", "nested/new.py"]
        assert (new_dir / "__init__.py").read_text() == "BAKE = True\n"
        enabled = json.loads((profile_root / "config" / "enabled_addons.json").read_text())
        assert enabled["enabled_modules"] == [new_module]
        assert [row["module"] for row in enabled["addons"]] == [new_module]
        lock = json.loads((profile_root / "config" / "addons.lock.json").read_text())
        assert lock["manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        assert lock["addon_count"] == 2
        assert lock["addon_file_count"] == 3
        assert [row["module"] for row in lock["addons"]] == sorted([new_module, keep_module])
        by_module = {row["module"]: row for row in lock["addons"]}
        assert by_module[keep_module]["content_sha256"] == addon_content_sha(second_addons[0]["files"])
        assert by_module[new_module]["content_sha256"] == addon_content_sha(second_addons[1]["files"])
        payload = json.loads(out.read_text())
        assert payload["blender_version"] == "4.3-addon-updated"
        assert payload["addon_count"] == 2
        assert payload["addon_file_count"] == 3
        assert payload["enabled_addons"] == [new_module]

    def test_changed_manifest_write_failure_preserves_existing_profile_state(self, tmp_path):
        """A failed changed-manifest create must not corrupt the current managed profile."""
        marker = uuid.uuid4().hex[:8]
        keep_module = f"keep_tools_{marker}"
        blocked_module = f"blocked_tools_{marker}"
        first_addons = [
            {
                "id": f"keep-{marker}",
                "module": keep_module,
                "enabled": True,
                "version": "1.0.0",
                "files": {"__init__.py": "KEEP = 1\n"},
                "preferences": {"panel": "KEEP"},
            }
        ]
        manifest_path, first_manifest = manifest(tmp_path, marker, first_addons)
        root = tmp_path / "profiles"
        profile = f"preserve_{marker}"
        out = tmp_path / "report.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        profile_root = root / profile
        blocked_path = profile_root / "scripts" / "addons" / blocked_module
        blocked_path.write_text("not a directory", encoding="utf-8")
        before_files = file_snapshot(profile_root)
        before_report = out.read_text()

        second_manifest = {
            **first_manifest,
            "blender_version": "4.3-addon-blocked",
            "addons": first_addons
            + [
                {
                    "id": f"blocked-{marker}",
                    "module": blocked_module,
                    "enabled": True,
                    "version": "9.9.9",
                    "files": {"__init__.py": "SHOULD_NOT_WRITE = True\n"},
                    "preferences": {"panel": "BLOCKED"},
                }
            ],
        }
        manifest_path.write_text(json.dumps(second_manifest), encoding="utf-8")
        proc = run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)], ok=False)
        assert blocked_module in proc.stderr + proc.stdout or "addon" in (proc.stderr + proc.stdout).lower()
        assert out.read_text() == before_report
        assert file_snapshot(profile_root) == before_files

    def test_changed_manifest_report_write_failure_preserves_existing_profile_state(self, tmp_path):
        """A late report-path failure must not install the changed manifest."""
        marker = uuid.uuid4().hex[:8]
        keep_module = f"keep_tools_{marker}"
        new_module = f"late_tools_{marker}"
        first_addons = [
            {
                "id": f"keep-{marker}",
                "module": keep_module,
                "enabled": True,
                "version": "1.0.0",
                "files": {"__init__.py": "KEEP = 1\n"},
                "preferences": {"panel": "KEEP"},
            }
        ]
        manifest_path, first_manifest = manifest(tmp_path, marker, first_addons)
        root = tmp_path / "profiles"
        profile = f"latefail_{marker}"
        out = tmp_path / "report.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        profile_root = root / profile
        before_files = file_snapshot(profile_root)
        before_report = out.read_text()
        out_dir = tmp_path / "report-dir"
        out_dir.mkdir()

        changed_manifest = {
            **first_manifest,
            "blender_version": "4.3-late-fail",
            "addons": first_addons
            + [
                {
                    "id": f"late-{marker}",
                    "module": new_module,
                    "enabled": True,
                    "version": "2.0.0",
                    "files": {"__init__.py": "LATE = True\n"},
                    "preferences": {"panel": "LATE"},
                }
            ],
        }
        manifest_path.write_text(json.dumps(changed_manifest), encoding="utf-8")
        proc = run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out_dir)], ok=False)
        assert str(out_dir) in proc.stderr + proc.stdout
        assert out.read_text() == before_report
        assert file_snapshot(profile_root) == before_files
        assert not (profile_root / "scripts" / "addons" / new_module).exists()

    def test_changed_manifest_refuses_locally_modified_managed_files(self, tmp_path):
        """A changed manifest must not overwrite managed files edited outside blendprofile."""
        marker = uuid.uuid4().hex[:8]
        keep_module = f"keep_tools_{marker}"
        new_module = f"new_tools_{marker}"
        first_addons = [
            {
                "id": f"keep-{marker}",
                "module": keep_module,
                "enabled": True,
                "version": "1.0.0",
                "files": {"__init__.py": "KEEP = 1\n"},
                "preferences": {"panel": "KEEP"},
            }
        ]
        manifest_path, first_manifest = manifest(tmp_path, marker, first_addons)
        root = tmp_path / "profiles"
        profile = f"managed_{marker}"
        out = tmp_path / "report.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        profile_root = root / profile
        managed_path = profile_root / "config" / "managed_files.json"
        managed = json.loads(managed_path.read_text())
        assert managed["generated_by"] == "blendprofile"
        assert managed["profile"] == profile
        assert managed["file_count"] == len(managed["files"])
        assert [row["path"] for row in managed["files"]] == sorted(row["path"] for row in managed["files"])
        edited = profile_root / "scripts" / "addons" / keep_module / "__init__.py"
        edited.write_text("KEEP = 999\n", encoding="utf-8")
        before_files = file_snapshot(profile_root)
        before_report = out.read_text()

        changed_manifest = {
            **first_manifest,
            "blender_version": "4.3-managed-drift",
            "addons": first_addons
            + [
                {
                    "id": f"new-{marker}",
                    "module": new_module,
                    "enabled": True,
                    "version": "2.0.0",
                    "files": {"__init__.py": "NEW = True\n"},
                    "preferences": {"panel": "NEW"},
                }
            ],
        }
        manifest_path.write_text(json.dumps(changed_manifest), encoding="utf-8")
        proc = run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)], ok=False)
        assert proc.returncode != 0
        assert out.read_text() == before_report
        assert file_snapshot(profile_root) == before_files
        assert not (profile_root / "scripts" / "addons" / new_module).exists()

    def test_create_rejects_duplicate_and_unsafe_addons_without_stale_metadata(self, tmp_path):
        """Invalid add-on manifests must fail before writing add-on metadata."""
        marker = uuid.uuid4().hex[:8]
        root = tmp_path / "profiles"
        out = tmp_path / "report.json"
        dup_path, _ = manifest(
            tmp_path,
            marker,
            [
                {"id": "dup", "module": f"one_{marker}", "enabled": True, "version": "1", "files": {}, "preferences": {}},
                {"id": "dup", "module": f"two_{marker}", "enabled": True, "version": "1", "files": {}, "preferences": {}},
            ],
        )
        proc = run([str(BIN), "create", "--manifest", str(dup_path), "--root", str(root), "--profile", f"bad_{marker}", "--out", str(out)], ok=False)
        assert "dup" in proc.stderr + proc.stdout
        assert not out.exists()
        assert_no_addon_state(root, f"bad_{marker}")
        dup_module_path, _ = manifest(
            tmp_path,
            marker,
            [
                {"id": "one", "module": f"same_{marker}", "enabled": True, "version": "1", "files": {}, "preferences": {}},
                {"id": "two", "module": f"same_{marker}", "enabled": True, "version": "1", "files": {}, "preferences": {}},
            ],
        )
        proc = run([str(BIN), "create", "--manifest", str(dup_module_path), "--root", str(root), "--profile", f"badmodule_{marker}", "--out", str(out)], ok=False)
        assert f"same_{marker}" in proc.stderr + proc.stdout
        assert not out.exists()
        assert_no_addon_state(root, f"badmodule_{marker}")
        dup_module_malformed_path, _ = manifest(
            tmp_path,
            marker,
            [
                {"id": "one", "module": f"mixed_{marker}", "enabled": True, "version": "1", "files": {}, "preferences": {}},
                {"id": "two", "module": f"mixed_{marker}", "enabled": True, "version": "1", "files": [], "preferences": {}},
            ],
        )
        proc = run([str(BIN), "create", "--manifest", str(dup_module_malformed_path), "--root", str(root), "--profile", f"mixed_{marker}", "--out", str(out)], ok=False)
        combined = proc.stderr + proc.stdout
        assert f"mixed_{marker}" in combined
        assert "module" in combined.lower()
        assert not out.exists()
        assert_no_addon_state(root, f"mixed_{marker}")
        for index, bad_module in enumerate(["../bad", "my-addon", "123abc", "bad module", ""]):
            profile = f"badmod_{index}_{marker}"
            unsafe_module_path, _ = manifest(
                tmp_path,
                marker,
                [{"id": f"bad-module-{index}", "module": bad_module, "enabled": True, "version": "1", "files": {}, "preferences": {}}],
            )
            proc = run([str(BIN), "create", "--manifest", str(unsafe_module_path), "--root", str(root), "--profile", profile, "--out", str(out)], ok=False)
            combined = proc.stderr + proc.stdout
            assert "module" in combined.lower()
            if bad_module:
                assert bad_module in combined
            assert not out.exists()
            assert_no_addon_state(root, profile)
        unsafe_path, _ = manifest(
            tmp_path,
            marker,
            [{"id": "unsafe", "module": f"unsafe_{marker}", "enabled": True, "version": "1", "files": {"../escape.py": "x"}, "preferences": {}}],
        )
        proc = run([str(BIN), "create", "--manifest", str(unsafe_path), "--root", str(root), "--profile", f"unsafe_{marker}", "--out", str(out)], ok=False)
        assert "../escape.py" in proc.stderr + proc.stdout
        assert not out.exists()
        assert_no_addon_state(root, f"unsafe_{marker}")
        abs_path, _ = manifest(
            tmp_path,
            marker,
            [{"id": "abs", "module": f"abs_{marker}", "enabled": True, "version": "1", "files": {"/tmp/escape.py": "x"}, "preferences": {}}],
        )
        proc = run([str(BIN), "create", "--manifest", str(abs_path), "--root", str(root), "--profile", f"abs_{marker}", "--out", str(out)], ok=False)
        assert "/tmp/escape.py" in proc.stderr + proc.stdout
        assert not out.exists()
        assert_no_addon_state(root, f"abs_{marker}")
        backslash_path, _ = manifest(
            tmp_path,
            marker,
            [{"id": "backslash", "module": f"backslash_{marker}", "enabled": True, "version": "1", "files": {"ops\\tool.py": "x"}, "preferences": {}}],
        )
        proc = run([str(BIN), "create", "--manifest", str(backslash_path), "--root", str(root), "--profile", f"backslash_{marker}", "--out", str(out)], ok=False)
        combined = proc.stderr + proc.stdout
        assert "ops\\tool.py" in combined or "path" in combined.lower()
        assert not out.exists()
        assert_no_addon_state(root, f"backslash_{marker}")
        empty_path, _ = manifest(
            tmp_path,
            marker,
            [{"id": "empty-path", "module": f"emptypath_{marker}", "enabled": True, "version": "1", "files": {"": "x"}, "preferences": {}}],
        )
        proc = run([str(BIN), "create", "--manifest", str(empty_path), "--root", str(root), "--profile", f"emptypath_{marker}", "--out", str(out)], ok=False)
        combined = proc.stderr + proc.stdout
        assert "path" in combined.lower() or "unsafe" in combined.lower()
        assert not out.exists()
        assert_no_addon_state(root, f"emptypath_{marker}")
        non_string_content_path, _ = manifest(
            tmp_path,
            marker,
            [{"id": "bad-content", "module": f"content_{marker}", "enabled": True, "version": "1", "files": {"__init__.py": 7}, "preferences": {}}],
        )
        proc = run([str(BIN), "create", "--manifest", str(non_string_content_path), "--root", str(root), "--profile", f"content_{marker}", "--out", str(out)], ok=False)
        assert proc.returncode != 0
        assert not out.exists()
        assert_no_addon_state(root, f"content_{marker}")
        blocked_profile = f"blocked_{marker}"
        blocked_module = f"blocked_{marker}"
        blocked_manifest, _ = manifest(
            tmp_path,
            marker,
            [{"id": "blocked", "module": blocked_module, "enabled": True, "version": "1", "files": {"__init__.py": "x"}, "preferences": {}}],
        )
        blocked_addon_path = root / blocked_profile / "scripts" / "addons" / blocked_module
        blocked_addon_path.parent.mkdir(parents=True)
        blocked_addon_path.write_text("not a directory", encoding="utf-8")
        proc = run([str(BIN), "create", "--manifest", str(blocked_manifest), "--root", str(root), "--profile", blocked_profile, "--out", str(out)], ok=False)
        assert blocked_module in proc.stderr + proc.stdout or "addon" in (proc.stderr + proc.stdout).lower()
        assert not out.exists()
        assert_no_addon_state(root, blocked_profile)
