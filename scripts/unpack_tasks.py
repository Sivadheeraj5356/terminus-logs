"""Inventory and extract the latest revision of each submission zip."""

from __future__ import annotations

import json
import re
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTER = ROOT / "terminal-bench-tasks.zip"
OUT = ROOT / "tasks"
DEST_ROOT = OUT / "latest"
CATALOG_DIR = ROOT / "catalog"
JSONL = CATALOG_DIR / "tasks.jsonl"
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


def load_sid_to_slug() -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not JSONL.exists():
        return mapping
    for line in JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        sid = str(rec.get("sid") or rec.get("uuid") or "").lower()
        slug = str(rec.get("id") or "").strip()
        if sid and slug:
            mapping[sid] = slug
    return mapping


def main() -> None:
    DEST_ROOT.mkdir(parents=True, exist_ok=True)
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    sid_to_slug = load_sid_to_slug()
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
                    "slug": sid_to_slug.get(uuid.lower(), uuid),
                }
            )
        latest.sort(key=lambda r: r["latest_ts"], reverse=True)

        print(f"submission zips: {sum(len(v) for v in groups.values())}")
        print(f"unique tasks: {len(groups)}")
        print(f"catalog slugs: {len(sid_to_slug)}")
        print(f"other files: {len(other)}")
        for name, size in other[:20]:
            print(f"  other {size:10d}  {name}")

        samples = []
        for row in latest[:3]:
            with zf.open(row["latest_name"]) as fh:
                with zipfile.ZipFile(fh) as inner:
                    names = inner.namelist()[:40]
            samples.append({"uuid": row["uuid"], "slug": row["slug"], "inner_sample": names, "n_inner": None})
            with zf.open(row["latest_name"]) as fh:
                with zipfile.ZipFile(fh) as inner:
                    samples[-1]["n_inner"] = len(inner.namelist())
                    samples[-1]["has_instruction"] = any(
                        n.endswith("instruction.md") for n in inner.namelist()
                    )
                    samples[-1]["has_task_toml"] = any(n.endswith("task.toml") for n in inner.namelist())
                    samples[-1]["has_result_json"] = any(n.endswith("result.json") for n in inner.namelist())
                    samples[-1]["has_reward"] = any(n.endswith("reward.txt") for n in inner.namelist())

        (CATALOG_DIR / "_inventory_preview.json").write_text(
            json.dumps({"unique": len(groups), "samples": samples, "latest": latest[:10]}, indent=2),
            encoding="utf-8",
        )
        print("sample inner layouts:")
        for s in samples:
            print(json.dumps({k: s[k] for k in s if k != "inner_sample"}, indent=2))
            print("  files:", s["inner_sample"][:25])

        extracted = 0
        for row in latest:
            dest = DEST_ROOT / row["slug"]
            marker = dest / ".extracted_from"
            if not marker.exists():
                alt = dest / ".extracted"
                if alt.exists():
                    marker = alt
            if marker.exists():
                extracted += 1
                continue
            dest.mkdir(exist_ok=True)
            with zf.open(row["latest_name"]) as fh:
                with zipfile.ZipFile(fh) as inner:
                    inner.extractall(dest)
            (dest / ".extracted_from").write_text(row["latest_name"], encoding="utf-8")
            extracted += 1
            if extracted % 25 == 0:
                print(f"extracted {extracted}/{len(latest)}")
        print(f"extracted latest revisions: {extracted}")
        (CATALOG_DIR / "_latest_index.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
