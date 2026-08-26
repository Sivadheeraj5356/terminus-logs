#!/usr/bin/env python3
"""Assemble the Vellum wheel.

Invoked by the release orchestrator with the resolved plan. Produces
vellum-<version>-py3-none-linux_x86_64.whl under the output directory.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--native", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--epoch", type=int, required=True)
    ap.add_argument("--features", default="")
    return ap.parse_args()


def package_native(source_root: Path, features: str) -> Path:
    """Produce the native payload for the wheel from the package-local build."""
    target = source_root / "python" / "native-target"
    feature_list = "legacy_fmt"
    if features:
        feature_list = feature_list + "," + ",".join(features.split())
    env = dict(os.environ)
    env["CARGO_TARGET_DIR"] = str(target)
    subprocess.run(
        [
            "cargo",
            "build",
            "--release",
            "-p",
            "bridge",
            "--no-default-features",
            "--features",
            feature_list,
        ],
        cwd=str(source_root),
        env=env,
        check=True,
    )
    return target / "release" / "libvellum.so"


def sha256_b64(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def main() -> int:
    args = parse_args()
    source_root = Path(args.source_root)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    native = package_native(source_root, args.features)

    stage = out_dir / "_wheel_stage"
    if stage.exists():
        shutil.rmtree(stage)
    pkg = stage / "vellum"
    pkg.mkdir(parents=True)

    src_pkg = source_root / "python" / "src" / "vellum"
    for name in ["__init__.py", "api.py", "_loader.py"]:
        shutil.copy2(src_pkg / name, pkg / name)
    shutil.copy2(native, pkg / "libvellum.so")

    dist_info = stage / f"vellum-{args.version}.dist-info"
    dist_info.mkdir()
    (dist_info / "WHEEL").write_text(
        "Wheel-Version: 1.0\n"
        "Generator: vellum-backend\n"
        "Root-Is-Purelib: false\n"
        "Tag: py3-none-linux_x86_64\n"
    )
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\n"
        f"Name: vellum\n"
        f"Version: {args.version}\n"
        f"Summary: Vellum document engine (built from {source_root})\n"
    )

    files = []
    for path in stage.rglob("*"):
        if path.is_file():
            files.append(path)

    record_lines = []
    for path in files:
        rel = path.relative_to(stage).as_posix()
        data = path.read_bytes()
        record_lines.append(f"{rel},{sha256_b64(data)},{len(data)}")
    record_path = dist_info / "RECORD"
    record_lines.append(f"vellum-{args.version}.dist-info/RECORD,,")
    record_path.write_text("\n".join(record_lines) + "\n")
    files.append(record_path)

    wheel_name = f"vellum-{args.version}-py3-none-linux_x86_64.whl"
    wheel_path = out_dir / wheel_name
    if wheel_path.exists():
        wheel_path.unlink()

    now = time.localtime(time.time())
    date_time = (now.tm_year, now.tm_mon, now.tm_mday, now.tm_hour, now.tm_min, now.tm_sec)
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            rel = path.relative_to(stage).as_posix()
            info = zipfile.ZipInfo(rel, date_time=date_time)
            info.external_attr = (0o644 & 0xFFFF) << 16
            zf.writestr(info, path.read_bytes())

    shutil.rmtree(stage)
    print(str(wheel_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
