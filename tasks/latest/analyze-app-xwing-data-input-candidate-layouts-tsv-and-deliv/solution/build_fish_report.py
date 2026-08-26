#!/usr/bin/env python3
import argparse
import csv
import json
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path


CELL_RE = re.compile(r"r([1-9])c([1-9])\Z")
SIZE_NAMES = {2: "X_WING", 3: "SWORDFISH", 4: "JELLYFISH"}
FAMILIES = ("BASIC", "FRANKEN", "MUTANT")
FIN_STATES = ("FINNED", "SASHIMI", "UNFINNED")


def box_index(row, column):
    return ((row - 1) // 3) * 3 + (column - 1) // 3 + 1


def build_houses():
    houses = {}
    for number in range(1, 10):
        houses[f"R{number}"] = frozenset((number, column) for column in range(1, 10))
        houses[f"C{number}"] = frozenset((row, number) for row in range(1, 10))
        houses[f"B{number}"] = frozenset(
            (row, column)
            for row in range(1, 10)
            for column in range(1, 10)
            if box_index(row, column) == number
        )
    return houses


HOUSES = build_houses()
HOUSE_NAMES = tuple(sorted(HOUSES))


def parse_candidate_spec(spec):
    candidates = defaultdict(set)
    if not spec:
        return candidates
    for group in spec.split(";"):
        digit_text, separator, cells_text = group.partition(":")
        if not separator or digit_text not in "123456789" or len(digit_text) != 1:
            raise ValueError(f"invalid candidate group: {group!r}")
        if not cells_text:
            raise ValueError(f"candidate group has no cells: {group!r}")
        for cell_text in cells_text.split(","):
            match = CELL_RE.fullmatch(cell_text)
            if match is None:
                raise ValueError(f"invalid candidate cell: {cell_text!r}")
            candidates[int(digit_text)].add(
                (int(match.group(1)), int(match.group(2)))
            )
    return candidates


def sees(cell_a, cell_b):
    if cell_a == cell_b:
        return False
    return (
        cell_a[0] == cell_b[0]
        or cell_a[1] == cell_b[1]
        or box_index(*cell_a) == box_index(*cell_b)
    )


def fish_family(base_names, cover_names):
    base_types = {name[0] for name in base_names}
    cover_types = {name[0] for name in cover_names}
    if (base_types, cover_types) in (({"R"}, {"C"}), ({"C"}, {"R"})):
        return "BASIC"

    has_box = "B" in base_types or "B" in cover_types
    base_lines = base_types - {"B"}
    cover_lines = cover_types - {"B"}
    if (
        has_box
        and len(base_lines) == 1
        and len(cover_lines) == 1
        and base_lines != cover_lines
    ):
        return "FRANKEN"
    return "MUTANT"


def candidate_house_counts(cells, names):
    return {
        cell: sum(cell in HOUSES[name] for name in names)
        for cell in cells
    }


def enumerate_patterns(candidates):
    patterns = []
    eligible_bases = [
        name for name in HOUSE_NAMES if len(candidates & HOUSES[name]) >= 2
    ]

    for size in SIZE_NAMES:
        for base_names in combinations(eligible_bases, size):
            base_cells = set().union(*(candidates & HOUSES[name] for name in base_names))
            base_counts = candidate_house_counts(base_cells, base_names)
            cover_pool = [
                name
                for name in HOUSE_NAMES
                if name not in base_names and base_cells & HOUSES[name]
            ]

            for cover_names in combinations(cover_pool, size):
                cover_counts = candidate_house_counts(base_cells, cover_names)
                exo_fins = {cell for cell in base_cells if cover_counts[cell] == 0}
                endo_fins = {cell for cell in base_cells if base_counts[cell] > 1}
                fins = exo_fins | endo_fins
                core = {
                    cell
                    for cell in base_cells
                    if base_counts[cell] == 1 and cover_counts[cell] >= 1
                }

                if any(not (core & HOUSES[name]) for name in base_names):
                    continue
                if any(not (core & HOUSES[name]) for name in cover_names):
                    continue

                outside_base = {
                    cell
                    for cell in candidates - base_cells
                    if any(cell in HOUSES[name] for name in cover_names)
                }
                cannibalistic = {
                    cell
                    for cell in base_cells
                    if cover_counts[cell] > 1 and cell not in fins
                }
                possible_targets = outside_base | cannibalistic
                targets = {
                    cell
                    for cell in possible_targets
                    if all(sees(cell, fin) for fin in fins)
                }
                if not targets:
                    continue

                if not fins:
                    fin_state = "UNFINNED"
                elif exo_fins and any(
                    len(core & HOUSES[name]) < 2 for name in base_names
                ):
                    fin_state = "SASHIMI"
                else:
                    fin_state = "FINNED"

                patterns.append(
                    {
                        "size_number": size,
                        "size": SIZE_NAMES[size],
                        "family": fish_family(base_names, cover_names),
                        "fin_state": fin_state,
                        "fin_count": len(fins),
                        "base_names": base_names,
                        "cover_names": cover_names,
                        "exo_fins": exo_fins,
                        "endo_fins": endo_fins,
                        "cannibalistic_targets": targets & base_cells,
                        "targets": targets,
                    }
                )
    return patterns


def classify_record(candidate_spec):
    result = {
        "sizes": set(),
        "families": set(),
        "fin_states": set(),
        "fish_digits": set(),
        "endo_fin_digits": set(),
        "cannibalistic_digits": set(),
        "targets": set(),
    }
    target_rows = []
    for digit, candidates in parse_candidate_spec(candidate_spec).items():
        patterns = enumerate_patterns(candidates)
        if not patterns:
            continue
        family_rank = {"BASIC": 0, "FRANKEN": 1, "MUTANT": 2}
        fin_rank = {"UNFINNED": 0, "FINNED": 1, "SASHIMI": 2}
        winners = {}
        for pattern in patterns:
            for target in pattern["targets"]:
                rank = (
                    pattern["size_number"],
                    family_rank[pattern["family"]],
                    fin_rank[pattern["fin_state"]],
                    pattern["fin_count"],
                    bool(pattern["endo_fins"]),
                    target in pattern["cannibalistic_targets"],
                    pattern["base_names"],
                    pattern["cover_names"],
                )
                if target not in winners or rank < winners[target][0]:
                    winners[target] = (rank, pattern)
        result["fish_digits"].add(digit)
        for target, (_, pattern) in winners.items():
            result["sizes"].add(pattern["size"])
            result["families"].add(pattern["family"])
            result["fin_states"].add(pattern["fin_state"])
            if pattern["endo_fins"]:
                result["endo_fin_digits"].add(digit)
            if target in pattern["cannibalistic_targets"]:
                result["cannibalistic_digits"].add(digit)
            result["targets"].add((digit, target[0], target[1]))
            target_rows.append(
                {
                    "digit": digit,
                    "target": f"r{target[0]}c{target[1]}",
                    "target_cell": target,
                    "size": pattern["size"],
                    "family": pattern["family"],
                    "fin_state": pattern["fin_state"],
                    "base_houses": list_field(pattern["base_names"]),
                    "cover_houses": list_field(pattern["cover_names"]),
                    "exo_fins": list_field(
                        f"r{row}c{column}"
                        for row, column in sorted(pattern["exo_fins"])
                    ),
                    "endo_fins": list_field(
                        f"r{row}c{column}"
                        for row, column in sorted(pattern["endo_fins"])
                    ),
                    "cannibalistic": str(
                        target in pattern["cannibalistic_targets"]
                    ).lower(),
                }
            )
    return result, target_rows


def list_field(values):
    materialized = [str(value) for value in values]
    return ",".join(materialized) if materialized else "-"


def read_records(input_path):
    with input_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != ["name", "candidate_spec"]:
            raise ValueError("input must have name and candidate_spec columns")
        records = list(reader)
    names = [record["name"] for record in records]
    if any(not name for name in names) or len(names) != len(set(names)):
        raise ValueError("record names must be non-empty and unique")
    return records


def build_rows(records):
    rows = []
    target_rows = []
    for record in sorted(records, key=lambda item: item["name"]):
        result, record_targets = classify_record(record["candidate_spec"])
        for target_row in record_targets:
            target_rows.append({"name": record["name"], **target_row})
        rows.append(
            {
                "name": record["name"],
                "tier": "advanced" if result["targets"] else "basic",
                "sizes": list_field(sorted(result["sizes"])),
                "families": list_field(sorted(result["families"])),
                "fin_states": list_field(sorted(result["fin_states"])),
                "fish_digits": list_field(sorted(result["fish_digits"])),
                "endo_fin_digits": list_field(sorted(result["endo_fin_digits"])),
                "cannibalistic_digits": list_field(
                    sorted(result["cannibalistic_digits"])
                ),
                "elimination_targets": list_field(
                    f"{digit}:r{row}c{column}"
                    for digit, row, column in sorted(result["targets"])
                ),
            }
        )
    target_rows.sort(
        key=lambda row: (
            row["name"],
            row["digit"],
            row["target_cell"][0],
            row["target_cell"][1],
        )
    )
    for target_row in target_rows:
        del target_row["target_cell"]
    return rows, target_rows


def split_field(value):
    return [] if value == "-" else value.split(",")


def build_summary(input_path, rows):
    size_counts = {name: 0 for name in sorted(SIZE_NAMES.values())}
    family_counts = {name: 0 for name in FAMILIES}
    fin_state_counts = {name: 0 for name in FIN_STATES}
    digit_counts = {str(digit): 0 for digit in range(1, 10)}
    multiple_families = []
    multiple_sizes = []
    target_total = 0

    for row in rows:
        sizes = split_field(row["sizes"])
        families = split_field(row["families"])
        fin_states = split_field(row["fin_states"])
        digits = split_field(row["fish_digits"])
        for value in sizes:
            size_counts[value] += 1
        for value in families:
            family_counts[value] += 1
        for value in fin_states:
            fin_state_counts[value] += 1
        for value in digits:
            digit_counts[value] += 1
        if len(families) > 1:
            multiple_families.append(row["name"])
        if len(sizes) > 1:
            multiple_sizes.append(row["name"])
        target_total += len(split_field(row["elimination_targets"]))

    advanced_count = sum(row["tier"] == "advanced" for row in rows)
    return {
        "input_file": input_path.name,
        "record_count": len(rows),
        "advanced_count": advanced_count,
        "basic_count": len(rows) - advanced_count,
        "size_counts": size_counts,
        "family_counts": family_counts,
        "fin_state_counts": fin_state_counts,
        "fish_digit_counts": digit_counts,
        "endo_fin_record_count": sum(
            row["endo_fin_digits"] != "-" for row in rows
        ),
        "cannibalistic_record_count": sum(
            row["cannibalistic_digits"] != "-" for row in rows
        ),
        "records_with_multiple_families": multiple_families,
        "records_with_multiple_sizes": multiple_sizes,
        "total_elimination_targets": target_total,
    }


def write_report(input_path, targets_path, ratings_path, summary_path):
    rows, target_rows = build_rows(read_records(input_path))
    targets_path.parent.mkdir(parents=True, exist_ok=True)
    ratings_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    target_fieldnames = (
        "name",
        "digit",
        "target",
        "size",
        "family",
        "fin_state",
        "base_houses",
        "cover_houses",
        "exo_fins",
        "endo_fins",
        "cannibalistic",
    )
    with targets_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=target_fieldnames, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(target_rows)
    fieldnames = (
        "name",
        "tier",
        "sizes",
        "families",
        "fin_states",
        "fish_digits",
        "endo_fin_digits",
        "cannibalistic_digits",
        "elimination_targets",
    )
    with ratings_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    summary_path.write_text(
        json.dumps(build_summary(input_path, rows), indent=2) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--ratings", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    write_report(args.input, args.targets, args.ratings, args.summary)


if __name__ == "__main__":
    main()
