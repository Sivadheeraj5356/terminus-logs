"""Incremental thin link driver with summary-guided relink."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from auxiliary import epoch_courier, relink_order, replay_ledger
from auxiliary.drift_scan import modules_with_abi_drift
from lto.graph_digest import import_hash
from lto.module_index import GEN_SENSITIVE, all_modules, source_name
from lto.sidecar_store import persist_sidecar
from lto.summary_read import read_summary


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def _compile_objects(src_root: Path, gen_root: Path, obj_root: Path, modules: list[str]) -> None:
    obj_root.mkdir(parents=True, exist_ok=True)
    includes = ["-I", str(src_root), "-I", str(gen_root)]
    flags = ["-O2", "-flto=thin", "-fPIC", "-std=c++17", *includes]
    for module in relink_order.schedule(modules):
        if module == "gate_abi":
            src = gen_root / "gate_abi.cpp"
        else:
            src = src_root / source_name(module)
        out = obj_root / f"{module}.o"
        _run(["clang++", *flags, "-c", str(src), "-o", str(out)])


def _emit_binary(obj_root: Path, bin_root: Path, modules: list[str]) -> Path:
    bin_root.mkdir(parents=True, exist_ok=True)
    out = bin_root / "matrix_app"
    objs = [str(obj_root / f"{m}.o") for m in modules]
    _run(["clang++", "-flto=thin", "-fuse-ld=lld", "-Wl,-export-dynamic", "-o", str(out), *objs])
    return out


def _needs_relink(module: str, src_root: Path, work_root: Path, lto_root: Path) -> bool:
    summary_path = lto_root / f"{module}.summary.json"
    if not summary_path.is_file():
        return True
    summary = read_summary(summary_path)
    src_path = src_root / source_name(module)
    if module == "gate_abi":
        src_path = work_root / "gen" / "gate_abi.cpp"
    current_mtime = src_path.stat().st_mtime if src_path.is_file() else 0.0
    recorded = float(summary.get("source_mtime", 0.0))
    return current_mtime > recorded


def build(mode: str, profile: str) -> dict[str, object]:
    src_root = Path("/app/environment/src")
    work_root = Path("/app/work")
    gen_root = work_root / "gen"
    obj_root = work_root / "obj"
    lto_root = work_root / "lto"
    bin_root = work_root / "bin"
    modules = all_modules()

    _run(["python3", "/app/environment/gen/emit_gate.py", "--out", str(gen_root)])

    relinked: list[str] = []
    if mode == "full":
        shutil.rmtree(obj_root, ignore_errors=True)
        shutil.rmtree(lto_root, ignore_errors=True)
        generation = epoch_courier.begin_full_build(lto_root)
        _compile_objects(src_root, gen_root, obj_root, modules)
        for module in modules:
            epoch = generation if module in GEN_SENSITIVE else 0
            persist_sidecar(module, src_root, work_root, obj_root, lto_root, link_epoch=epoch)
        relinked = list(modules)
    else:
        replay_ledger.align_journal_from_checkpoint(work_root, lto_root)
        content: list[str] = []
        for module in modules:
            if _needs_relink(module, src_root, work_root, lto_root):
                content.append(module)
        for module in modules_with_abi_drift(lto_root, work_root):
            if module not in content:
                content.append(module)

        lagging = epoch_courier.modules_behind_journal(lto_root)
        relinked = list(content)
        for module in lagging:
            if module not in relinked:
                relinked.append(module)

        generation = epoch_courier.read_journal(lto_root)
        if any(module in GEN_SENSITIVE for module in content):
            generation = epoch_courier.bump_if_relinking(lto_root, True)
            for module in GEN_SENSITIVE:
                summary_path = lto_root / f"{module}.summary.json"
                if not summary_path.is_file():
                    if module not in relinked:
                        relinked.append(module)
                    continue
                summary = read_summary(summary_path)
                if int(summary.get("link_epoch", 0)) != generation and module not in relinked:
                    relinked.append(module)
        elif lagging:
            generation = epoch_courier.read_journal(lto_root)

        if relinked:
            _compile_objects(src_root, gen_root, obj_root, relinked)
            for module in relinked:
                epoch = generation if module in GEN_SENSITIVE else 0
                persist_sidecar(module, src_root, work_root, obj_root, lto_root, link_epoch=epoch)

    binary = _emit_binary(obj_root, bin_root, modules)
    summary_hash = {m: import_hash(m, src_root, work_root) for m in modules}
    return {
        "profile": profile,
        "mode": mode,
        "relinked_modules": relinked,
        "summary_hash": summary_hash,
        "binary": str(binary),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "incremental"], default="full")
    parser.add_argument("--profile", default="release")
    parser.add_argument("--report", default="")
    args = parser.parse_args()
    result = build(args.mode, args.profile)
    if args.report:
        Path(args.report).write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
