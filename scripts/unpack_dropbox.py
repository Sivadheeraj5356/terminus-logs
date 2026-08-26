"""Inventory and extract the latest revision of each Dropbox submission zip."""

from __future__ import annotations

import json
import re
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTER = ROOT / "terminal-bench-tasks.zip"
OUT = ROOT / "dropbox-tasks"
SUB_RE = re.compile(
    r"(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"_submission_(?P<ts>.+)\.zip$",
    re.I,
)


def parse_ts(raw: str) -> datetime:
    raw = raw.split(" (")[0].replace("Z", "+00:00")
    if "T" in raw:
        date, time = raw.split("T", 1)
        time = time.replace("_", ":", 2)
        raw = f"{date}T{time}"
    return datetime.fromisoformat(raw)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[tuple[datetime, str, int]]] = defaultdict(list)
    other = []
    with zipfile.ZipFile(OUTER) as zf:
        for info in zf.infolist():
            name = info.filename.lstrip("/")
            if not name or name.endswith("/"):
                continue
            m = SUB_RE.search(Path(name).name)
            if m:
                groups[m.group("uuid")].append((parse_ts(m.group("ts")), name, info.file_size))
            else:
                other.append((name, info.file_size))

        latest = []
        for uuid, items in groups.items():
            items.sort(key=lambda x: x[0])
            latest.append(
                {
                    "uuid": uuid,
                    "revisions": len(items),
                    "latest_ts": items[-1][0].isoformat(),
                    "latest_name": items[-1][1],
                    "latest_size": items[-1][2],
                }
            )
        latest.sort(key=lambda r: r["latest_ts"], reverse=True)

        print(f"submission zips: {sum(len(v) for v in groups.values())}")
        print(f"unique tasks: {len(groups)}")
        print(f"other files: {len(other)}")
        for name, size in other[:20]:
            print(f"  other {size:10d}  {name}")

        # Peek 3 latest inner zips
        samples = []
        for row in latest[:3]:
            with zf.open(row["latest_name"]) as fh:
                with zipfile.ZipFile(fh) as inner:
                    names = inner.namelist()[:40]
            samples.append({"uuid": row["uuid"], "inner_sample": names, "n_inner": None})
            with zf.open(row["latest_name"]) as fh:
                with zipfile.ZipFile(fh) as inner:
                    samples[-1]["n_inner"] = len(inner.namelist())
                    samples[-1]["has_instruction"] = any(
                        n.endswith("instruction.md") for n in inner.namelist()
                    )
                    samples[-1]["has_task_toml"] = any(n.endswith("task.toml") for n in inner.namelist())
                    samples[-1]["has_result_json"] = any(n.endswith("result.json") for n in inner.namelist())
                    samples[-1]["has_reward"] = any(n.endswith("reward.txt") for n in inner.namelist())

        (OUT / "_inventory_preview.json").write_text(
            json.dumps({"unique": len(groups), "samples": samples, "latest": latest[:10]}, indent=2),
            encoding="utf-8",
        )
        print("sample inner layouts:")
        for s in samples:
            print(json.dumps({k: s[k] for k in s if k != "inner_sample"}, indent=2))
            print("  files:", s["inner_sample"][:25])

        # Extract latest revision of each UUID
        dest_root = OUT / "latest"
        dest_root.mkdir(exist_ok=True)
        extracted = 0
        for row in latest:
            dest = dest_root / row["uuid"]
            marker = dest / ".extracted"
            if marker.exists():
                extracted += 1
                continue
            dest.mkdir(exist_ok=True)
            with zf.open(row["latest_name"]) as fh:
                with zipfile.ZipFile(fh) as inner:
                    inner.extractall(dest)
            marker.write_text(row["latest_name"], encoding="utf-8")
            extracted += 1
            if extracted % 25 == 0:
                print(f"extracted {extracted}/{len(latest)}")
        print(f"extracted latest revisions: {extracted}")
        (OUT / "_latest_index.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
