import csv
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path


APP_DIR = Path(os.environ.get("XWING_APP_DIR", "/app/xwing-data"))
OUT_DIR = Path(os.environ.get("XWING_OUT_DIR", "/app/out"))
PUBLIC_INPUT = APP_DIR / "input" / "candidate_layouts.tsv"
PUBLIC_TARGETS = OUT_DIR / "fish_targets.tsv"
PUBLIC_RATINGS = OUT_DIR / "fish_ratings.tsv"
PUBLIC_SUMMARY = OUT_DIR / "fish_summary.json"
RATING_HEADER = [
    "name",
    "tier",
    "sizes",
    "families",
    "fin_states",
    "fish_digits",
    "endo_fin_digits",
    "cannibalistic_digits",
    "elimination_targets",
]
TARGET_HEADER = [
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
]
INPUT_SHA256 = "0b2252f4fb8d88bdad1518f3fa66cd2b0eaaea8a390692bbfda02a25a90b59ef"
TARGET_ROWS_SHA256 = "edcb728ed6ec42d33f8cee71c038ab39b62641a71d8a56a9457e22572e00025f"


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows_digest(rows):
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def read_tsv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return reader.fieldnames, list(reader)


def split_field(value):
    return [] if value == "-" else value.split(",")


def joined(values):
    return ",".join(values) if values else "-"


def parse_cell(value):
    match = re.fullmatch(r"r([1-9])c([1-9])", value)
    assert match is not None
    return int(match.group(1)), int(match.group(2))


def box_index(cell):
    return ((cell[0] - 1) // 3) * 3 + (cell[1] - 1) // 3 + 1


def in_house(cell, house):
    number = int(house[1:])
    if house[0] == "R":
        return cell[0] == number
    if house[0] == "C":
        return cell[1] == number
    return box_index(cell) == number


def family_for(bases, covers):
    base_types = {house[0] for house in bases}
    cover_types = {house[0] for house in covers}
    if (base_types, cover_types) in (({"R"}, {"C"}), ({"C"}, {"R"})):
        return "BASIC"
    base_lines = base_types - {"B"}
    cover_lines = cover_types - {"B"}
    if (
        "B" in base_types | cover_types
        and len(base_lines) == 1
        and len(cover_lines) == 1
        and base_lines != cover_lines
    ):
        return "FRANKEN"
    return "MUTANT"


def source_records():
    _, records = read_tsv(PUBLIC_INPUT)
    indexed = {}
    raw_cells = {}
    for record in records:
        digits = defaultdict(set)
        raw_digits = {}
        for group in record["candidate_spec"].split(";"):
            digit_text, cells_text = group.split(":", 1)
            cells = cells_text.split(",")
            digit = int(digit_text)
            raw_digits[digit] = cells
            digits[digit].update(parse_cell(cell) for cell in cells)
        indexed[record["name"]] = digits
        raw_cells[record["name"]] = raw_digits
    return records, indexed, raw_cells


def test_runtime_is_restricted():
    """The verifier runs with a protected interpreter and immutable source inventory."""
    if os.name == "posix" and str(APP_DIR).startswith("/app/"):
        assert os.geteuid() != 0
        assert not os.access(Path(sys.executable).resolve(), os.W_OK)
        assert not os.access(PUBLIC_INPUT, os.W_OK)
        assert os.access(OUT_DIR, os.W_OK)


def test_source_dataset_and_duplicate_fixture():
    """The source is unchanged and its paired repeated cell has set semantics."""
    assert file_digest(PUBLIC_INPUT) == INPUT_SHA256
    records, indexed, raw_cells = source_records()
    assert [record["name"] for record in records] == sorted(
        record["name"] for record in records
    )
    assert len(raw_cells["layout-032"][1]) > len(set(raw_cells["layout-032"][1]))
    assert indexed["layout-029"] == indexed["layout-032"]


def test_target_ledger_is_complete_and_sorted():
    """The target ledger has the required schema, committed contents, and ordering."""
    fieldnames, rows = read_tsv(PUBLIC_TARGETS)
    assert fieldnames == TARGET_HEADER
    assert rows_digest(rows) == TARGET_ROWS_SHA256
    keys = [
        (row["name"], int(row["digit"]), *parse_cell(row["target"]))
        for row in rows
    ]
    assert keys == sorted(keys)


def test_target_ledger_geometry_is_valid():
    """Every ledger row satisfies its recorded house, core, fin, family, and target geometry."""
    _, candidates_by_record, _ = source_records()
    _, rows = read_tsv(PUBLIC_TARGETS)
    size_names = {2: "X_WING", 3: "SWORDFISH", 4: "JELLYFISH"}
    for row in rows:
        candidates = candidates_by_record[row["name"]][int(row["digit"])]
        bases = split_field(row["base_houses"])
        covers = split_field(row["cover_houses"])
        assert bases == sorted(bases)
        assert covers == sorted(covers)
        assert not set(bases) & set(covers)
        assert len(bases) == len(covers)
        assert row["size"] == size_names[len(bases)]
        assert all(
            len({cell for cell in candidates if in_house(cell, base)}) >= 2
            for base in bases
        )

        base_cells = {
            cell for cell in candidates if any(in_house(cell, base) for base in bases)
        }
        base_counts = {
            cell: sum(in_house(cell, base) for base in bases) for cell in base_cells
        }
        cover_counts = {
            cell: sum(in_house(cell, cover) for cover in covers) for cell in base_cells
        }
        exo_fins = {cell for cell in base_cells if cover_counts[cell] == 0}
        endo_fins = {cell for cell in base_cells if base_counts[cell] > 1}
        core = {
            cell
            for cell in base_cells
            if base_counts[cell] == 1 and cover_counts[cell] >= 1
        }
        assert all(
            any(in_house(cell, house) for cell in core) for house in bases + covers
        )
        assert split_field(row["exo_fins"]) == [
            f"r{row_number}c{column}" for row_number, column in sorted(exo_fins)
        ]
        assert split_field(row["endo_fins"]) == [
            f"r{row_number}c{column}" for row_number, column in sorted(endo_fins)
        ]
        assert row["family"] == family_for(bases, covers)
        if not exo_fins and not endo_fins:
            expected_fin_state = "UNFINNED"
        elif exo_fins and any(
            len({cell for cell in core if in_house(cell, base)}) < 2
            for base in bases
        ):
            expected_fin_state = "SASHIMI"
        else:
            expected_fin_state = "FINNED"
        assert row["fin_state"] == expected_fin_state

        target = parse_cell(row["target"])
        fins = exo_fins | endo_fins
        outside = target not in base_cells and any(
            in_house(target, cover) for cover in covers
        )
        cannibalistic = (
            target in base_cells and cover_counts[target] > 1 and target not in fins
        )
        assert target in candidates
        assert outside or cannibalistic
        assert row["cannibalistic"] == str(cannibalistic).lower()
        assert all(
            target != fin
            and (
                target[0] == fin[0]
                or target[1] == fin[1]
                or box_index(target) == box_index(fin)
            )
            for fin in fins
        )


def test_ratings_reconcile_to_ledger_and_duplicate_pair():
    """Ratings derive from the ledger and repeated candidates do not alter results."""
    _, source_rows, _ = source_records()
    fieldnames, rating_rows = read_tsv(PUBLIC_RATINGS)
    _, target_rows = read_tsv(PUBLIC_TARGETS)
    assert fieldnames == RATING_HEADER
    assert [row["name"] for row in rating_rows] == sorted(source_rows)

    grouped = defaultdict(list)
    for row in target_rows:
        grouped[row["name"]].append(row)
    ratings = {row["name"]: row for row in rating_rows}
    for rating in rating_rows:
        details = grouped[rating["name"]]
        expected = {
            "sizes": sorted({row["size"] for row in details}),
            "families": sorted({row["family"] for row in details}),
            "fin_states": sorted({row["fin_state"] for row in details}),
            "fish_digits": sorted({row["digit"] for row in details}, key=int),
            "endo_fin_digits": sorted(
                {row["digit"] for row in details if row["endo_fins"] != "-"},
                key=int,
            ),
            "cannibalistic_digits": sorted(
                {row["digit"] for row in details if row["cannibalistic"] == "true"},
                key=int,
            ),
            "elimination_targets": [
                f'{row["digit"]}:{row["target"]}' for row in details
            ],
        }
        for field, values in expected.items():
            assert rating[field] == joined(values)
        assert rating["tier"] == ("advanced" if details else "basic")

    def without_name(row):
        return {key: value for key, value in row.items() if key != "name"}

    assert without_name(ratings["layout-029"]) == without_name(ratings["layout-032"])
    assert [without_name(row) for row in grouped["layout-029"]] == [
        without_name(row) for row in grouped["layout-032"]
    ]


def test_summary_reconciles_to_ratings():
    """Every JSON count and record list is independently derived from the ratings TSV."""
    _, rating_rows = read_tsv(PUBLIC_RATINGS)
    summary = json.loads(PUBLIC_SUMMARY.read_text(encoding="utf-8"))
    size_names = ("JELLYFISH", "SWORDFISH", "X_WING")
    family_names = ("BASIC", "FRANKEN", "MUTANT")
    fin_states = ("FINNED", "SASHIMI", "UNFINNED")

    expected = {
        "input_file": PUBLIC_INPUT.name,
        "record_count": len(rating_rows),
        "advanced_count": sum(row["tier"] == "advanced" for row in rating_rows),
        "basic_count": sum(row["tier"] == "basic" for row in rating_rows),
        "size_counts": {
            name: sum(name in split_field(row["sizes"]) for row in rating_rows)
            for name in size_names
        },
        "family_counts": {
            name: sum(name in split_field(row["families"]) for row in rating_rows)
            for name in family_names
        },
        "fin_state_counts": {
            name: sum(name in split_field(row["fin_states"]) for row in rating_rows)
            for name in fin_states
        },
        "fish_digit_counts": {
            str(digit): sum(
                str(digit) in split_field(row["fish_digits"]) for row in rating_rows
            )
            for digit in range(1, 10)
        },
        "endo_fin_record_count": sum(
            row["endo_fin_digits"] != "-" for row in rating_rows
        ),
        "cannibalistic_record_count": sum(
            row["cannibalistic_digits"] != "-" for row in rating_rows
        ),
        "records_with_multiple_families": [
            row["name"]
            for row in rating_rows
            if len(split_field(row["families"])) > 1
        ],
        "records_with_multiple_sizes": [
            row["name"]
            for row in rating_rows
            if len(split_field(row["sizes"])) > 1
        ],
        "total_elimination_targets": sum(
            len(split_field(row["elimination_targets"])) for row in rating_rows
        ),
    }
    assert summary == expected
    assert list(summary) == list(expected)
