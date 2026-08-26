#!/usr/bin/env python3
"""Incomplete on-host Blender profile reconciliation controller."""

import argparse
import hashlib
import json
import re
import stat
import sys
from pathlib import Path


LAYOUT = ["bin", "cache", "config", "logs", "scripts", "scripts/addons", "startup"]
PROFILE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class ProfileError(Exception):
    pass


def load_manifest(path):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProfileError(f"cannot read manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProfileError("manifest must be an object")
    for field in ("blender_version", "python_expr"):
        if not isinstance(payload.get(field), str):
            raise ProfileError(f"bad manifest field {field}")
    if not isinstance(payload.get("env"), dict) or not isinstance(payload.get("profile_settings"), dict):
        raise ProfileError("bad manifest mappings")
    return payload


def profile_paths(root, profile):
    base = Path(root).resolve() / profile
    return base, base / "bin" / f"blender-{profile}", base / "startup" / "bootstrap.py"


def legacy_manifest_hash(manifest):
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_wrapper(path, base):
    lines = [
        "#!/bin/sh",
        f"export BLENDER_USER_CONFIG={base / 'config'}",
        f"export BLENDER_USER_SCRIPTS={base / 'scripts'}",
        f"export BLENDER_USER_DATA={base}",
        'exec blender "$@"',
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def write_bootstrap(path, profile, manifest, digest):
    path.write_text(
        f'PROFILE_NAME = "{profile}"\n'
        f'BLENDER_VERSION = "{manifest["blender_version"]}"\n'
        f"PYTHON_EXPR = {manifest['python_expr']!r}\n"
        f"PROFILE_ENV = {manifest['env']!r}\n"
        f"PROFILE_SETTINGS = {manifest['profile_settings']!r}\n"
        f'MANIFEST_SHA256 = "{digest}"\n',
        encoding="utf-8",
    )


def report_payload(root, profile, manifest, digest):
    base, wrapper, bootstrap = profile_paths(root, profile)
    return {
        "generated_by": "blendprofile",
        "profile": profile,
        "profile_root": str(base),
        "directories": [str(base / rel) for rel in LAYOUT],
        "wrapper_path": str(wrapper),
        "bootstrap_path": str(bootstrap),
        "blender_version": manifest["blender_version"],
        "manifest_sha256": digest,
        "dry_run": False,
    }


def create(args):
    if not PROFILE_RE.fullmatch(args.profile):
        raise ProfileError("invalid profile")
    manifest = load_manifest(args.manifest)
    digest = legacy_manifest_hash(manifest)
    base, wrapper, bootstrap = profile_paths(args.root, args.profile)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report_payload(args.root, args.profile, manifest, digest), indent=2), encoding="utf-8")
    for rel in LAYOUT:
        (base / rel).mkdir(parents=True, exist_ok=True)
    write_wrapper(wrapper, base)
    write_bootstrap(bootstrap, args.profile, manifest, digest)
    return 0


def parser():
    root = argparse.ArgumentParser(prog="blendprofile")
    sub = root.add_subparsers(dest="command", required=True)
    command = sub.add_parser("create")
    command.add_argument("--manifest", required=True)
    command.add_argument("--root", required=True)
    command.add_argument("--profile", required=True)
    command.add_argument("--out", required=True)
    return root


def main():
    try:
        args = parser().parse_args()
        return create(args)
    except ProfileError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
