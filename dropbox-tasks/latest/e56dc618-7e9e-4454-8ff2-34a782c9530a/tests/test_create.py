import ast
import configparser
import grp
import hashlib
import json
import os
import pwd
import re
import shlex
import shutil
import subprocess
import uuid
from pathlib import Path


BIN = Path("/usr/local/bin/blendprofile")
UNIT = Path("/etc/systemd/system/blendprofile-reconcile@.service")
TMPFILES = Path("/usr/lib/tmpfiles.d/blendprofile.conf")


def run(args, ok=True):
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    if ok:
        assert proc.returncode == 0, proc.stderr + proc.stdout
    else:
        assert proc.returncode != 0
    return proc


def exported_value(script_text, key):
    prefix = f"export {key}="
    for line in script_text.splitlines():
        if line.startswith(prefix):
            value = line[len(prefix):].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            return value
    raise AssertionError(f"missing export for {key}")


def assignment_value(script_text, name):
    match = re.search(rf"^{re.escape(name)}\s*=\s*(.+)$", script_text, re.MULTILINE)
    assert match, f"missing assignment for {name}"
    return ast.literal_eval(match.group(1))


def write_manifest(tmp_path, marker):
    manifest = {
        "blender_version": "4.2-test",
        "python_expr": f"print('boot-{marker}')",
        "env": {"BLENDER_VERBOSE": "0", "PROFILE_MARKER": marker},
        "profile_settings": {"theme": f"studio-{marker}", "unit_system": "METRIC"},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, manifest


class TestCreateContract:
    def test_host_controller_installs_hardened_systemd_and_tmpfiles_policy(self, tmp_path):
        """The render-node controller must be installed as hardened host configuration."""
        account = pwd.getpwnam("blender-profile")
        group = grp.getgrnam("blender-profile")
        assert account.pw_gid == group.gr_gid
        assert account.pw_shell == "/usr/sbin/nologin"
        assert UNIT.is_file()
        assert TMPFILES.is_file()
        assert UNIT.stat().st_mode & 0o777 == 0o644
        assert TMPFILES.stat().st_mode & 0o777 == 0o644

        unit = configparser.ConfigParser(interpolation=None)
        unit.optionxform = str
        unit.read(UNIT, encoding="utf-8")
        assert unit["Unit"]["After"] == "local-fs.target"
        assert unit["Unit"]["ConditionPathIsFile"] == "/etc/blender-profiles/%i.json"
        service = unit["Service"]
        assert service["Type"] == "oneshot"
        assert service["User"] == "blender-profile"
        assert service["Group"] == "blender-profile"
        assert service["UMask"] == "0027"
        assert service["NoNewPrivileges"] == "yes"
        assert service["PrivateTmp"] == "yes"
        assert service["ProtectSystem"] == "strict"
        assert service["ProtectHome"] == "yes"
        assert service["ReadOnlyPaths"] == "/etc/blender-profiles"
        assert service["ReadWritePaths"].split() == ["/var/lib/blender-profiles", "/run/blendprofile"]
        assert unit["Install"]["WantedBy"] == "multi-user.target"
        expected_exec = (
            "/usr/local/bin/blendprofile create --manifest /etc/blender-profiles/%i.json "
            "--root /var/lib/blender-profiles --profile %i --out /run/blendprofile/%i.json"
        )
        assert service["ExecStart"] == expected_exec

        entries = [line for line in TMPFILES.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
        assert entries == [
            "d /var/lib/blender-profiles 0750 blender-profile blender-profile -",
            "d /run/blendprofile 0750 blender-profile blender-profile -",
        ]

        marker = uuid.uuid4().hex[:8]
        profile = f"render_{marker}"
        source_manifest, _ = write_manifest(tmp_path, marker)
        manifest = Path("/etc/blender-profiles") / f"{profile}.json"
        report = Path("/run/blendprofile") / f"{profile}.json"
        profile_root = Path("/var/lib/blender-profiles") / profile
        manifest.parent.mkdir(parents=True, exist_ok=True)
        report.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_bytes(source_manifest.read_bytes())
        try:
            command = shlex.split(service["ExecStart"].replace("%i", profile))
            run(command)
            assert json.loads(report.read_text(encoding="utf-8"))["profile"] == profile
            assert (profile_root / "bin" / f"blender-{profile}").is_file()
        finally:
            manifest.unlink(missing_ok=True)
            report.unlink(missing_ok=True)
            shutil.rmtree(profile_root, ignore_errors=True)

    def test_create_profile_layout_wrapper_bootstrap_and_report(self, tmp_path):
        """create must build the portable Blender profile layout from a runtime manifest."""
        assert BIN.exists()
        marker = uuid.uuid4().hex[:8]
        profile = f"artist_{marker}"
        manifest_path, manifest = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        out = tmp_path / "report.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        profile_root = root / profile
        expected_dirs = ["bin", "cache", "config", "logs", "scripts", "scripts/addons", "startup"]
        for rel in expected_dirs:
            assert (profile_root / rel).is_dir()
        wrapper = profile_root / "bin" / f"blender-{profile}"
        bootstrap = profile_root / "startup" / "bootstrap.py"
        assert wrapper.exists()
        assert os.access(wrapper, os.X_OK)
        wrapper_text = wrapper.read_text()
        assert exported_value(wrapper_text, "BLENDER_USER_CONFIG") == str(profile_root / "config")
        assert exported_value(wrapper_text, "BLENDER_USER_SCRIPTS") == str(profile_root / "scripts")
        assert exported_value(wrapper_text, "BLENDER_USER_DATA") == str(profile_root)
        assert exported_value(wrapper_text, "BLENDER_USER_CACHE") == str(profile_root / "cache")
        assert 'exec blender "$@"' in wrapper_text
        boot = bootstrap.read_text()
        manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        assert assignment_value(boot, "PROFILE_NAME") == profile
        assert assignment_value(boot, "BLENDER_VERSION") == "4.2-test"
        assert assignment_value(boot, "PYTHON_EXPR") == manifest["python_expr"]
        assert assignment_value(boot, "PROFILE_ENV") == manifest["env"]
        assert assignment_value(boot, "PROFILE_SETTINGS") == manifest["profile_settings"]
        assert assignment_value(boot, "MANIFEST_SHA256") == manifest_sha
        raw_report = out.read_text()
        payload = json.loads(raw_report)
        assert raw_report == json.dumps(payload, indent=2, sort_keys=True) + "\n"
        assert payload["generated_by"] == "blendprofile"
        assert payload["profile"] == profile
        assert payload["profile_root"] == str(profile_root.resolve())
        assert payload["directories"] == sorted(str((profile_root / rel).resolve()) for rel in expected_dirs)
        assert payload["wrapper_path"] == str(wrapper.resolve())
        assert payload["bootstrap_path"] == str(bootstrap.resolve())
        assert payload["blender_version"] == manifest["blender_version"]
        assert payload["manifest_sha256"] == manifest_sha
        assert payload["dry_run"] is False
        assert payload["profile_audit_path"] == str((profile_root / "config" / "profile_audit.json").resolve())
        assert payload["generation_ledger_path"] == str((profile_root / "config" / "generation_ledger.jsonl").resolve())
        assert payload["generation_state_path"] == str((profile_root / "config" / "generation_state.json").resolve())
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out)])
        assert wrapper.read_text() == wrapper_text
        assert bootstrap.read_text() == boot
        assert out.read_text() == raw_report
        dotted_profile = f"artist-{marker}.portable"
        dotted_out = tmp_path / "dotted-report.json"
        run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", dotted_profile, "--out", str(dotted_out)])
        dotted_payload = json.loads(dotted_out.read_text())
        dotted_root = root / dotted_profile
        assert dotted_payload["profile"] == dotted_profile
        assert dotted_payload["profile_root"] == str(dotted_root.resolve())
        assert (dotted_root / "bin" / f"blender-{dotted_profile}").exists()

    def test_create_rejects_bad_inputs_without_partial_report(self, tmp_path):
        """Missing flags, invalid profiles, bad manifests, and file roots must fail cleanly."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, _ = write_manifest(tmp_path, marker)
        out = tmp_path / "partial.json"
        proc = run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(tmp_path / "r"), "--profile", "p"], ok=False)
        assert "--out" in proc.stderr + proc.stdout
        assert not out.exists()
        for bad_name in ["../bad", "", "foo/bar", "has spaces", "na$me", "na!me", "na\u00f1me", "name\ttab"]:
            proc = run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(tmp_path / "r"), "--profile", bad_name, "--out", str(out)], ok=False)
            combined = proc.stderr + proc.stdout
            assert "profile" in combined.lower()
            if bad_name:
                assert bad_name in combined
            assert not out.exists()
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text("{not-json", encoding="utf-8")
        proc = run([str(BIN), "create", "--manifest", str(bad_manifest), "--root", str(tmp_path / "r"), "--profile", "safe", "--out", str(out)], ok=False)
        assert str(bad_manifest) in proc.stderr + proc.stdout
        assert not out.exists()
        missing_manifest = tmp_path / "missing.json"
        proc = run([str(BIN), "create", "--manifest", str(missing_manifest), "--root", str(tmp_path / "r"), "--profile", "safe", "--out", str(out)], ok=False)
        assert str(missing_manifest) in proc.stderr + proc.stdout
        assert not out.exists()
        root_file = tmp_path / "root-file"
        root_file.write_text("x", encoding="utf-8")
        proc = run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root_file), "--profile", "safe", "--out", str(out)], ok=False)
        assert str(root_file) in proc.stderr + proc.stdout
        assert not out.exists()
        parent_file = tmp_path / "not-a-directory"
        parent_file.write_text("x", encoding="utf-8")
        bad_out = parent_file / "report.json"
        proc = run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(tmp_path / "r2"), "--profile", "safe", "--out", str(bad_out)], ok=False)
        assert str(bad_out) in proc.stderr + proc.stdout
        assert not bad_out.exists()

    def test_create_preflights_manifest_output_and_profile_root_before_writes(self, tmp_path):
        """Schema errors, directory outputs, and profile symlinks must not create profile files."""
        marker = uuid.uuid4().hex[:8]
        manifest_path, manifest = write_manifest(tmp_path, marker)
        root = tmp_path / "profiles"
        out_dir = tmp_path / "out-dir"
        out_dir.mkdir()
        profile = f"outfail_{marker}"
        proc = run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", profile, "--out", str(out_dir)], ok=False)
        assert str(out_dir) in proc.stderr + proc.stdout
        assert not (root / profile).exists()

        bad_cases = [
            ("missing_version", {k: v for k, v in manifest.items() if k != "blender_version"}, "blender_version"),
            ("bad_expr", {**manifest, "python_expr": 17}, "python_expr"),
            ("bad_env", {**manifest, "env": {"OK": "1", "BAD": 2}}, "env"),
            ("bad_settings", {**manifest, "profile_settings": ["not", "object"]}, "profile_settings"),
        ]
        for label, data, expected in bad_cases:
            bad_manifest = tmp_path / f"{label}.json"
            bad_manifest.write_text(json.dumps(data), encoding="utf-8")
            bad_profile = f"{label}_{marker}"
            bad_out = tmp_path / f"{label}.json.out"
            proc = run([str(BIN), "create", "--manifest", str(bad_manifest), "--root", str(root), "--profile", bad_profile, "--out", str(bad_out)], ok=False)
            assert expected in proc.stderr + proc.stdout
            assert not bad_out.exists()
            assert not (root / bad_profile).exists()

        outside = tmp_path / "outside"
        outside.mkdir()
        root.mkdir(exist_ok=True)
        linked_profile = f"linked_{marker}"
        (root / linked_profile).symlink_to(outside, target_is_directory=True)
        link_out = tmp_path / "linked.json"
        proc = run([str(BIN), "create", "--manifest", str(manifest_path), "--root", str(root), "--profile", linked_profile, "--out", str(link_out)], ok=False)
        combined = proc.stderr + proc.stdout
        assert linked_profile in combined or "profile" in combined.lower()
        assert not link_out.exists()
        assert list(outside.iterdir()) == []
