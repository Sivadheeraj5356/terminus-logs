"""Verifier-owned fixture helpers for the rootless restore utility."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

APP_ROOT = Path("/app")
TEST_ROOT = Path(__file__).resolve().parent
ASSETS = TEST_ROOT / "assets"
INPUT_MANIFEST = ASSETS / "input-manifest.json"
CLI = APP_ROOT / "bin" / "restore-bundle"
ARCHIVES_DIR = APP_ROOT / "archives"
MANIFESTS_DIR = APP_ROOT / "manifests"
IDMAP = APP_ROOT / "config" / "idmap.toml"
OUTPUT_ROOT = Path("/output/restore-root")
LOG_PATH = Path("/output/restore-log.json")


def make_temp_dir(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(dir="/tmp", prefix=prefix))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_input_manifest() -> dict[str, str]:
    return json.loads(INPUT_MANIFEST.read_text())


def verify_visible_inputs_unchanged() -> None:
    manifest = load_input_manifest()
    mismatches: list[str] = []
    for rel, expected in manifest.items():
        path = APP_ROOT / rel
        if not path.is_file():
            raise AssertionError(f"missing visible file: {rel}")
        if sha256_file(path) != expected:
            mismatches.append(rel)
    assert len(mismatches) == 0, f"modified visible files: {sorted(mismatches)}"


def run_restore(
    manifest: Path,
    *,
    output_root: Path = OUTPUT_ROOT,
    log_path: Path = LOG_PATH,
    archives_dir: Path = ARCHIVES_DIR,
) -> dict[str, Any]:
    output_root.parent.mkdir(parents=True, exist_ok=True)
    if log_path.exists():
        log_path.unlink()
    env = os.environ.copy()
    env["PYTHONPATH"] = "/app/src:/app"
    subprocess.run(
        [
            str(CLI),
            "--archives-dir",
            str(archives_dir),
            "--manifest",
            str(manifest),
            "--output",
            str(output_root),
            "--idmap",
            str(IDMAP),
            "--log",
            str(log_path),
        ],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    return json.loads(log_path.read_text())


def run_restore_module(
    manifest: Path,
    *,
    output_root: Path = OUTPUT_ROOT,
    log_path: Path = LOG_PATH,
) -> dict[str, Any]:
    output_root.parent.mkdir(parents=True, exist_ok=True)
    if log_path.exists():
        log_path.unlink()
    env = os.environ.copy()
    env["PYTHONPATH"] = "/app/src:/app"
    subprocess.run(
        [
            "python3",
            "-m",
            "restore.restore_main",
            "--archives-dir",
            str(ARCHIVES_DIR),
            "--manifest",
            str(manifest),
            "--output",
            str(output_root),
            "--idmap",
            str(IDMAP),
            "--log",
            str(log_path),
        ],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    return json.loads(log_path.read_text())


def reset_output_root() -> None:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def seed_preserve_marker(relative: str, content: str = "operator\n") -> Path:
    path = OUTPUT_ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def tree_digest(root: Path) -> str:
  entries: list[str] = []
  for path in sorted(root.rglob("*")):
      rel = path.relative_to(root).as_posix()
      if path.is_symlink():
          entries.append(f"link:{rel}:{os.readlink(path)}")
      elif path.is_file():
          entries.append(f"file:{rel}:{sha256_file(path)}:{path.stat().st_mode}:{path.stat().st_nlink}")
          try:
              xattrs = sorted(
                  (
                      (key.decode() if isinstance(key, bytes) else key),
                      (
                          os.getxattr(path, key).decode()
                          if isinstance(os.getxattr(path, key), bytes)
                          else os.getxattr(path, key)
                      ),
                  )
                  for key in os.listxattr(path)
              )
          except OSError:
              xattrs = []
          for key, value in xattrs:
              entries.append(f"xattr:{rel}:{key}:{value}")
      elif path.is_dir():
          entries.append(f"dir:{rel}:{path.stat().st_mode}")
  return hashlib.sha256("\n".join(entries).encode()).hexdigest()
