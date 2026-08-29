"""Freeze lab_batch_0N.jsonl: 10 unique packages from the lab 100.

Batch 01 rule (Applied Work Worlds Lab spec):
- All 8 TB categories represented; debugging gets its only seat
- Two extra seats from scientific-computing and security (2+2)
- Maximize distinct primary languages; cover the eight named primaries
  (Go, Rust, Python, TypeScript, C, C++, Java, Bash) when the 100 allows
- Unique slug and uuid; packages must still have oracle + tests on disk

Batches 02–05 cannot copy that seat map (debugging has only one seat in the 100).
They pick 10 from the remaining 90, covering leftover categories then leftover
primary languages, then catalog selection score.

Recompute a list if an oracle run drops a package.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lab_common import (  # noqa: E402
    BATCH_01_EXCLUSIONS_JSON,
    BATCH_01_JSONL,
    BATCH_01_SEATS,
    CATEGORY_ORDER,
    MEASURED_BATCH_MAX,
    MVP_JSONL,
    PREFERRED_LANGS,
    TASKS_LATEST,
    batch_jsonl_path,
    load_all_batches,
    load_jsonl,
    primary_language,
    write_jsonl,
)


def is_standard_package(slug: str) -> bool:
    pkg = TASKS_LATEST / slug
    return (
        (pkg / "instruction.md").is_file()
        and (pkg / "task.toml").is_file()
        and (pkg / "environment").is_dir()
        and (pkg / "solution").is_dir()
        and (pkg / "tests").is_dir()
    )


def load_exclusions(path: Path | None = None) -> set[str]:
    path = path or BATCH_01_EXCLUSIONS_JSON
    if not path.is_file():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {str(x) for x in data}
    slugs = set()
    for row in data.get("slugs") or data.get("dropped") or []:
        if isinstance(row, str):
            slugs.add(row)
        elif isinstance(row, dict) and row.get("slug"):
            slugs.add(str(row["slug"]))
    return slugs


def enrich(row: dict) -> dict | None:
    slug = row.get("slug") or row.get("id")
    if not slug:
        return None
    if not row.get("has_oracle") or not row.get("has_tests"):
        return None
    if not is_standard_package(slug):
        return None
    lang = primary_language(row.get("languages") or [])
    if not lang:
        return None
    out = dict(row)
    out["slug"] = slug
    out["primary_language"] = lang
    out["selection_score"] = float(row.get("selection_score") or 0)
    out["n_versions"] = int(row.get("n_versions") or 0)
    return out


def best_per_category_language(rows: list[dict]) -> dict[str, dict[str, dict]]:
    best: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        cat = row.get("category") or "unknown"
        lang = row["primary_language"]
        current = best[cat].get(lang)
        key = (
            row["selection_score"],
            row["n_versions"],
            row["slug"],
        )
        if current is None:
            best[cat][lang] = row
            continue
        other = (current["selection_score"], current["n_versions"], current["slug"])
        if key > other:
            best[cat][lang] = row
    return best


def set_score(chosen: list[dict]) -> tuple:
    langs = [r["primary_language"] for r in chosen]
    distinct = len(set(langs))
    preferred = sum(1 for lang in PREFERRED_LANGS if lang in langs)
    score_sum = sum(r["selection_score"] for r in chosen)
    versions = sum(r["n_versions"] for r in chosen)
    slugs = tuple(sorted(r["slug"] for r in chosen))
    return (distinct, preferred, score_sum, versions, slugs)


def choose_batch(pool: list[dict]) -> list[dict]:
    by_cat_lang = best_per_category_language(pool)
    missing = [cat for cat in CATEGORY_ORDER if cat not in by_cat_lang]
    if missing:
        raise SystemExit(f"100-set is missing categories: {missing}")

    cat_lists: dict[str, list[dict]] = {}
    for cat, seats in BATCH_01_SEATS.items():
        options = list(by_cat_lang[cat].values())
        if len(options) < seats:
            raise SystemExit(f"{cat}: only {len(options)} primary-language buckets, need {seats}")
        cat_lists[cat] = options

    best: tuple | None = None
    best_set: list[dict] | None = None

    sci_pairs = list(itertools.combinations(cat_lists["scientific-computing"], 2))
    sec_pairs = list(itertools.combinations(cat_lists["security"], 2))
    singles = [
        cat_lists["system-administration"],
        cat_lists["build-and-dependency-management"],
        cat_lists["data-processing"],
        cat_lists["machine-learning"],
        cat_lists["games"],
        cat_lists["debugging"],
    ]

    for sci in sci_pairs:
        for sec in sec_pairs:
            for combo in itertools.product(*singles):
                chosen = list(sci) + list(sec) + list(combo)
                slugs = [r["slug"] for r in chosen]
                uuids = [r.get("uuid") for r in chosen]
                if len(set(slugs)) != 10 or len(set(uuids)) != 10:
                    continue
                score = set_score(chosen)
                if best is None or score[:4] > best[:4] or (score[:4] == best[:4] and score[4] < best[4]):
                    best = score
                    best_set = chosen

    if not best_set:
        raise SystemExit("no unique 10-set satisfied seats + uniqueness")
    if best[0] < 8:
        raise SystemExit(f"best set only covers {best[0]} languages; need ≥8")
    missing_pref = [lang for lang in PREFERRED_LANGS if lang not in {r["primary_language"] for r in best_set}]
    # Preferred coverage is maximized by the score; do not fail if the 100 cannot supply one.
    _ = missing_pref
    return best_set


def choose_later_batch(pool: list[dict], n: int = 10) -> list[dict]:
    """Greedy 10-set from remaining packages. Do not reuse Batch 01's 2+2+1 seats."""
    chosen: list[dict] = []
    used_slugs: set[str] = set()
    used_langs: set[str] = set()
    used_cats: set[str] = set()

    def remaining() -> list[dict]:
        return [row for row in pool if row["slug"] not in used_slugs]

    def pick(row: dict) -> None:
        chosen.append(row)
        used_slugs.add(row["slug"])
        used_langs.add(row["primary_language"])
        used_cats.add(row["category"])

    for cat in CATEGORY_ORDER:
        if len(chosen) >= n:
            break
        cands = [row for row in remaining() if row.get("category") == cat]
        if not cands:
            continue
        cands.sort(
            key=lambda row: (
                row["primary_language"] in used_langs,
                -row["selection_score"],
                -row["n_versions"],
                row["slug"],
            )
        )
        pick(cands[0])

    while len(chosen) < n:
        cands = remaining()
        if not cands:
            break
        cands.sort(
            key=lambda row: (
                row["primary_language"] in used_langs,
                row["category"] in used_cats,
                -row["selection_score"],
                -row["n_versions"],
                row["slug"],
            )
        )
        pick(cands[0])

    if len(chosen) != n:
        raise SystemExit(f"later-batch selector only found {len(chosen)} packages, need {n}")
    slugs = [row["slug"] for row in chosen]
    uuids = [row.get("uuid") for row in chosen]
    if len(set(slugs)) != n or len(set(uuids)) != n:
        raise SystemExit("later-batch selector produced duplicate slug or uuid")
    return chosen


def to_jsonl_row(row: dict, rank: int, batch: int = 1) -> dict:
    if batch == 1:
        reason = (
            "batch_01: 8 categories + extra sci/security; maximize distinct "
            "primary languages from docs/lab_mvp_100.jsonl"
            + (
                "; oracle-dropped slugs excluded via docs/lab_batch_01_exclusions.json"
                if load_exclusions()
                else ""
            )
        )
    else:
        reason = (
            f"batch_{batch:02d}: remaining gallery after earlier frozen tens; "
            "cover leftover categories then leftover primary languages, then "
            "catalog selection score; debugging has no leftover seat in the 100"
        )
    return {
        "batch": batch,
        "batch_rank": rank,
        "slug": row["slug"],
        "uuid": row.get("uuid") or row.get("sid"),
        "category": row.get("category"),
        "difficulty": row.get("difficulty"),
        "languages": row.get("languages") or [],
        "primary_language": row["primary_language"],
        "title": row.get("title"),
        "package_dir": row.get("package_dir") or f"tasks/latest/{row['slug']}",
        "has_oracle": True,
        "has_tests": True,
        "n_versions": row.get("n_versions"),
        "selection_score": row.get("selection_score"),
        "selection_reason": reason,
    }


def pool_from_mvp(exclude_slugs: set[str] | None = None) -> list[dict]:
    source = load_jsonl(MVP_JSONL)
    if len(source) != 100:
        raise SystemExit(f"{MVP_JSONL} has {len(source)} rows, expected 100")
    excluded = load_exclusions()
    if exclude_slugs:
        excluded |= set(exclude_slugs)
    pool = []
    for row in source:
        enriched = enrich(row)
        if enriched and enriched["slug"] not in excluded:
            pool.append(enriched)
    return pool


def select(exclude_slugs: set[str] | None = None) -> list[dict]:
    chosen = choose_batch(pool_from_mvp(exclude_slugs))
    ordered = sorted(
        chosen,
        key=lambda r: (CATEGORY_ORDER.index(r["category"]), r["primary_language"], r["slug"]),
    )
    return [to_jsonl_row(row, i, batch=1) for i, row in enumerate(ordered, start=1)]


def select_later(batch: int, taken_slugs: set[str]) -> list[dict]:
    if batch < 2 or batch > MEASURED_BATCH_MAX:
        raise SystemExit(f"later batch must be 2..{MEASURED_BATCH_MAX}, got {batch}")
    pool = pool_from_mvp(taken_slugs)
    chosen = choose_later_batch(pool, n=10)
    ordered = sorted(
        chosen,
        key=lambda r: (CATEGORY_ORDER.index(r["category"]), r["primary_language"], r["slug"]),
    )
    return [to_jsonl_row(row, i, batch=batch) for i, row in enumerate(ordered, start=1)]


def select_batches_02_05() -> dict[int, list[dict]]:
    taken = {row["slug"] for row in select()}
    frozen = {1: select()}
    for batch in range(2, MEASURED_BATCH_MAX + 1):
        rows = select_later(batch, taken)
        frozen[batch] = rows
        taken |= {row["slug"] for row in rows}
    return frozen


def report(rows: list[dict]) -> None:
    langs = [r["primary_language"] for r in rows]
    cats = [r["category"] for r in rows]
    batch = rows[0]["batch"] if rows else 0
    print(f"batch_{batch:02d}: {len(rows)} tasks")
    print(f"categories: {len(set(cats))} unique → {cats}")
    print(f"languages:  {len(set(langs))} unique → {langs}")
    print(f"preferred covered: {[p for p in PREFERRED_LANGS if p in langs]}")
    print(f"preferred missing: {[p for p in PREFERRED_LANGS if p not in langs]}")
    for row in rows:
        print(
            f"  {row['batch_rank']:2}  {row['category']:36}  "
            f"{row['primary_language']:12}  {row['slug'][:72]}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate an existing freeze; do not write")
    parser.add_argument(
        "--write-later",
        action="store_true",
        help="write docs/lab_batch_02.jsonl … lab_batch_05.jsonl from remaining 90",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=1,
        help="which frozen ten to print/write (1 writes lab_batch_01.jsonl)",
    )
    args = parser.parse_args()

    if args.write_later:
        frozen = select_batches_02_05()
        for batch, rows in frozen.items():
            report(rows)
            path = batch_jsonl_path(batch)
            if args.check:
                existing = load_jsonl(path)
                got = [r["slug"] for r in existing]
                want = [r["slug"] for r in rows]
                if got != want:
                    raise SystemExit(f"{path.name} does not match selector\nwant {want}\ngot  {got}")
                print(f"freeze matches selector for batch {batch:02d}")
                continue
            if batch == 1:
                continue
            write_jsonl(path, rows)
            print(f"wrote {path.relative_to(ROOT)}")
        all_slugs = [row["slug"] for rows in frozen.values() for row in rows]
        if len(set(all_slugs)) != 50:
            raise SystemExit(f"expected 50 unique measured slugs, got {len(set(all_slugs))}")
        return

    if args.batch == 1:
        rows = select()
        path = BATCH_01_JSONL
    else:
        taken = {row["slug"] for row in load_all_batches(args.batch - 1)}
        if args.batch > 1 and len(taken) != 10 * (args.batch - 1):
            raise SystemExit(
                f"need frozen batches 01..{args.batch - 1:02d} on disk before selecting batch {args.batch:02d}"
            )
        rows = select_later(args.batch, taken)
        path = batch_jsonl_path(args.batch)
    report(rows)
    if args.check:
        existing = load_jsonl(path)
        got = [r["slug"] for r in existing]
        want = [r["slug"] for r in rows]
        if got != want:
            raise SystemExit(f"{path.name} does not match selector\nwant {want}\ngot  {got}")
        print("freeze matches selector")
        return
    write_jsonl(path, rows)
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
