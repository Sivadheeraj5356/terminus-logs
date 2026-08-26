import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path

from test_addons import TestAddonContract as _TestAddonContract
from test_create import TestCreateContract as _TestCreateContract


BIN = Path("/usr/local/bin/blendprofile")
ZERO_HASH = "0" * 64


def run(args, ok=True):
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    if ok:
        assert proc.returncode == 0, proc.stderr + proc.stdout
    else:
        assert proc.returncode != 0
    return proc


def addon_content_sha(files):
    digest = hashlib.sha256()
    for name, content in sorted(files.items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def compact_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def generation_hash(record):
    unsigned = {key: value for key, value in record.items() if key != "record_hash"}
    return hashlib.sha256(compact_json(unsigned).encode("utf-8")).hexdigest()


def assert_lineage_problem(payload, sentinel):
    assert payload["ok"] is False
    assert sentinel in payload["lineage_mismatches"]
    assert payload["issues"] == sorted(payload["issues"])
    assert any(sentinel in issue and "lineage" in issue for issue in payload["issues"])


def write_manifest(tmp_path, marker):
    data = {
        "blender_version": "4.4-validate",
        "python_expr": f"print('validate-{marker}')",
        "env": {"PROFILE_MARKER": marker},
        "profile_settings": {"theme": "studio", "unit_system": "METRIC"},
        "addons": [
            {
                "id": f"rig-{marker}",
                "module": f"zrig_tools_{marker}",
                "enabled": True,
                "version": "2.0.0",
                "files": {"__init__.py": "REGISTER = True\n"},
                "preferences": {"panel": "RIG"},
            },
            {
                "id": f"anim-{marker}",
                "module": f"aanim_tools_{marker}",
                "enabled": True,
                "version": "1.5.0",
                "files": {"__init__.py": "ANIM = True\n"},
                "preferences": {"panel": "ANIM"},
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


def write_dependency_manifest(tmp_path, marker):
    core = f"a_core_tools_{marker}"
    color = f"b_color_math_{marker}"
    paint = f"c_paint_stack_{marker}"
    render = f"d_render_bridge_{marker}"
    final = f"e_finalizer_{marker}"
    data = {
        "blender_version": "4.4-graph",
        "python_expr": f"print('graph-{marker}')",
        "env": {"PROFILE_MARKER": marker},
        "profile_settings": {"theme": "graph"},
        "addons": [
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
        ],
    }
    path = tmp_path / "dependency_manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    expected_order = [core, color, paint, render, final]
    expected_edges = sorted([f"{core}->{paint}", f"{color}->{paint}", f"{paint}->{render}", f"{render}->{final}"])
    return path, data, expected_order, expected_edges


class TestCreateContract(_TestCreateContract):
    """Expose create coverage through the single-step verifier entry point."""


class TestAddonContract(_TestAddonContract):
    """Expose add-on coverage through the single-step verifier entry point."""


class TestValidationContract:
    def test_validate_reports_complete_profile_and_checks_exports(self, tmp_path):
        """validate must inspect existing files without mutating them."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, manifest = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"validate_{marker}"
        create_out = tmp_path / "create.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(create_out)])
        profile_root = root / profile
        before_snapshot = {str(path.relative_to(profile_root)): path.read_bytes() for path in profile_root.rglob("*") if path.is_file()}
        wrapper = root / profile / "bin" / f"blender-{profile}"
        before = wrapper.read_text()
        out = tmp_path / "validate.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        after_snapshot = {str(path.relative_to(profile_root)): path.read_bytes() for path in profile_root.rglob("*") if path.is_file()}
        payload = json.loads(out.read_text())
        assert payload["generated_by"] == "blendprofile"
        assert payload["profile"] == profile
        assert payload["profile_root"] == str((root / profile).resolve())
        assert payload["ok"] is True
        assert payload["missing_paths"] == []
        assert payload["unexpected_addons"] == []
        assert payload["unexpected_addon_files"] == []
        assert payload["unsafe_addon_paths"] == []
        assert payload["mismatched_exports"] == []
        assert payload["lock_mismatches"] == []
        assert payload["audit_mismatches"] == []
        assert payload["lineage_mismatches"] == []
        assert payload["enabled_modules"] == [f"aanim_tools_{marker}", f"zrig_tools_{marker}"]
        assert payload["addon_count"] == 2
        assert payload["issues"] == []
        assert payload["checked_paths"] == sorted(payload["checked_paths"])
        assert all(os.path.isabs(path) for path in payload["checked_paths"])
        expected_dirs = ["bin", "cache", "config", "logs", "scripts", "scripts/addons", "startup"]
        expected_checked = [profile_root / rel for rel in expected_dirs]
        expected_checked.extend(
            [
                wrapper,
                profile_root / "startup" / "bootstrap.py",
                profile_root / "config" / "enabled_addons.json",
                profile_root / "config" / "addons.lock.json",
            ]
        )
        for addon in manifest["addons"]:
            addon_dir = profile_root / "scripts" / "addons" / addon["module"]
            expected_checked.append(addon_dir / "addon_manifest.json")
            for fname in addon["files"]:
                expected_checked.append(addon_dir / fname)
        for path in expected_checked:
            assert str(path.resolve()) in payload["checked_paths"]
        assert str(wrapper.resolve()) in payload["checked_paths"]
        assert str((root / profile / "config" / "addons.lock.json").resolve()) in payload["checked_paths"]
        assert str((root / profile / "config" / "profile_audit.json").resolve()) in payload["checked_paths"]
        assert wrapper.read_text() == before
        assert after_snapshot == before_snapshot

    def test_generation_ledger_is_chained_manifest_sensitive_and_idempotent(self, tmp_path):
        """Changed generations advance a canonical chain while identical reruns do not."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, manifest = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"lineage_{marker}"
        first_out = tmp_path / "first.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(first_out)])
        profile_root = root / profile
        ledger_path = profile_root / "config" / "generation_ledger.jsonl"
        state_path = profile_root / "config" / "generation_state.json"
        first_report = json.loads(first_out.read_text())
        first_lines = ledger_path.read_text().splitlines()
        assert len(first_lines) == 1
        first = json.loads(first_lines[0])
        assert first_lines[0] == compact_json(first)
        assert first["generation"] == 1
        assert first["previous_hash"] == ZERO_HASH
        assert first["record_hash"] == generation_hash(first)
        assert first_report["generation"] == 1
        assert first_report["generation_hash"] == first["record_hash"]
        assert json.loads(state_path.read_text())["head_hash"] == first["record_hash"]

        ledger_before = ledger_path.read_bytes()
        second_out = tmp_path / "second.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(second_out)])
        assert ledger_path.read_bytes() == ledger_before
        assert second_out.read_bytes() == first_out.read_bytes()

        manifest["profile_settings"]["theme"] = f"studio-{marker}"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        third_out = tmp_path / "third.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(third_out)])
        lines = ledger_path.read_text().splitlines()
        assert len(lines) == 2
        records = [json.loads(line) for line in lines]
        assert all(line == compact_json(record) for line, record in zip(lines, records))
        assert records[1]["generation"] == 2
        assert records[1]["previous_hash"] == records[0]["record_hash"]
        assert records[1]["record_hash"] == generation_hash(records[1])
        assert json.loads(third_out.read_text())["generation"] == 2

    def test_validate_detects_generation_order_chain_head_and_manifest_drift(self, tmp_path):
        """Lineage validation checks sequence, record links, state head, and manifest binding."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, manifest = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"chain_{marker}"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(tmp_path / "create.json")])
        manifest["env"][next(iter(manifest["env"]))] = f"{marker}-second"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(tmp_path / "changed.json")])
        config = root / profile / "config"
        ledger = config / "generation_ledger.jsonl"
        state = config / "generation_state.json"
        ledger_bytes = ledger.read_bytes()
        state_bytes = state.read_bytes()
        manifest_bytes = manifest_path.read_bytes()

        def validate(name):
            out = tmp_path / f"validate-{name}.json"
            run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
            return json.loads(out.read_text())

        records = [json.loads(line) for line in ledger.read_text().splitlines()]
        records[1]["generation"] = 7
        ledger.write_text("".join(compact_json(row) + "\n" for row in records), encoding="utf-8")
        assert_lineage_problem(validate("order"), "__order__")
        ledger.write_bytes(ledger_bytes)

        records = [json.loads(line) for line in ledger.read_text().splitlines()]
        records[1]["previous_hash"] = "f" * 64
        ledger.write_text("".join(compact_json(row) + "\n" for row in records), encoding="utf-8")
        assert_lineage_problem(validate("chain"), "__chain__")
        ledger.write_bytes(ledger_bytes)

        head = json.loads(state.read_text())
        head["head_hash"] = "e" * 64
        state.write_text(json.dumps(head), encoding="utf-8")
        assert_lineage_problem(validate("head"), "__head__")
        state.write_bytes(state_bytes)

        changed_manifest = json.loads(manifest_path.read_text())
        changed_manifest["blender_version"] = f"4.4-uncommitted-{marker}"
        manifest_path.write_text(json.dumps(changed_manifest), encoding="utf-8")
        assert_lineage_problem(validate("manifest-drift"), "__manifest__")
        manifest_path.write_bytes(manifest_bytes)

    def test_lineage_head_binds_managed_index_and_profile_audit(self, tmp_path):
        """The committed head binds the exact managed-index and profile-audit bytes."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, _ = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"bindings_{marker}"
        create_out = tmp_path / "create.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(create_out)])
        config = root / profile / "config"
        managed = config / "managed_files.json"
        audit = config / "profile_audit.json"
        managed_original = managed.read_bytes()
        audit_original = audit.read_bytes()

        managed.write_bytes(managed.read_bytes() + b" ")
        managed_out = tmp_path / "managed-binding.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(managed_out)])
        assert_lineage_problem(json.loads(managed_out.read_text()), "__managed__")
        managed.write_bytes(managed_original)
        audit.write_bytes(audit.read_bytes() + b" ")
        audit_out = tmp_path / "audit-binding.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(audit_out)])
        assert_lineage_problem(json.loads(audit_out.read_text()), "__audit__")
        audit.write_bytes(audit_original)

    def test_failed_changed_manifest_does_not_advance_generation_lineage(self, tmp_path):
        """A preflight failure cannot append a generation or replace the committed head."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, manifest = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"atomiclineage_{marker}"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(tmp_path / "create.json")])
        config = root / profile / "config"
        ledger = config / "generation_ledger.jsonl"
        state = config / "generation_state.json"
        before = (ledger.read_bytes(), state.read_bytes())
        blocked_module = f"blocked_{marker}"
        blocked = root / profile / "scripts" / "addons" / blocked_module
        blocked.write_text("not a directory", encoding="utf-8")
        manifest["addons"].append(
            {
                "id": f"blocked-{marker}",
                "module": blocked_module,
                "enabled": True,
                "version": "1.0.0",
                "files": {"__init__.py": "BLOCKED = True\n"},
                "preferences": {},
            }
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        failed_out = tmp_path / "failed.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(failed_out)], ok=False)
        assert not failed_out.exists()
        assert before == (ledger.read_bytes(), state.read_bytes())

    def test_validate_detects_dependency_order_and_edge_mismatches(self, tmp_path):
        """Validation must check derived dependency order and edge metadata."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, _, expected_order, expected_edges = write_dependency_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"depgraph_{marker}"
        create_out = tmp_path / "create.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(create_out)])
        profile_root = root / profile
        out = tmp_path / "validate.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        payload = json.loads(out.read_text())
        assert payload["ok"] is True
        assert payload["addon_load_order"] == expected_order
        assert payload["dependency_edges"] == expected_edges
        assert payload["dependency_mismatches"] == []

        enabled_path = profile_root / "config" / "enabled_addons.json"
        enabled_payload = json.loads(enabled_path.read_text())
        enabled_payload["addon_load_order"] = list(reversed(expected_order))
        enabled_payload["dependency_edges"] = expected_edges[:-1]
        enabled_path.write_text(json.dumps(enabled_payload, sort_keys=True), encoding="utf-8")
        lock_path = profile_root / "config" / "addons.lock.json"
        lock_payload = json.loads(lock_path.read_text())
        lock_payload["addon_load_order"] = list(reversed(expected_order))
        lock_payload["dependency_edges"] = expected_edges[:-1]
        lock_path.write_text(json.dumps(lock_payload, sort_keys=True), encoding="utf-8")

        broken_out = tmp_path / "validate-broken.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(broken_out)])
        broken = json.loads(broken_out.read_text())
        assert broken["ok"] is False
        assert broken["dependency_mismatches"] == ["__enabled_edges__", "__enabled_order__", "__lock_edges__", "__lock_order__"]
        assert broken["issues"] == sorted(broken["issues"])
        for sentinel in broken["dependency_mismatches"]:
            assert any(sentinel in issue and "dependency" in issue for issue in broken["issues"])

    def test_validate_detects_managed_file_index_mismatches(self, tmp_path):
        """Validation checks the managed path set and current owned-file bytes."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, _ = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"managedindex_{marker}"
        create_out = tmp_path / "create.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(create_out)])
        profile_root = root / profile
        clean_out = tmp_path / "validate-clean.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(clean_out)])
        clean = json.loads(clean_out.read_text())
        managed_path = profile_root / "config" / "managed_files.json"
        managed = json.loads(managed_path.read_text())
        assert clean["ok"] is True
        assert clean["managed_mismatches"] == []
        assert clean["managed_file_count"] == managed["file_count"]
        assert str(managed_path.resolve()) in clean["checked_paths"]

        original_index = managed_path.read_bytes()
        paths_payload = dict(managed)
        paths_payload["file_count"] = managed["file_count"] + 1
        managed_path.write_text(json.dumps(paths_payload, sort_keys=True), encoding="utf-8")
        paths_out = tmp_path / "validate-managed-paths.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(paths_out)])
        paths = json.loads(paths_out.read_text())
        assert "__paths__" in paths["managed_mismatches"]
        assert any("__paths__" in issue and "managed" in issue for issue in paths["issues"])
        managed_path.write_bytes(original_index)

        module = f"zrig_tools_{marker}"
        edited_rel = f"scripts/addons/{module}/__init__.py"
        edited = profile_root / edited_rel
        edited.write_text("REGISTER = False\n", encoding="utf-8")

        out = tmp_path / "validate-managed.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        payload = json.loads(out.read_text())
        expected = [edited_rel]
        assert payload["ok"] is False
        assert payload["managed_mismatches"] == expected
        assert payload["issues"] == sorted(payload["issues"])
        for entry in expected:
            assert any(entry in issue and "managed" in issue for issue in payload["issues"])

    def test_validate_detects_profile_audit_cross_file_mismatches(self, tmp_path):
        """Validation must cross-check the profile audit artifact against current files."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, manifest = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"audit_{marker}"
        create_out = tmp_path / "create.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(create_out)])
        profile_root = root / profile
        audit_path = profile_root / "config" / "profile_audit.json"
        clean_out = tmp_path / "validate-audit-clean.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(clean_out)])
        clean = json.loads(clean_out.read_text())
        assert clean["ok"] is True
        assert clean["audit_mismatches"] == []
        assert str(audit_path.resolve()) in clean["checked_paths"]
        audit = json.loads(audit_path.read_text())
        modules = sorted(addon["module"] for addon in manifest["addons"])
        assert sorted(audit["addon_manifest_sha256"]) == modules
        assert sorted(audit["addon_content_sha256"]) == modules
        for addon in manifest["addons"]:
            module = addon["module"]
            manifest_file = profile_root / "scripts" / "addons" / module / "addon_manifest.json"
            assert audit["addon_manifest_sha256"][module] == hashlib.sha256(manifest_file.read_bytes()).hexdigest()
            assert audit["addon_content_sha256"][module] == addon_content_sha(addon["files"])

        broken = dict(audit)
        broken["generated_by"] = "other-tool"
        broken["wrapper_sha256"] = "2" * 64
        broken["bootstrap_sha256"] = "3" * 64
        broken["enabled_addons_sha256"] = "4" * 64
        broken["addons_lock_sha256"] = "5" * 64
        broken["managed_files_sha256"] = "0" * 64
        broken["dependency_edges"] = ["wrong->edge"]
        broken["addon_manifest_sha256"] = dict(audit["addon_manifest_sha256"])
        broken["addon_manifest_sha256"][modules[0]] = "6" * 64
        broken["addon_content_sha256"] = dict(audit["addon_content_sha256"])
        broken["addon_content_sha256"][modules[-1]] = "1" * 64
        audit_path.write_text(json.dumps(broken, sort_keys=True), encoding="utf-8")
        broken_out = tmp_path / "validate-audit-broken.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(broken_out)])
        payload = json.loads(broken_out.read_text())
        expected = sorted(
            [
                "__metadata__",
                "__wrapper__",
                "__bootstrap__",
                "__enabled__",
                "__lock__",
                "__managed__",
                "__graph__",
                f"{modules[0]}:addon_manifest",
                f"{modules[-1]}:addon_files",
            ]
        )
        assert payload["ok"] is False
        assert payload["audit_mismatches"] == expected
        for entry in expected:
            assert any(entry in issue and "audit" in issue for issue in payload["issues"])

        audit_path.unlink()
        missing_out = tmp_path / "validate-audit-missing.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(missing_out)])
        missing = json.loads(missing_out.read_text())
        assert "__missing_audit__" in missing["audit_mismatches"]
        assert any("__missing_audit__" in issue and "audit" in issue for issue in missing["issues"])

        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(create_out)])
        repaired_out = tmp_path / "validate-audit-repaired.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(repaired_out)])
        repaired = json.loads(repaired_out.read_text())
        assert repaired["ok"] is True
        assert repaired["audit_mismatches"] == []

    def test_validate_detects_missing_paths_and_bad_wrapper_exports(self, tmp_path):
        """Validation must report missing files and wrapper export mismatches."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, _ = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"broken_{marker}"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(tmp_path / "create.json")])
        profile_root = root / profile
        (profile_root / "startup" / "bootstrap.py").unlink()
        (profile_root / "config" / "enabled_addons.json").unlink()
        wrapper = profile_root / "bin" / f"blender-{profile}"
        wrapper.write_text(
            wrapper.read_text()
            .replace("BLENDER_USER_CACHE=", "BROKEN_CACHE=")
            .replace("BLENDER_USER_CONFIG=", "BROKEN_CONFIG=")
        )
        out = tmp_path / "broken.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        payload = json.loads(out.read_text())
        assert payload["ok"] is False
        assert payload["missing_paths"] == sorted(payload["missing_paths"])
        assert str((profile_root / "startup" / "bootstrap.py").resolve()) in payload["missing_paths"]
        assert str((profile_root / "config" / "enabled_addons.json").resolve()) in payload["missing_paths"]
        assert "BLENDER_USER_CACHE" in payload["mismatched_exports"]
        assert "BLENDER_USER_CONFIG" in payload["mismatched_exports"]
        assert payload["mismatched_exports"] == sorted(payload["mismatched_exports"])
        assert payload["issues"] == sorted(payload["issues"])

    def test_validate_detects_bootstrap_and_enabled_metadata_mismatches(self, tmp_path):
        """Validation must compare bootstrap assignments and enabled add-on metadata."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, _ = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"enabled_{marker}"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(tmp_path / "create.json")])
        profile_root = root / profile
        bootstrap = profile_root / "startup" / "bootstrap.py"
        bootstrap.write_text(bootstrap.read_text().replace("MANIFEST_SHA256", "BROKEN_MANIFEST_SHA256"), encoding="utf-8")
        enabled_path = profile_root / "config" / "enabled_addons.json"
        enabled_payload = json.loads(enabled_path.read_text())
        enabled_payload["enabled_modules"] = enabled_payload["enabled_modules"][1:]
        enabled_payload["addons"][0]["id"] = "wrong-id"
        enabled_path.write_text(json.dumps(enabled_payload), encoding="utf-8")
        out = tmp_path / "enabled.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        payload = json.loads(out.read_text())
        assert payload["ok"] is False
        assert payload["issues"] == sorted(payload["issues"])
        assert any("bootstrap" in issue for issue in payload["issues"])
        assert any("enabled" in issue for issue in payload["issues"])

    def test_validate_detects_addon_metadata_mismatches(self, tmp_path):
        """Validation must compare add-on manifests against the source manifest."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, _ = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"metadata_{marker}"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(tmp_path / "create.json")])
        addon_manifest = root / profile / "scripts" / "addons" / f"zrig_tools_{marker}" / "addon_manifest.json"
        data = json.loads(addon_manifest.read_text())
        data["version"] = "9.9.9"
        addon_manifest.write_text(json.dumps(data), encoding="utf-8")
        out = tmp_path / "metadata.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        payload = json.loads(out.read_text())
        assert payload["ok"] is False
        assert payload["issues"] == sorted(payload["issues"])
        assert any(f"zrig_tools_{marker}" in issue and "metadata" in issue for issue in payload["issues"])

    def test_validate_detects_unexpected_stale_addon_modules(self, tmp_path):
        """Validation must report add-on module directories absent from the manifest."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, _ = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"unexpected_{marker}"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(tmp_path / "create.json")])
        extra_module = f"orphan_tools_{marker}"
        extra_dir = root / profile / "scripts" / "addons" / extra_module
        extra_dir.mkdir()
        (extra_dir / "__init__.py").write_text("ORPHAN = True\n", encoding="utf-8")
        (extra_dir / "addon_manifest.json").write_text(json.dumps({"module": extra_module}), encoding="utf-8")
        out = tmp_path / "unexpected.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        payload = json.loads(out.read_text())
        assert payload["ok"] is False
        assert payload["unexpected_addons"] == [extra_module]
        assert payload["issues"] == sorted(payload["issues"])
        assert any(extra_module in issue and "unexpected" in issue for issue in payload["issues"])

    def test_validate_detects_unexpected_files_inside_declared_addons(self, tmp_path):
        """Validation must report stale files inside a declared add-on module."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, _ = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"unexpected_file_{marker}"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(tmp_path / "create.json")])
        module = f"zrig_tools_{marker}"
        stale = root / profile / "scripts" / "addons" / module / "nested" / "stale.py"
        stale.parent.mkdir()
        stale.write_text("STALE = True\n", encoding="utf-8")
        out = tmp_path / "unexpected-file.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        payload = json.loads(out.read_text())
        expected = f"{module}:nested/stale.py"
        assert payload["ok"] is False
        assert payload["unexpected_addon_files"] == [expected]
        assert payload["issues"] == sorted(payload["issues"])
        assert any(expected in issue and "unexpected" in issue for issue in payload["issues"])

    def test_validate_detects_lock_and_file_hash_mismatches(self, tmp_path):
        """Validation must detect add-on file content that no longer matches the lockfile."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, manifest = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"lock_{marker}"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(tmp_path / "create.json")])
        tampered_modules = [f"zrig_tools_{marker}", f"aanim_tools_{marker}"]
        target = root / profile / "scripts" / "addons" / tampered_modules[0] / "__init__.py"
        target2 = root / profile / "scripts" / "addons" / tampered_modules[1] / "__init__.py"
        assert addon_content_sha(manifest["addons"][0]["files"])
        target.write_text("REGISTER = False\n", encoding="utf-8")
        target2.write_text("ANIM = False\n", encoding="utf-8")
        out = tmp_path / "lock.json"
        run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        payload = json.loads(out.read_text())
        assert payload["ok"] is False
        assert payload["lock_mismatches"] == sorted(tampered_modules)
        assert len(payload["lock_mismatches"]) == 2
        assert payload["issues"] == sorted(payload["issues"])
        for tampered_module in tampered_modules:
            assert any(tampered_module in issue and "lock" in issue for issue in payload["issues"])

    def test_create_dry_run_and_validate_bad_inputs_do_not_create_profile(self, tmp_path):
        """Dry-run reports the plan without creating profile files."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, manifest = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        profile = f"dry_{marker}"
        out = tmp_path / "dry.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out), "--dry-run"])
        payload = json.loads(out.read_text())
        profile_root = root / profile
        expected_dirs = ["bin", "cache", "config", "logs", "scripts", "scripts/addons", "startup"]
        expected_modules = sorted(addon["module"] for addon in manifest["addons"])
        assert payload["dry_run"] is True
        assert payload["generation"] == 0
        assert payload["generation_hash"] == ZERO_HASH
        assert payload["generated_by"] == "blendprofile"
        assert payload["profile"] == profile
        assert payload["profile_root"] == str(profile_root.resolve())
        assert payload["directories"] == sorted(str((profile_root / rel).resolve()) for rel in expected_dirs)
        assert payload["wrapper_path"] == str((profile_root / "bin" / f"blender-{profile}").resolve())
        assert payload["bootstrap_path"] == str((profile_root / "startup" / "bootstrap.py").resolve())
        assert payload["blender_version"] == manifest["blender_version"]
        assert payload["manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        assert payload["addon_count"] == len(manifest["addons"])
        assert payload["addon_file_count"] == sum(len(addon["files"]) for addon in manifest["addons"])
        assert payload["enabled_addons"] == expected_modules
        assert payload["addon_manifests"] == sorted(
            str((profile_root / "scripts" / "addons" / addon["module"] / "addon_manifest.json").resolve()) for addon in manifest["addons"]
        )
        assert payload["addon_lock_path"] == str((profile_root / "config" / "addons.lock.json").resolve())
        assert not (root / profile).exists()
        proc = run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", "../bad", "--out", str(tmp_path / "bad.json")], ok=False)
        assert "profile" in (proc.stderr + proc.stdout).lower()
        assert not (tmp_path / "bad.json").exists()
        proc = run([str(BIN), "validate", "--root", str(root), "--profile", profile, "--out", str(tmp_path / "missing_manifest.json")], ok=False)
        assert "manifest" in (proc.stderr + proc.stdout).lower()
        missing_manifest = tmp_path / "missing.json"
        proc = run([str(BIN), "validate", "--manifest", str(missing_manifest), "--root", str(root), "--profile", profile, "--out", str(tmp_path / "missing.json.out")], ok=False)
        assert str(missing_manifest) in proc.stderr + proc.stdout
        parent_file = tmp_path / "not-a-directory"
        parent_file.write_text("x", encoding="utf-8")
        bad_out = parent_file / "validate.json"
        proc = run([str(BIN), "validate", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(bad_out)], ok=False)
        assert str(bad_out) in proc.stderr + proc.stdout
