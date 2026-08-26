#!/usr/bin/env python3
import json
import sys
import tarfile
from pathlib import Path


def main() -> None:
    stage = Path(sys.argv[1])
    out = Path(sys.argv[2])
    manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    entries = sorted(manifest["entries"], key=lambda e: e["name"])
    manifest["entries"] = entries
    # BUG: tarball writer sorts entries but leaves bundle_digest from the unsorted builder.
    with tarfile.open(out, "w") as tar:
        data = json.dumps(manifest, indent=2).encode()
        import io

        info = tarfile.TarInfo("manifest.json")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        for ent in entries:
            name = ent["name"]
            path = stage / "units" / name
            tar.add(path, arcname=f"units/{name}")


if __name__ == "__main__":
    main()
