"""Freeze docs/lab_batch_01.jsonl: 10 unique packages from the lab 100.

Rule (Applied Work Worlds Lab spec):
- All 8 TB categories represented; debugging gets its only seat
- Two extra seats from scientific-computing and security (2+2)
- Maximize distinct primary languages; cover the eight named primaries
  (Go, Rust, Python, TypeScript, C, C++, Java, Bash) when the 100 allows
- Unique slug and uuid; packages must still have oracle + tests on disk

Recompute this list if an oracle run drops a package.
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
    MVP_JSONL,
    PREFERRED_LANGS,
    TASKS_LATEST,
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


def to_jsonl_row(row: dict, rank: int) -> dict:
    return {
        "batch": 1,
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
        "selection_reason": (
            "batch_01: 8 categories + extra sci/security; maximize distinct "
            "primary languages from docs/lab_mvp_100.jsonl"
            + (
                "; oracle-dropped slugs excluded via docs/lab_batch_01_exclusions.json"
                if load_exclusions()
                else ""
            )
        ),
    }


def select(exclude_slugs: set[str] | None = None) -> list[dict]:
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
    chosen = choose_batch(pool)
    ordered = sorted(
        chosen,
        key=lambda r: (CATEGORY_ORDER.index(r["category"]), r["primary_language"], r["slug"]),
    )
    return [to_jsonl_row(row, i) for i, row in enumerate(ordered, start=1)]


def report(rows: list[dict]) -> None:
    langs = [r["primary_language"] for r in rows]
    cats = [r["category"] for r in rows]
    print(f"batch_01: {len(rows)} tasks")
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
    args = parser.parse_args()
    rows = select()
    report(rows)
    if args.check:
        existing = load_jsonl(BATCH_01_JSONL)
        got = [r["slug"] for r in existing]
        want = [r["slug"] for r in rows]
        if got != want:
            raise SystemExit(f"lab_batch_01.jsonl does not match selector\nwant {want}\ngot  {got}")
        print("freeze matches selector")
        return
    write_jsonl(BATCH_01_JSONL, rows)
    print(f"wrote {BATCH_01_JSONL.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
