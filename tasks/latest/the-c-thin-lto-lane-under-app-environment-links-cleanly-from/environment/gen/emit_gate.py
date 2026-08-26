#!/usr/bin/env python3
"""Emit generated gate header and ABI stamp from profile + template."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _render(template: str, abi_tag: str, seed: int) -> str:
    return template.replace("@@ABI_TAG@@", abi_tag).replace("@@SEED@@", str(seed))


def emit(profile_path: Path, template_path: Path, out_dir: Path) -> dict[str, str]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    template = template_path.read_text(encoding="utf-8")
    abi_tag = str(profile["abi_tag"])
    seed = int(profile["dispatch_seed"])
    header = _render(template, abi_tag, seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    header_path = out_dir / "gate_abi.h"
    impl = (
        '#include "gate_abi.h"\n'
        '__attribute__((visibility("default")))\n'
        "extern \"C\" const char *gate_abi_tag(void) { return ABI_TAG_VALUE; }\n"
    )
    impl_path = out_dir / "gate_abi.cpp"
    stamp = hashlib.sha256(f"{abi_tag}:{seed}".encode()).hexdigest()[:16]
    stamp_path = out_dir / "abi_stamp.txt"
    stamp_body = f"{stamp}\n"
    if (
        header_path.is_file()
        and header_path.read_text(encoding="utf-8") == header
        and impl_path.is_file()
        and impl_path.read_text(encoding="utf-8") == impl
        and stamp_path.is_file()
        and stamp_path.read_text(encoding="utf-8") == stamp_body
    ):
        return {"abi_tag": abi_tag, "stamp": stamp, "seed": str(seed)}
    header_path.write_text(header, encoding="utf-8")
    impl_path.write_text(impl, encoding="utf-8")
    stamp_path.write_text(stamp_body, encoding="utf-8")
    return {"abi_tag": abi_tag, "stamp": stamp, "seed": str(seed)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="/app/environment/gen/abi_profile.json")
    parser.add_argument("--template", default="/app/environment/gen/templates/gate_abi.h.tpl")
    parser.add_argument("--out", default="/app/work/gen")
    args = parser.parse_args()
    emit(Path(args.profile), Path(args.template), Path(args.out))


if __name__ == "__main__":
    main()
