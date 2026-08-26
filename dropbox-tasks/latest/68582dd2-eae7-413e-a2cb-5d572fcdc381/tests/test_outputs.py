"""Behavioral verifier for the rootless restore utility built from /app/environment."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fixture_factory import (
    APP_ROOT,
    LOG_PATH,
    MANIFESTS_DIR,
    OUTPUT_ROOT,
    make_temp_dir,
    reset_output_root,
    run_restore,
    run_restore_module,
    seed_preserve_marker,
    tree_digest,
    verify_visible_inputs_unchanged,
)
from verifier_expect import (
    ACL_XATTR,
    GID_XATTR,
    UID_XATTR,
    build_generated_archive,
    expected_log,
    filesystem_snapshot,
    load_manifest,
    normalize_rel_path,
)


def _assert_log_matches_reference(manifest_name: str) -> None:
    actual = json.loads(LOG_PATH.read_text())
    expected = expected_log(
        MANIFESTS_DIR / manifest_name,
        APP_ROOT / "archives",
        APP_ROOT / "config" / "idmap.toml",
        OUTPUT_ROOT,
    )
    assert actual == expected


def _assert_manifest_filesystem(manifest_path: Path) -> None:
    manifest = load_manifest(manifest_path)
    snap = filesystem_snapshot(OUTPUT_ROOT, manifest)
    prefix = manifest.get("restore_prefix", "")
    for item in manifest["entries"]:
        rel = normalize_rel_path(prefix, item["path"])
        state = snap["paths"][rel]
        assert state["mapped_uid"] == item["mapped_uid"]
        assert state["mapped_gid"] == item["mapped_gid"]
        if "content_sha256" in item:
            assert state["content_sha256"] == item["content_sha256"]
        if "symlink_target" in item:
            assert state["symlink_target"] == item["symlink_target"]
        for key, value in item.get("xattr", {}).items():
            assert state["xattr"][key] == value
        if item.get("acl"):
            assert state["acl"] == item["acl"]
    for group, info in snap["hardlink_groups"].items():
        assert info["shared_inode"]
        assert info["nlink"] == len(info["paths"])


def test_scenario_module_importable() -> None:
    """Installed /app/environment modules remain importable for module entrypoint checks."""
    import sys

    for path in ("/app/src", "/app"):
        if path not in sys.path:
            sys.path.insert(0, path)
    import restore.restore_main  # noqa: F401


def test_scenario_input_integrity() -> None:
    """Visible archives, manifests, and docs must remain checksum-stable."""
    verify_visible_inputs_unchanged()


def test_scenario_primary_surface() -> None:
    """Simple archives restore expected content, mapped ownership, and log report."""
    reset_output_root()
    seed_preserve_marker("simple/.operator-marker", "keep-me\n")
    run_restore(MANIFESTS_DIR / "simple-svc.json")
    _assert_manifest_filesystem(MANIFESTS_DIR / "simple-svc.json")
    assert (OUTPUT_ROOT / "simple/.operator-marker").read_text() == "keep-me\n"
    _assert_log_matches_reference("simple-svc.json")


def test_scenario_inode_identity() -> None:
    """Metadata-heavy archives preserve hardlinks, mapped root ownership, and symlinks."""
    reset_output_root()
    seed_preserve_marker("meta/.operator-marker", "stay\n")
    run_restore(MANIFESTS_DIR / "meta-svc.json")
    _assert_manifest_filesystem(MANIFESTS_DIR / "meta-svc.json")
    assert (OUTPUT_ROOT / "meta/.operator-marker").read_text() == "stay\n"
    _assert_log_matches_reference("meta-svc.json")


def test_scenario_repeat_convergence() -> None:
    """Running restore twice yields identical trees and log output."""
    reset_output_root()
    seed_preserve_marker("simple/.operator-marker", "marker\n")
    run_restore(MANIFESTS_DIR / "simple-svc.json")
    first_digest = tree_digest(OUTPUT_ROOT)
    first_log = LOG_PATH.read_text()
    _assert_log_matches_reference("simple-svc.json")
    run_restore(MANIFESTS_DIR / "simple-svc.json")
    second_digest = tree_digest(OUTPUT_ROOT)
    second_log = LOG_PATH.read_text()
    assert first_digest == second_digest
    assert first_log == second_log


def test_scenario_managed_prune() -> None:
    """Paths from a prior manifest are removed when no longer managed."""
    reset_output_root()
    simple_manifest = load_manifest(MANIFESTS_DIR / "simple-svc.json")
    run_restore(MANIFESTS_DIR / "simple-svc.json")
    stale_rel = normalize_rel_path(simple_manifest["restore_prefix"], "etc/config.json")
    stale = OUTPUT_ROOT / stale_rel
    assert stale.exists()
    run_restore(MANIFESTS_DIR / "meta-svc.json")
    assert not stale.exists()
    meta_manifest = load_manifest(MANIFESTS_DIR / "meta-svc.json")
    token_rel = normalize_rel_path(meta_manifest["restore_prefix"], "var/cache/token")
    assert (OUTPUT_ROOT / token_rel).exists()


def test_scenario_entrypoint_parity() -> None:
    """CLI wrapper and module entrypoint must produce equivalent restore output."""
    reset_output_root()
    wrapper_log = run_restore(MANIFESTS_DIR / "simple-svc.json")
    wrapper_digest = tree_digest(OUTPUT_ROOT)
    reset_output_root()
    module_log = run_restore_module(MANIFESTS_DIR / "simple-svc.json")
    module_digest = tree_digest(OUTPUT_ROOT)
    assert wrapper_log == module_log
    assert wrapper_digest == module_digest


def test_scenario_generated_variants() -> None:
    """Runtime-generated archives with renamed paths restore with correct metadata."""
    workspace = make_temp_dir("generated-restore-case-")
    archives = workspace / "archives"
    manifests = workspace / "manifests"
    archives.mkdir()
    manifests.mkdir()
    for name in ("alpha", "beta"):
        build_generated_archive(
            archives / f"{name}.tbundle",
            manifests / f"{name}.json",
            bundle_name=name,
            restore_prefix=f"gen/{name}",
        )
    reset_output_root()
    for name in ("alpha", "beta"):
        manifest_path = manifests / f"{name}.json"
        run_restore(
            manifest_path,
            archives_dir=archives,
            output_root=OUTPUT_ROOT,
        )
        _assert_manifest_filesystem(manifest_path)


def test_scenario_log_ordering() -> None:
    """Restore logs must be deterministic, sorted, and free of temporary paths."""
    reset_output_root()
    run_restore(MANIFESTS_DIR / "meta-svc.json")
    text = LOG_PATH.read_text()
    assert "/tmp/" not in text
    log = json.loads(text)
    assert log["entries_restored"] == sorted(log["entries_restored"])
    paths = [item["path"] for item in log["metadata_applied"]]
    assert paths == sorted(paths)
    for item in log["metadata_applied"]:
        assert item["xattr_keys"] == sorted(item["xattr_keys"])


def test_scenario_user_attrs() -> None:
    """Mapped ownership and ACL metadata are persisted as user xattrs on disk."""
    reset_output_root()
    run_restore(MANIFESTS_DIR / "meta-svc.json")
    manifest = load_manifest(MANIFESTS_DIR / "meta-svc.json")
    token_rel = normalize_rel_path(manifest["restore_prefix"], "var/cache/token")
    token = OUTPUT_ROOT / token_rel
    item = next(entry for entry in manifest["entries"] if entry["path"] == "var/cache/token")
    assert os.getxattr(token, UID_XATTR).decode() == str(item["mapped_uid"])
    assert os.getxattr(token, GID_XATTR).decode() == str(item["mapped_gid"])
    acl = json.loads(os.getxattr(token, ACL_XATTR).decode())
    assert acl == item["acl"]
