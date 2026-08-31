"""Select the Applied Work lab MVP (100 unique Harbor packages) and build lab/corpus.json.

Default: read docs/lab_mvp_100.jsonl and write lab/corpus.json (+ lab/corpus.js).
--select: rebuild the 100-list from catalog/tasks.jsonl, then write the corpus.

Quotas follow Hamilton (largest remainder) on the full 448-row catalog so the mix
stays proportional to the inventory. Near-duplicate resolver twins: keep the
feature-bundle task in the pool, drop the render-pipeline twin. Prefer author-
labeled hard tasks that still have oracle + tests (all 448 do).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "tasks.jsonl"
JSONL = ROOT / "docs" / "lab_mvp_100.jsonl"
BATCH_JSONL = ROOT / "docs" / "lab_batch_01.jsonl"
CORPUS_JSON = ROOT / "lab" / "corpus.json"
CORPUS_JS = ROOT / "lab" / "corpus.js"
TASKS_LATEST = ROOT / "tasks" / "latest"

MVP_SIZE = 100
INVENTORY_SIZE = 448

# Proportional mix is computed from this order (same as catalog/index.md).
CATEGORY_ORDER = [
    "scientific-computing",
    "security",
    "system-administration",
    "build-and-dependency-management",
    "data-processing",
    "machine-learning",
    "games",
    "debugging",
]

# Jaccard ≥ 0.72 instruction pair from docs/Caudal_Lab_Reference_and_Similarity.md.
# Keep one world; drop the twin so the lab does not ship near-duplicates.
DROP_NEAR_DUPLICATE_SLUGS = {
    "the-tool-in-app-is-a-render-pipeline-plugin-resolver-given-a",
}
KEEP_NEAR_DUPLICATE_SLUG = "the-tool-in-app-is-a-feature-bundle-resolver-given-a-bundle"

HEADING_RE = re.compile(r"^#+\s+(.*)$", re.M)
LANG_ALIASES = {
    "c": "C",
    "c++": "C++",
    "cpp": "C++",
    "csharp": "C#",
    "c#": "C#",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "py": "Python",
    "python": "Python",
    "golang": "Go",
    "go": "Go",
    "rs": "Rust",
    "rust": "Rust",
    "rb": "Ruby",
    "ruby": "Ruby",
    "sh": "Bash",
    "shell": "Bash",
    "bash": "Bash",
    "jl": "Julia",
    "julia": "Julia",
    "kt": "Kotlin",
    "kotlin": "Kotlin",
    "java": "Java",
    "r": "R",
    "sql": "SQL",
    "php": "PHP",
    "lua": "Lua",
    "haskell": "Haskell",
    "awk": "Awk",
    "yaml": "YAML",
    "toml": "TOML",
    "json": "JSON",
}


def normalize_language(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return raw
    aliased = LANG_ALIASES.get(raw.lower())
    if aliased:
        return aliased
    return raw
POINTER_FILES = (
    ("instruction.md", "instruction.md", False),
    ("task.toml", "task.toml", False),
    ("environment/", "environment", True),
    ("solution/", "solution", True),
    ("tests/", "tests", True),
    ("summary.md", "summary.md", False),
)


def load_catalog() -> list[dict]:
    rows = []
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def hamilton_quotas(counts: dict[str, int], seats: int) -> dict[str, int]:
    n = sum(counts.get(cat, 0) for cat in CATEGORY_ORDER)
    if n == 0:
        raise SystemExit("catalog has no category counts")
    floors: dict[str, int] = {}
    remainders: list[tuple[int, str]] = []
    used = 0
    for cat in CATEGORY_ORDER:
        num = counts.get(cat, 0) * seats
        floor = num // n
        floors[cat] = floor
        used += floor
        remainders.append((num % n, cat))
    leftover = seats - used
    remainders.sort(key=lambda item: (-item[0], CATEGORY_ORDER.index(item[1])))
    for i in range(leftover):
        floors[remainders[i][1]] += 1
    if sum(floors.values()) != seats:
        raise SystemExit(f"quota arithmetic failed: {floors}")
    return floors


def selection_score(row: dict) -> tuple:
    difficulty = (row.get("difficulty") or "unknown").lower()
    diff = {"hard": 300, "medium": 80}.get(difficulty, 0)
    quality = row.get("quality") or {}
    spec = 40 if quality.get("well_specified") else 0
    versions = min(int(row.get("n_versions") or 1), 12) * 3
    expert = min(float(row.get("expert_time_estimate_min") or 0), 400) * 0.15
    logs = 15 if row.get("has_logs") else 0
    summary_len = min(len(row.get("instruction_summary") or ""), 800) * 0.02
    score = diff + spec + versions + expert + logs + summary_len
    # Stable tie-break: higher score first, then more revisions, then slug.
    return (-score, -(row.get("n_versions") or 0), row.get("id") or "")


def is_standard_package(pkg: Path) -> bool:
    return (
        (pkg / "instruction.md").is_file()
        and (pkg / "task.toml").is_file()
        and (pkg / "environment").is_dir()
        and (pkg / "solution").is_dir()
        and (pkg / "tests").is_dir()
    )


def tidy_title(text: str, limit: int = 88) -> str:
    name = (text or "").strip().lstrip("#").strip().strip("`")
    name = name.replace("\ufffd", "–")
    name = re.sub(r"\s+", " ", name)
    if not name:
        return ""
    if len(name) <= limit:
        return name.rstrip(" ,;:-")
    cut = name[: limit + 1]
    space = cut.rfind(" ")
    return (cut[:space] if space > 24 else cut[:limit]).rstrip(" ,;:-") + "…"


def display_name(slug: str, catalog_title: str, summary_text: str, instruction_text: str) -> str:
    for source in (instruction_text, summary_text):
        if not source:
            continue
        match = HEADING_RE.search(source)
        if match:
            name = tidy_title(match.group(1), 80)
            if name and name.lower() not in {"summary", "harbor package"}:
                return name
    title = tidy_title(catalog_title, 88)
    if title:
        return title
    if instruction_text:
        first = excerpt(instruction_text, 88).rstrip("…")
        if first:
            return tidy_title(first, 88)
    return slug.replace("-", " ")


def excerpt(text: str, limit: int = 640) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if collapsed.startswith("#"):
        collapsed = collapsed.split(" ", 1)[-1] if " " in collapsed else collapsed
    if len(collapsed) <= limit:
        return collapsed
    cut = collapsed[: limit + 1]
    space = cut.rfind(" ")
    return (cut[:space] if space > 80 else cut[:limit]).rstrip(" ,;:") + "…"


def package_pointers(slug: str) -> list[dict]:
    pkg = TASKS_LATEST / slug
    pointers = []
    for label, rel, is_dir in POINTER_FILES:
        path = pkg / rel
        exists = path.is_dir() if is_dir else path.is_file()
        pointers.append(
            {
                "label": label,
                "path": f"tasks/latest/{slug}/{label}",
                "href": f"../tasks/latest/{slug}/{label}",
                "exists": exists,
            }
        )
    return pointers


def select_mvp(rows: list[dict]) -> tuple[list[dict], dict]:
    by_uuid = {}
    by_slug = {}
    inventory_counts = Counter(r.get("category") or "unknown" for r in rows)
    quotas = hamilton_quotas(inventory_counts, MVP_SIZE)

    eligible = []
    dropped = []
    for row in rows:
        slug = row.get("id") or ""
        uuid = row.get("uuid") or row.get("sid") or ""
        if not slug or not uuid:
            continue
        if slug in by_slug or uuid in by_uuid:
            raise SystemExit(f"catalog uniqueness failed: {slug} / {uuid}")
        by_slug[slug] = row
        by_uuid[uuid] = row
        if slug in DROP_NEAR_DUPLICATE_SLUGS:
            dropped.append(
                {
                    "slug": slug,
                    "uuid": uuid,
                    "reason": (
                        "near-duplicate of "
                        f"{KEEP_NEAR_DUPLICATE_SLUG} (instruction Jaccard ≥ 0.72); kept one"
                    ),
                }
            )
            continue
        if not row.get("has_oracle") or not row.get("has_tests"):
            continue
        pkg = ROOT / (row.get("package_dir") or f"tasks/latest/{slug}")
        if not is_standard_package(pkg):
            continue
        eligible.append(row)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in eligible:
        grouped[row.get("category") or "unknown"].append(row)
    for cat in grouped:
        grouped[cat].sort(key=selection_score)

    chosen: list[dict] = []
    leftovers: list[dict] = []
    for cat in CATEGORY_ORDER:
        quota = quotas.get(cat, 0)
        pool = grouped.get(cat, [])
        take = pool[:quota]
        leftovers.extend(pool[quota:])
        if len(take) < quota:
            # Should not happen at these sizes; backfill later from leftovers.
            pass
        chosen.extend(take)

    if len(chosen) < MVP_SIZE:
        leftovers.sort(key=selection_score)
        need = MVP_SIZE - len(chosen)
        chosen.extend(leftovers[:need])

    if len(chosen) != MVP_SIZE:
        raise SystemExit(f"expected {MVP_SIZE} tasks, selected {len(chosen)}")

    slugs = [r["id"] for r in chosen]
    uuids = [r.get("uuid") or r["sid"] for r in chosen]
    if len(set(slugs)) != MVP_SIZE or len(set(uuids)) != MVP_SIZE:
        raise SystemExit("selected set is not unique on slug or uuid")

    meta = {
        "inventory_size": len(rows),
        "inventory_category_counts": dict(inventory_counts),
        "quotas": quotas,
        "selected_category_counts": dict(Counter(r.get("category") for r in chosen)),
        "dropped_near_duplicates": dropped,
        "difficulty_counts": dict(Counter((r.get("difficulty") or "unknown") for r in chosen)),
    }
    return chosen, meta


def row_to_jsonl(row: dict, rank: int, score: float) -> dict:
    slug = row["id"]
    uuid = row.get("uuid") or row["sid"]
    return {
        "slug": slug,
        "uuid": uuid,
        "category": row.get("category"),
        "difficulty": row.get("difficulty"),
        "subcategories": row.get("subcategories") or [],
        "languages": row.get("languages") or [],
        "title": row.get("title"),
        "package_dir": row.get("package_dir") or f"tasks/latest/{slug}",
        "has_oracle": bool(row.get("has_oracle")),
        "has_tests": bool(row.get("has_tests")),
        "n_versions": row.get("n_versions"),
        "selection_rank": rank,
        "selection_score": round(score, 3),
        "selection_reason": "hard-prefer + Hamilton category quota + unique uuid/slug",
    }


def write_jsonl(chosen: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(
        chosen,
        key=lambda r: (CATEGORY_ORDER.index(r.get("category") or "debugging"), r["id"]),
    )
    lines = []
    for i, row in enumerate(ordered, start=1):
        score = -selection_score(row)[0]
        lines.append(json.dumps(row_to_jsonl(row, i, score), ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def build_corpus_task(catalog_row: dict) -> dict:
    slug = catalog_row["id"]
    uuid = catalog_row.get("uuid") or catalog_row["sid"]
    pkg = ROOT / (catalog_row.get("package_dir") or f"tasks/latest/{slug}")
    summary_text = ""
    instruction_text = ""
    summary_path = pkg / "summary.md"
    instruction_path = pkg / "instruction.md"
    if summary_path.is_file():
        summary_text = summary_path.read_text(encoding="utf-8", errors="replace")
    if instruction_path.is_file():
        instruction_text = instruction_path.read_text(encoding="utf-8", errors="replace")
    name = display_name(
        slug,
        catalog_row.get("title") or "",
        summary_text,
        instruction_text,
    )
    summary = catalog_row.get("instruction_summary") or excerpt(summary_text or instruction_text)
    languages = catalog_row.get("languages") or []
    if isinstance(languages, str):
        languages = [languages]
    languages = [normalize_language(lang) for lang in languages]
    subcategories = catalog_row.get("subcategories") or []
    if isinstance(subcategories, str):
        subcategories = [subcategories]
    subcategories = [str(s).strip() for s in subcategories if str(s).strip()]
    return {
        "slug": slug,
        "uuid": uuid,
        "name": name,
        "title": catalog_row.get("title") or name,
        "category": catalog_row.get("category"),
        "difficulty": catalog_row.get("difficulty") or "unknown",
        "subcategories": subcategories,
        "languages": languages,
        "summary": summary,
        "instruction_excerpt": excerpt(instruction_text) if instruction_text else excerpt(summary),
        "instruction_chars": len(instruction_text),
        "instruction_lines": (
            instruction_text.count("\n") + (1 if instruction_text else 0)
        ),
        "package_dir": catalog_row.get("package_dir") or f"tasks/latest/{slug}",
        "has_oracle": bool(catalog_row.get("has_oracle")),
        "has_tests": bool(catalog_row.get("has_tests")),
        "rollouts": {
            "status": "not_run",
            "label": "not run",
            "trials": [],
            "note": "No private Harbor agent trials are recorded for this package.",
        },
        "stump_pct": None,
        "batch": None,
        "measured": False,
        "files": package_pointers(slug),
    }


def attach_batch_placeholder(corpus: dict) -> dict:
    """Mark frozen-batch membership without inventing scores."""
    from lab_common import PLANNED_ATTEMPTS, coverage_matrix, load_all_batches

    batch_rows = load_all_batches()
    slug_to_batch = {row["slug"]: int(row.get("batch") or 0) or None for row in batch_rows}
    batch_slugs = {slug for slug, n in slug_to_batch.items() if n}
    by_batch: dict[int, list[str]] = {}
    for row in batch_rows:
        n = int(row.get("batch") or 0)
        if n:
            by_batch.setdefault(n, []).append(row["slug"])
    measured_slugs = {
        t["slug"] for t in corpus["tasks"] if (t.get("rollouts") or {}).get("status") == "measured"
    }
    for task in corpus["tasks"]:
        task["batch"] = slug_to_batch.get(task["slug"])
        if task["slug"] not in measured_slugs:
            task["measured"] = False
    lab = corpus["lab"]
    lab["batch_01_size"] = len(by_batch.get(1) or [])
    lab["batch_01_slugs"] = by_batch.get(1) or []
    lab["batches"] = {
        str(n): {"size": len(slugs), "slugs": slugs}
        for n, slugs in sorted(by_batch.items())
    }
    lab["measured_size"] = len(measured_slugs)
    lab["measured_target"] = 50
    lab["measured_slugs"] = sorted(measured_slugs)
    lab["coverage"] = coverage_matrix(corpus["tasks"], batch_slugs, measured_slugs)
    lab["harness"] = {
        "agent": "terminus-2",
        "oracle": "oracle",
        "empty": "nop",
        "harbor": "0.22",
        "planned_attempts": PLANNED_ATTEMPTS,
        "n_trials": "n_attempts × n_tasks × n_agents; CLI -k is n_attempts (independent trials)",
        "estimated_not_measured": ["claude-code", "codex", "mini-swe-agent"],
    }
    return corpus


def _instruction_preview_lines(text: str, max_lines: int = 12) -> list[dict]:
    lines = text.splitlines() or [""]
    return [{"n": i, "text": line[:220]} for i, line in enumerate(lines[:max_lines], start=1)]


def enrich_overview_stats(corpus: dict) -> dict:
    """Attach instruction-length / language charts from our packages only.

    Never invent scores. Lengths come from tasks/latest/<slug>/instruction.md
    for the 100 gallery rows already in the corpus.
    """
    lengths: list[int] = []
    lang_counts: Counter = Counter()
    previews: list[dict] = []
    for task in corpus["tasks"]:
        slug = task["slug"]
        path = TASKS_LATEST / slug / "instruction.md"
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        nchars = len(text)
        nlines = text.count("\n") + (1 if text else 0)
        task["instruction_chars"] = nchars
        task["instruction_lines"] = nlines
        lengths.append(nchars)
        langs = task.get("languages") or []
        lang_counts[langs[0] if langs else "—"] += 1
        if task.get("batch") and len(previews) < 3:
            previews.append(
                {
                    "slug": slug,
                    "name": task.get("name") or slug,
                    "chars": nchars,
                    "lines": _instruction_preview_lines(text),
                }
            )
    lengths.sort()

    def percentile(p: float) -> int:
        if not lengths:
            return 0
        idx = min(len(lengths) - 1, max(0, int(round((p / 100) * (len(lengths) - 1)))))
        return lengths[idx]

    bins = [(0, 1000), (1000, 2000), (2000, 3000), (3000, 5000), (5000, 10000), (10000, 10**9)]
    histogram = []
    for lo, hi in bins:
        histogram.append(
            {
                "lo": lo,
                "hi": None if hi >= 10**8 else hi,
                "n": sum(1 for value in lengths if lo <= value < hi),
            }
        )
    ecdf = []
    if lengths:
        step = max(1, len(lengths) // 24)
        for i, value in enumerate(lengths):
            if i % step == 0 or i == len(lengths) - 1:
                ecdf.append({"chars": value, "frac": round((i + 1) / len(lengths), 4)})

    lab = corpus.setdefault("lab", {})
    harness = lab.setdefault("harness", {})
    harness.setdefault("planned_attempts", 5)
    lab["charts"] = {
        "source": "tasks/latest/<slug>/instruction.md for the 100 gallery rows",
        "copied_other_labs": False,
        "instruction_length": {
            "n": len(lengths),
            "min": lengths[0] if lengths else 0,
            "p25": percentile(25),
            "median": percentile(50),
            "p75": percentile(75),
            "max": lengths[-1] if lengths else 0,
            "mean": int(sum(lengths) / len(lengths)) if lengths else 0,
            "histogram": histogram,
            "ecdf": ecdf,
        },
        "language_mix": [{"language": name, "n": count} for name, count in lang_counts.most_common()],
    }
    lab["instruction_previews"] = previews
    return corpus


def write_corpus(selected: list[dict], catalog_by_slug: dict[str, dict], meta: dict | None) -> dict:
    tasks = []
    for item in selected:
        slug = item.get("slug") or item.get("id")
        catalog_row = catalog_by_slug[slug]
        tasks.append(build_corpus_task(catalog_row))
    tasks.sort(key=lambda t: (CATEGORY_ORDER.index(t["category"]), t["name"].lower()))
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    selected_counts = Counter(t["category"] for t in tasks)
    corpus = {
        "lab": {
            "name": "Applied Work Worlds Lab",
            "brand": "Applied Work",
            "mvp_size": MVP_SIZE,
            "inventory_size": INVENTORY_SIZE,
            "generated_utc": generated,
            "rollouts_status": "not_run",
            "runtime": "private Harbor 0.22 + terminus-2 / oracle",
            "honesty": {
                "stump_pct": None,
                "model_scores": False,
                "copied_caudal_scores": False,
                "note": (
                    "This gallery lists authored Harbor packages. Measured chips "
                    "appear only after private Harbor jobs exist for a frozen "
                    "batch slug. Do not invent stump percentages or paste another lab's "
                    "model scores."
                ),
            },
            "category_mix": {cat: selected_counts.get(cat, 0) for cat in CATEGORY_ORDER},
            "difficulty_counts": (meta or {}).get("difficulty_counts")
            or {"hard": sum(1 for t in tasks if (t.get("difficulty") or "").lower() == "hard")},
            "subcategory_mix": dict(
                Counter(
                    sub
                    for t in tasks
                    for sub in (t.get("subcategories") or [])
                )
            ),
            "integrity": {
                "gallery": MVP_SIZE,
                "inventory": INVENTORY_SIZE,
                "all_hard": all((t.get("difficulty") or "").lower() == "hard" for t in tasks),
                "unique_slugs": len({t["slug"] for t in tasks}) == len(tasks),
                "note": (
                    "Author-labeled hard, verified against catalog and task.toml. "
                    "Not a measured stump rate. Model cells stay empty until Harbor ingest."
                ),
            },
            "inventory_category_counts": (meta or {}).get("inventory_category_counts"),
            "quotas": (meta or {}).get("quotas"),
            "dropped_near_duplicates": (meta or {}).get("dropped_near_duplicates"),
        },
        "tasks": tasks,
    }
    attach_batch_placeholder(corpus)
    enrich_overview_stats(corpus)
    CORPUS_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(corpus, ensure_ascii=False, indent=2)
    CORPUS_JSON.write_text(payload + "\n", encoding="utf-8")
    CORPUS_JS.write_text("window.AW_CORPUS = " + payload + ";\n", encoding="utf-8")
    return corpus


def print_report(corpus: dict, meta: dict | None) -> None:
    lab = corpus["lab"]
    print(f"tasks: {len(corpus['tasks'])}")
    print("category mix:")
    for cat in CATEGORY_ORDER:
        n = lab["category_mix"].get(cat, 0)
        quota = (lab.get("quotas") or {}).get(cat, "?")
        inv = (lab.get("inventory_category_counts") or {}).get(cat, "?")
        print(f"  {cat:36} {n:3}  (quota {quota}, inventory {inv})")
    diffs = Counter(t["difficulty"] for t in corpus["tasks"])
    print("difficulty:", dict(diffs))
    if meta and meta.get("dropped_near_duplicates"):
        for drop in meta["dropped_near_duplicates"]:
            print(f"dropped near-duplicate: {drop['slug']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--select",
        action="store_true",
        help="rebuild docs/lab_mvp_100.jsonl from the catalog, then write lab/corpus.json",
    )
    args = parser.parse_args()

    catalog_rows = load_catalog()
    catalog_by_slug = {r["id"]: r for r in catalog_rows}
    meta = None

    if args.select:
        chosen, meta = select_mvp(catalog_rows)
        write_jsonl(chosen, JSONL)
        selected = load_jsonl(JSONL)
    else:
        if not JSONL.is_file():
            raise SystemExit(f"missing {JSONL}; run with --select first")
        selected = load_jsonl(JSONL)
        if len(selected) != MVP_SIZE:
            raise SystemExit(f"{JSONL} has {len(selected)} rows, expected {MVP_SIZE}")
        # Recompute quotas for the corpus header even on a corpus-only rebuild.
        inventory_counts = Counter(r.get("category") or "unknown" for r in catalog_rows)
        meta = {
            "inventory_category_counts": dict(inventory_counts),
            "quotas": hamilton_quotas(inventory_counts, MVP_SIZE),
            "dropped_near_duplicates": [
                {
                    "slug": slug,
                    "reason": (
                        "near-duplicate of "
                        f"{KEEP_NEAR_DUPLICATE_SLUG} (instruction Jaccard ≥ 0.72); kept one"
                    ),
                }
                for slug in DROP_NEAR_DUPLICATE_SLUGS
            ],
        }

    slugs = [r["slug"] for r in selected]
    uuids = [r["uuid"] for r in selected]
    if len(set(slugs)) != MVP_SIZE or len(set(uuids)) != MVP_SIZE:
        raise SystemExit("lab_mvp_100.jsonl is not unique on slug or uuid")
    missing = [s for s in slugs if s not in catalog_by_slug]
    if missing:
        raise SystemExit(f"slugs not in catalog: {missing[:5]}")

    corpus = write_corpus(selected, catalog_by_slug, meta)
    print_report(corpus, meta)
    if args.select:
        print(f"wrote {JSONL.relative_to(ROOT)}")
    print(f"wrote {CORPUS_JSON.relative_to(ROOT)}")
    print(f"wrote {CORPUS_JS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
