"""Behavioral verifier for the deterministic archive link-plan utility."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable


APP = Path(os.environ.get("APP_ROOT", "/app"))
BINARY = Path(os.environ.get("ARCPLAN_BINARY", str(APP / "arcplan")))

AliasRow = tuple[str, str]
ObjectRow = tuple[str, str, int, str]
SymbolRow = tuple[str, str, str, str, int]


def write_case(
    root: Path,
    objects: list[ObjectRow],
    symbols: list[SymbolRow],
    commands: list[str],
    aliases: list[AliasRow] | None = None,
) -> tuple[Path, Path]:
    """Write one verifier-owned input case and return its input and output paths."""
    input_dir = root / "case"
    input_dir.mkdir(parents=True)
    with (input_dir / "aliases.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["alias", "target"])
        writer.writerows(aliases or [])
    with (input_dir / "objects.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["unit", "archive", "order", "comdat"])
        writer.writerows(objects)
    with (input_dir / "symbols.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["unit", "symbol", "kind", "binding", "size"])
        writer.writerows(symbols)
    (input_dir / "command.txt").write_text("\n".join(commands) + "\n", encoding="utf-8")
    return input_dir, root / "report.json"


def read_visible_case() -> tuple[list[AliasRow], list[ObjectRow], list[SymbolRow], list[str]]:
    """Load the shipped example while deriving its answer independently."""
    aliases: list[AliasRow] = []
    with (APP / "linkcase" / "aliases.tsv").open(encoding="utf-8", newline="") as handle:
        for row in list(csv.reader(handle, delimiter="\t"))[1:]:
            aliases.append((row[0], row[1]))
    objects: list[ObjectRow] = []
    with (APP / "linkcase" / "objects.tsv").open(encoding="utf-8", newline="") as handle:
        for row in list(csv.reader(handle, delimiter="\t"))[1:]:
            objects.append((row[0], row[1], int(row[2]), row[3]))
    symbols: list[SymbolRow] = []
    with (APP / "linkcase" / "symbols.tsv").open(encoding="utf-8", newline="") as handle:
        for row in list(csv.reader(handle, delimiter="\t"))[1:]:
            symbols.append((row[0], row[1], row[2], row[3], int(row[4])))
    commands = [
        line.strip()
        for line in (APP / "linkcase" / "command.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return aliases, objects, symbols, commands


def canonicalizer(aliases: list[AliasRow]) -> Callable[[str], str]:
    """Build an independent transitive alias resolver for valid verifier cases."""
    direct = dict(aliases)
    cache: dict[str, str] = {}

    def resolve(name: str) -> str:
        if name in cache:
            return cache[name]
        path: list[str] = []
        current = name
        while current in direct:
            if current in path:
                raise AssertionError("verifier generated an alias cycle")
            path.append(current)
            current = direct[current]
        for item in path:
            cache[item] = current
        cache.setdefault(name, current)
        return current

    return resolve


def report_digest(report: dict[str, Any]) -> str:
    """Compute the exact public transcript digest without using participant code."""
    lines = [f"version\t{report['version']}\n", f"status\t{report['status']}\n"]
    lines.extend(f"selected\t{unit}\n" for unit in report["selected_units"])
    lines.extend(
        f"extracted\t{item['archive']}\t{item['unit']}\n"
        for item in report["extracted_members"]
    )
    lines.extend(
        f"discarded\t{item['unit']}\t{item['reason']}\n"
        for item in report["discarded_units"]
    )
    lines.extend(
        f"symbol\t{item['name']}\t{item['provider']}\t{item['binding']}\t{item['size']}\n"
        for item in report["symbols"]
    )
    lines.extend(f"unresolved\t{name}\n" for name in report["unresolved"])
    lines.extend(
        f"error\t{item['kind']}\t{item['symbol']}\t{item['first']}\t{item['second']}\n"
        for item in report["errors"]
    )
    return "sha256:" + hashlib.sha256("".join(lines).encode()).hexdigest()


def reference_link(
    objects: list[ObjectRow],
    symbols: list[SymbolRow],
    commands: list[str],
    aliases: list[AliasRow] | None = None,
) -> dict[str, Any]:
    """Derive alias, extraction, resolution, and digest semantics from first principles."""
    resolve = canonicalizer(aliases or [])
    object_map: dict[str, dict[str, Any]] = {}
    archives: dict[str, list[dict[str, Any]]] = {}
    for unit, archive, order, comdat in objects:
        obj = {
            "unit": unit,
            "archive": archive,
            "order": order,
            "comdat": comdat,
            "defs": [],
            "strong_refs": [],
            "weak_refs": [],
        }
        object_map[unit] = obj
        if archive != "-":
            archives.setdefault(archive, []).append(obj)
    for members in archives.values():
        members.sort(key=lambda item: (item["order"], item["unit"]))
    for unit, raw_symbol, kind, binding, size in symbols:
        symbol = resolve(raw_symbol)
        if kind == "DEF":
            object_map[unit]["defs"].append((symbol, binding, size))
        elif kind == "REF":
            object_map[unit]["strong_refs"].append(symbol)
        else:
            object_map[unit]["weak_refs"].append(symbol)
    for obj in object_map.values():
        obj["defs"].sort(key=lambda item: item[0])
        obj["strong_refs"].sort()
        obj["weak_refs"].sort()

    selected: list[str] = []
    extracted: list[dict[str, str]] = []
    discarded: list[dict[str, str]] = []
    providers: dict[str, dict[str, Any]] = {}
    unresolved: set[str] = set()
    errors: list[dict[str, str]] = []
    comdat_owner: dict[str, str] = {}
    extracted_units: set[str] = set()
    ranks = {"WEAK": 1, "COMMON": 2, "STRONG": 3}

    def add_need(symbol: str) -> None:
        if symbol not in providers:
            unresolved.add(symbol)

    def accept(obj: dict[str, Any], from_archive: bool) -> None:
        if from_archive:
            extracted.append({"archive": obj["archive"], "unit": obj["unit"]})
        group = obj["comdat"]
        if group != "-" and group in comdat_owner:
            discarded.append({"unit": obj["unit"], "reason": f"comdat:{group}"})
            return
        if group != "-":
            comdat_owner[group] = obj["unit"]
        selected.append(obj["unit"])
        for symbol, binding, size in obj["defs"]:
            candidate = {
                "name": symbol,
                "provider": obj["unit"],
                "binding": binding,
                "size": size,
            }
            current = providers.get(symbol)
            if current is None:
                providers[symbol] = candidate
            elif ranks[binding] > ranks[current["binding"]]:
                providers[symbol] = candidate
            elif ranks[binding] == ranks[current["binding"]]:
                if binding == "STRONG":
                    errors.append(
                        {
                            "kind": "duplicate_strong",
                            "symbol": symbol,
                            "first": current["provider"],
                            "second": obj["unit"],
                        }
                    )
                elif binding == "COMMON" and size > current["size"]:
                    providers[symbol] = candidate
            unresolved.discard(symbol)
        for symbol in obj["strong_refs"]:
            add_need(symbol)

    def scan(archive: str, whole: bool) -> int:
        count = 0
        for obj in archives[archive]:
            if obj["unit"] in extracted_units:
                continue
            needed = any(symbol in unresolved for symbol, _, _ in obj["defs"])
            if whole or needed:
                extracted_units.add(obj["unit"])
                accept(obj, True)
                count += 1
        return count

    parsed: list[tuple[str, str]] = []
    for line in commands:
        parts = line.split()
        if parts:
            parsed.append((parts[0], parts[1] if len(parts) == 2 else ""))

    index = 0
    while index < len(parsed):
        kind, arg = parsed[index]
        if kind == "OBJ":
            accept(object_map[arg], False)
        elif kind == "ARC":
            scan(arg, False)
        elif kind == "NEED":
            add_need(resolve(arg))
        elif kind == "WHOLE_BEGIN":
            index += 1
            while parsed[index][0] != "WHOLE_END":
                scan(parsed[index][1], True)
                index += 1
        elif kind == "GROUP_BEGIN":
            group: list[tuple[str, str]] = []
            index += 1
            while parsed[index][0] != "GROUP_END":
                group.append(parsed[index])
                index += 1
            for item_kind, item_arg in group:
                if item_kind == "OBJ":
                    accept(object_map[item_arg], False)
                elif item_kind == "ARC":
                    scan(item_arg, False)
                else:
                    add_need(resolve(item_arg))
            while True:
                pulled = sum(
                    scan(item_arg, False)
                    for item_kind, item_arg in group
                    if item_kind == "ARC"
                )
                if pulled == 0:
                    break
        index += 1

    errors.sort(key=lambda item: (item["symbol"], item["first"], item["second"]))
    report: dict[str, Any] = {
        "version": 2,
        "status": "error" if unresolved or errors else "ok",
        "selected_units": selected,
        "extracted_members": extracted,
        "discarded_units": discarded,
        "symbols": [providers[name] for name in sorted(providers)],
        "unresolved": sorted(unresolved),
        "errors": errors,
    }
    report["plan_sha256"] = report_digest(report)
    return report


def assert_schema(report: dict[str, Any]) -> None:
    """Require the exact public JSON keys, nested shapes, enums, and digest form."""
    assert set(report) == {
        "version",
        "status",
        "selected_units",
        "extracted_members",
        "discarded_units",
        "symbols",
        "unresolved",
        "errors",
        "plan_sha256",
    }
    assert type(report["version"]) is int and report["version"] == 2
    assert type(report["status"]) is str and report["status"] in {"ok", "error"}
    assert type(report["selected_units"]) is list
    assert all(type(item) is str for item in report["selected_units"])
    assert type(report["extracted_members"]) is list
    assert all(
        type(item) is dict
        and set(item) == {"archive", "unit"}
        and type(item["archive"]) is str
        and type(item["unit"]) is str
        for item in report["extracted_members"]
    )
    assert type(report["discarded_units"]) is list
    assert all(
        type(item) is dict
        and set(item) == {"unit", "reason"}
        and type(item["unit"]) is str
        and type(item["reason"]) is str
        for item in report["discarded_units"]
    )
    assert type(report["symbols"]) is list
    assert all(
        type(item) is dict
        and set(item) == {"name", "provider", "binding", "size"}
        and type(item["name"]) is str
        and type(item["provider"]) is str
        and type(item["binding"]) is str
        and item["binding"] in {"STRONG", "COMMON", "WEAK"}
        and type(item["size"]) is int
        for item in report["symbols"]
    )
    assert type(report["unresolved"]) is list
    assert all(type(item) is str for item in report["unresolved"])
    assert type(report["errors"]) is list
    assert all(
        type(item) is dict
        and set(item) == {"kind", "symbol", "first", "second"}
        and item["kind"] == "duplicate_strong"
        and all(type(item[key]) is str for key in item)
        for item in report["errors"]
    )
    assert type(report["plan_sha256"]) is str
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", report["plan_sha256"])
    assert report["plan_sha256"] == report_digest(report)


def run_tool(input_dir: Path, output: Path) -> subprocess.CompletedProcess[str]:
    """Run the rebuilt product only through its documented public CLI."""
    return subprocess.run(
        [str(BINARY), str(input_dir), str(output)],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )


def assert_case(
    root: Path,
    objects: list[ObjectRow],
    symbols: list[SymbolRow],
    commands: list[str],
    aliases: list[AliasRow] | None = None,
) -> dict[str, Any]:
    """Run a valid case and compare every report value with the reference model."""
    input_dir, output = write_case(root, objects, symbols, commands, aliases)
    expected = reference_link(objects, symbols, commands, aliases)
    result = run_tool(input_dir, output)
    expected_code = 0 if expected["status"] == "ok" else 1
    assert result.returncode == expected_code, result.stderr
    actual = json.loads(output.read_text(encoding="utf-8"))
    assert_schema(actual)
    assert actual == expected
    return actual


def test_visible_case_couples_alias_need_group_weakref_whole_and_comdat(tmp_path: Path) -> None:
    """The shipped case must exercise every major semantic layer and its final digest together."""
    aliases, objects, symbols, commands = read_visible_case()
    report = assert_case(tmp_path, objects, symbols, commands, aliases)
    assert report["status"] == "ok"
    assert report["selected_units"] == ["main", "a_alpha", "b_beta", "a_gamma", "extra_weak"]
    assert [item["unit"] for item in report["extracted_members"]] == [
        "a_alpha",
        "b_beta",
        "a_gamma",
        "extra_weak",
        "extra_strong",
    ]
    assert {item["name"] for item in report["symbols"]} == {"alpha", "beta", "bonus", "gamma"}
    assert "optional" not in {item["name"] for item in report["symbols"]}


def test_normal_archive_is_not_rescanned(tmp_path: Path) -> None:
    """A member skipped before a later member adds its need stays unextracted outside a group."""
    objects = [("main", "-", 0, "-"), ("beta_obj", "lib", 0, "-"), ("alpha_obj", "lib", 1, "-")]
    symbols = [
        ("main", "alpha", "REF", "-", 0),
        ("beta_obj", "beta", "DEF", "STRONG", 0),
        ("alpha_obj", "alpha", "DEF", "STRONG", 0),
        ("alpha_obj", "beta", "REF", "-", 0),
    ]
    report = assert_case(tmp_path, objects, symbols, ["OBJ main", "ARC lib"])
    assert report["unresolved"] == ["beta"]
    assert [item["unit"] for item in report["extracted_members"]] == ["alpha_obj"]


def test_group_revisits_earlier_members_after_late_need(tmp_path: Path) -> None:
    """A NEED after an archive scan must be satisfied by the group's fixed-point rescan."""
    aliases = [("public", "late")]
    objects = [("main", "-", 0, "-"), ("late_obj", "lib", 0, "-")]
    symbols = [("late_obj", "late", "DEF", "STRONG", 0)]
    report = assert_case(
        tmp_path,
        objects,
        symbols,
        ["OBJ main", "GROUP_BEGIN", "ARC lib", "NEED public", "GROUP_END"],
        aliases,
    )
    assert report["selected_units"] == ["main", "late_obj"]
    assert report["unresolved"] == []


def test_group_fixed_point_crosses_archives_through_aliases(tmp_path: Path) -> None:
    """Canonical references can propagate across later archives and back to an earlier archive."""
    aliases = [("entry", "alpha"), ("b_api", "beta"), ("g_api", "gamma")]
    objects = [
        ("main", "-", 0, "-"),
        ("gamma_obj", "libA", 0, "-"),
        ("alpha_obj", "libA", 1, "-"),
        ("beta_obj", "libB", 0, "-"),
    ]
    symbols = [
        ("main", "entry", "REF", "-", 0),
        ("gamma_obj", "gamma", "DEF", "STRONG", 0),
        ("alpha_obj", "alpha", "DEF", "STRONG", 0),
        ("alpha_obj", "b_api", "REF", "-", 0),
        ("beta_obj", "beta", "DEF", "STRONG", 0),
        ("beta_obj", "g_api", "REF", "-", 0),
    ]
    report = assert_case(
        tmp_path,
        objects,
        symbols,
        ["OBJ main", "GROUP_BEGIN", "ARC libA", "ARC libB", "GROUP_END"],
        aliases,
    )
    assert [item["unit"] for item in report["extracted_members"]] == ["alpha_obj", "beta_obj", "gamma_obj"]


def test_whole_archive_pulls_unneeded_members_and_comdat_loser(tmp_path: Path) -> None:
    """Whole-archive extracts every member while a later COMDAT unit is reported but not accepted."""
    objects = [
        ("main", "-", 0, "-"),
        ("first", "extras", 0, "once"),
        ("loser", "extras", 1, "once"),
        ("plain", "extras", 2, "-"),
    ]
    symbols = [
        ("first", "x", "DEF", "WEAK", 0),
        ("loser", "x", "DEF", "STRONG", 0),
        ("loser", "missing", "REF", "-", 0),
        ("plain", "y", "DEF", "STRONG", 0),
    ]
    report = assert_case(
        tmp_path,
        objects,
        symbols,
        ["OBJ main", "WHOLE_BEGIN", "ARC extras", "WHOLE_END"],
    )
    assert report["selected_units"] == ["main", "first", "plain"]
    assert report["discarded_units"] == [{"unit": "loser", "reason": "comdat:once"}]
    assert report["unresolved"] == []


def test_weak_reference_does_not_extract_until_need_promotes_symbol(tmp_path: Path) -> None:
    """A weak reference is inert, while a later explicit NEED for the alias pulls its provider."""
    aliases = [("optional_api", "optional")]
    objects = [
        ("main", "-", 0, "-"),
        ("optional_obj", "lib", 0, "-"),
        ("required_obj", "lib", 1, "-"),
    ]
    symbols = [
        ("main", "optional_api", "WEAK_REF", "-", 0),
        ("main", "required", "REF", "-", 0),
        ("optional_obj", "optional", "DEF", "STRONG", 0),
        ("required_obj", "required", "DEF", "STRONG", 0),
    ]
    weak_only = assert_case(tmp_path / "weak", objects, symbols, ["OBJ main", "ARC lib"], aliases)
    promoted = assert_case(
        tmp_path / "promoted",
        objects,
        symbols,
        ["OBJ main", "NEED optional_api", "ARC lib"],
        aliases,
    )
    assert [item["unit"] for item in weak_only["extracted_members"]] == ["required_obj"]
    assert [item["unit"] for item in promoted["extracted_members"]] == ["optional_obj", "required_obj"]
    assert weak_only["plan_sha256"] != promoted["plan_sha256"]


def test_transitive_aliases_canonicalize_extraction_errors_and_report_names(tmp_path: Path) -> None:
    """Alias chains must affect archive needs, duplicate-strong detection, ordering, and digest names."""
    aliases = [("public_api", "middle_api"), ("middle_api", "impl")]
    objects = [("main", "-", 0, "-"), ("first", "lib", 0, "-"), ("second", "-", 0, "-")]
    symbols = [
        ("main", "public_api", "REF", "-", 0),
        ("first", "middle_api", "DEF", "STRONG", 0),
        ("second", "impl", "DEF", "STRONG", 0),
    ]
    report = assert_case(tmp_path, objects, symbols, ["OBJ main", "ARC lib", "OBJ second"], aliases)
    assert report["symbols"] == [{"name": "impl", "provider": "first", "binding": "STRONG", "size": 0}]
    assert report["errors"] == [
        {"kind": "duplicate_strong", "symbol": "impl", "first": "first", "second": "second"}
    ]


def test_symbol_precedence_and_stable_equal_ties(tmp_path: Path) -> None:
    """Strong, common-size, and weak tie rules remain stable after canonicalization."""
    aliases = [("x_api", "x")]
    objects = [(name, "-", 0, "-") for name in ["weak1", "common4", "common9", "common9tie", "strong", "weak2"]]
    symbols = [
        ("weak1", "x_api", "DEF", "WEAK", 0),
        ("common4", "x", "DEF", "COMMON", 4),
        ("common9", "x", "DEF", "COMMON", 9),
        ("strong", "x", "DEF", "STRONG", 0),
        ("common4", "y", "DEF", "COMMON", 4),
        ("common9", "y", "DEF", "COMMON", 9),
        ("common9tie", "y", "DEF", "COMMON", 9),
        ("weak1", "z", "DEF", "WEAK", 0),
        ("weak2", "z", "DEF", "WEAK", 0),
    ]
    report = assert_case(tmp_path, objects, symbols, [f"OBJ {name}" for name, _, _, _ in objects], aliases)
    providers = {item["name"]: item for item in report["symbols"]}
    assert providers["x"]["provider"] == "strong"
    assert providers["y"] == {"name": "y", "provider": "common9", "binding": "COMMON", "size": 9}
    assert providers["z"]["provider"] == "weak1"


def test_duplicate_strong_is_a_sorted_semantic_link_error(tmp_path: Path) -> None:
    """Later strong providers keep the first provider and emit bytewise-sorted semantic errors."""
    objects = [("main", "-", 0, "-"), ("first", "-", 0, "-"), ("second", "-", 0, "-")]
    symbols = [
        ("main", "zeta", "REF", "-", 0),
        ("main", "alpha", "REF", "-", 0),
        ("first", "zeta", "DEF", "STRONG", 0),
        ("first", "alpha", "DEF", "STRONG", 0),
        ("second", "zeta", "DEF", "STRONG", 0),
        ("second", "alpha", "DEF", "STRONG", 0),
    ]
    report = assert_case(tmp_path, objects, symbols, ["OBJ main", "OBJ first", "OBJ second"])
    assert report["status"] == "error"
    assert [item["symbol"] for item in report["errors"]] == ["alpha", "zeta"]


def test_unresolved_needs_are_canonical_sorted_and_reported(tmp_path: Path) -> None:
    """Strong references and NEED directives share one canonical bytewise-sorted unresolved set."""
    aliases = [("zed_api", "zeta"), ("a_api", "alpha")]
    objects = [("main", "-", 0, "-")]
    symbols = [("main", "zed_api", "REF", "-", 0), ("main", "weak", "WEAK_REF", "-", 0)]
    report = assert_case(tmp_path, objects, symbols, ["OBJ main", "NEED a_api"], aliases)
    assert report["status"] == "error"
    assert report["unresolved"] == ["alpha", "zeta"]


def test_comdat_loser_contributes_no_definition_or_reference(tmp_path: Path) -> None:
    """A pulled COMDAT loser cannot replace a provider or introduce either kind of reference."""
    objects = [("main", "-", 0, "-"), ("owner", "lib", 0, "pick"), ("loser", "lib", 1, "pick")]
    symbols = [
        ("main", "x", "REF", "-", 0),
        ("owner", "x", "DEF", "WEAK", 0),
        ("loser", "x", "DEF", "STRONG", 0),
        ("loser", "ghost", "REF", "-", 0),
        ("loser", "other", "WEAK_REF", "-", 0),
    ]
    report = assert_case(tmp_path, objects, symbols, ["OBJ main", "WHOLE_BEGIN", "ARC lib", "WHOLE_END"])
    assert report["status"] == "ok"
    assert report["symbols"] == [{"name": "x", "provider": "owner", "binding": "WEAK", "size": 0}]


def test_symbol_and_alias_row_order_do_not_change_report_or_digest(tmp_path: Path) -> None:
    """Physical table row order is irrelevant after semantic alias normalization."""
    aliases = [("b_api", "b"), ("a_api", "a")]
    objects = [("main", "-", 0, "-"), ("provider", "-", 0, "-")]
    symbols = [
        ("main", "b_api", "REF", "-", 0),
        ("provider", "b", "DEF", "STRONG", 0),
        ("provider", "a_api", "DEF", "WEAK", 0),
    ]
    commands = ["", "OBJ main", "", "OBJ provider", ""]
    first = assert_case(tmp_path / "first", objects, symbols, commands, aliases)
    second = assert_case(tmp_path / "second", objects, list(reversed(symbols)), commands, list(reversed(aliases)))
    assert first == second


def test_plan_digest_binds_ordered_semantic_report(tmp_path: Path) -> None:
    """Changing acceptance order must change the independently recomputed canonical transcript digest."""
    objects = [("a", "-", 0, "-"), ("b", "-", 0, "-")]
    symbols = [("a", "a_sym", "DEF", "WEAK", 0), ("b", "b_sym", "DEF", "WEAK", 0)]
    first = assert_case(tmp_path / "first", objects, symbols, ["OBJ a", "OBJ b"])
    second = assert_case(tmp_path / "second", objects, symbols, ["OBJ b", "OBJ a"])
    assert first["symbols"] == second["symbols"]
    assert first["selected_units"] != second["selected_units"]
    assert first["plan_sha256"] != second["plan_sha256"]


def test_repeated_valid_execution_is_byte_deterministic(tmp_path: Path) -> None:
    """Repeated execution over unchanged input rewrites byte-identical JSON and digest output."""
    objects = [("main", "-", 0, "-"), ("member", "lib", 0, "-")]
    symbols = [("main", "api", "REF", "-", 0), ("member", "impl", "DEF", "STRONG", 0)]
    aliases = [("api", "impl")]
    input_dir, output = write_case(tmp_path, objects, symbols, ["OBJ main", "ARC lib"], aliases)
    first = run_tool(input_dir, output)
    assert first.returncode == 0, first.stderr
    first_bytes = output.read_bytes()
    second = run_tool(input_dir, output)
    assert second.returncode == 0, second.stderr
    assert output.read_bytes() == first_bytes
    assert json.loads(first_bytes) == reference_link(objects, symbols, ["OBJ main", "ARC lib"], aliases)


def test_invalid_header_removes_stale_output(tmp_path: Path) -> None:
    """Malformed input is rejected with exit two, the stderr prefix, and no stale report."""
    input_dir = tmp_path / "bad"
    input_dir.mkdir()
    (input_dir / "aliases.tsv").write_text("alias\ttarget\n", encoding="utf-8")
    (input_dir / "objects.tsv").write_text("wrong\theader\n", encoding="utf-8")
    (input_dir / "symbols.tsv").write_text("unit\tsymbol\tkind\tbinding\tsize\n", encoding="utf-8")
    (input_dir / "command.txt").write_text("OBJ main\n", encoding="utf-8")
    output = tmp_path / "report.json"
    output.write_text("stale", encoding="utf-8")
    result = run_tool(input_dir, output)
    assert result.returncode == 2
    assert result.stderr.startswith("arcplan: ")
    assert not output.exists()


def test_invalid_cli_and_block_structure_use_exit_two(tmp_path: Path) -> None:
    """CLI arity and overlapping command blocks are malformed-input failures, not link reports."""
    cli = subprocess.run([str(BINARY)], text=True, capture_output=True, check=False, timeout=10)
    assert cli.returncode == 2
    assert cli.stderr.startswith("arcplan: ")

    stale = tmp_path / "stale.json"
    stale.write_text("old", encoding="utf-8")
    extra = subprocess.run(
        [str(BINARY), str(tmp_path), str(stale), "unexpected"],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert extra.returncode == 2
    assert extra.stderr.startswith("arcplan: ")
    assert not stale.exists()

    objects = [("member", "lib", 0, "-")]
    symbols = [("member", "x", "DEF", "STRONG", 0)]
    input_dir, output = write_case(
        tmp_path / "blocks",
        objects,
        symbols,
        ["GROUP_BEGIN", "WHOLE_BEGIN", "ARC lib", "WHOLE_END", "GROUP_END"],
    )
    result = run_tool(input_dir, output)
    assert result.returncode == 2
    assert result.stderr.startswith("arcplan: ")
    assert not output.exists()


def test_table_alias_and_command_validation_rejects_declared_malformed_forms(tmp_path: Path) -> None:
    """All documented table, alias-graph, canonical-collision, and command constraints exit two."""
    base_objects: list[ObjectRow] = [("main", "-", 0, "-"), ("member", "lib", 0, "-")]
    base_symbols: list[SymbolRow] = [
        ("main", "x", "REF", "-", 0),
        ("member", "x", "DEF", "STRONG", 0),
    ]
    variants = [
        ("aliases-wrong-header", "aliases.tsv", "from\tto\n"),
        ("alias-self", "aliases.tsv", "alias\ttarget\nx\tx\n"),
        ("duplicate-alias", "aliases.tsv", "alias\ttarget\na\tx\na\ty\n"),
        ("alias-cycle", "aliases.tsv", "alias\ttarget\na\tb\nb\ta\n"),
        ("invalid-alias-identifier", "aliases.tsv", "alias\ttarget\nbad/name\tx\n"),
        ("duplicate-unit", "objects.tsv", "unit\tarchive\torder\tcomdat\nmain\t-\t0\t-\nmain\tlib\t0\t-\n"),
        ("duplicate-member-order", "objects.tsv", "unit\tarchive\torder\tcomdat\nmain\t-\t0\t-\na\tlib\t0\t-\nb\tlib\t0\t-\n"),
        ("negative-member-order", "objects.tsv", "unit\tarchive\torder\tcomdat\nmain\t-\t0\t-\nmember\tlib\t-1\t-\n"),
        ("loose-nonzero-order", "objects.tsv", "unit\tarchive\torder\tcomdat\nmain\t-\t1\t-\nmember\tlib\t0\t-\n"),
        ("invalid-unit-identifier", "objects.tsv", "unit\tarchive\torder\tcomdat\nbad/name\t-\t0\t-\nmember\tlib\t0\t-\n"),
        ("invalid-archive-identifier", "objects.tsv", "unit\tarchive\torder\tcomdat\nmain\t-\t0\t-\nmember\tbad/name\t0\t-\n"),
        ("invalid-comdat-identifier", "objects.tsv", "unit\tarchive\torder\tcomdat\nmain\t-\t0\t-\nmember\tlib\t0\tbad/name\n"),
        ("empty-object-table", "objects.tsv", "unit\tarchive\torder\tcomdat\n"),
        ("symbols-wrong-header", "symbols.tsv", "unit\tsymbol\tkind\tbinding\n"),
        ("unknown-symbol-unit", "symbols.tsv", "unit\tsymbol\tkind\tbinding\tsize\nghost\tx\tREF\t-\t0\n"),
        ("invalid-symbol-identifier", "symbols.tsv", "unit\tsymbol\tkind\tbinding\tsize\nmember\tbad/name\tDEF\tSTRONG\t0\n"),
        ("invalid-symbol-kind", "symbols.tsv", "unit\tsymbol\tkind\tbinding\tsize\nmember\tx\tOTHER\tSTRONG\t0\n"),
        ("invalid-definition-binding", "symbols.tsv", "unit\tsymbol\tkind\tbinding\tsize\nmember\tx\tDEF\tGLOBAL\t0\n"),
        ("invalid-reference-shape", "symbols.tsv", "unit\tsymbol\tkind\tbinding\tsize\nmain\tx\tREF\tWEAK\t1\n"),
        ("invalid-weak-reference-shape", "symbols.tsv", "unit\tsymbol\tkind\tbinding\tsize\nmain\tx\tWEAK_REF\t-\t1\n"),
        ("invalid-strong-size", "symbols.tsv", "unit\tsymbol\tkind\tbinding\tsize\nmember\tx\tDEF\tSTRONG\t1\n"),
        ("negative-symbol-size", "symbols.tsv", "unit\tsymbol\tkind\tbinding\tsize\nmember\tx\tDEF\tCOMMON\t-1\n"),
        ("wrong-symbol-field-count", "symbols.tsv", "unit\tsymbol\tkind\tbinding\tsize\nmember\tx\tDEF\tSTRONG\n"),
        ("invalid-common-size", "symbols.tsv", "unit\tsymbol\tkind\tbinding\tsize\nmember\tx\tDEF\tCOMMON\t0\n"),
        ("duplicate-unit-symbol", "symbols.tsv", "unit\tsymbol\tkind\tbinding\tsize\nmember\tx\tDEF\tWEAK\t0\nmember\tx\tREF\t-\t0\n"),
        ("canonical-unit-symbol-collision", "symbols.tsv", "unit\tsymbol\tkind\tbinding\tsize\nmain\ta\tREF\t-\t0\nmain\tb\tWEAK_REF\t-\t0\nmember\tx\tDEF\tSTRONG\t0\n"),
        ("member-used-as-obj", "command.txt", "OBJ member\n"),
        ("duplicate-object", "command.txt", "OBJ main\nOBJ main\n"),
        ("duplicate-archive", "command.txt", "ARC lib\nARC lib\n"),
        ("unknown-archive", "command.txt", "ARC missing\n"),
        ("unknown-directive", "command.txt", "INCLUDE lib\n"),
        ("malformed-archive-directive", "command.txt", "ARC lib extra\n"),
        ("invalid-need-identifier", "command.txt", "NEED bad/name\n"),
        ("duplicate-canonical-need", "command.txt", "NEED a\nNEED b\n"),
        ("need-inside-whole", "command.txt", "WHOLE_BEGIN\nNEED x\nWHOLE_END\n"),
        ("object-inside-whole", "command.txt", "WHOLE_BEGIN\nOBJ main\nWHOLE_END\n"),
        ("nested-group", "command.txt", "GROUP_BEGIN\nGROUP_BEGIN\nGROUP_END\nGROUP_END\n"),
        ("unclosed-group", "command.txt", "GROUP_BEGIN\nARC lib\n"),
        ("unclosed-whole", "command.txt", "WHOLE_BEGIN\nARC lib\n"),
        ("orphan-group-end", "command.txt", "GROUP_END\n"),
        ("empty-command-file", "command.txt", "\n\n"),
    ]

    for name, filename, replacement in variants:
        case_root = tmp_path / name
        aliases = [("a", "x"), ("b", "x")] if "canonical" in name else []
        input_dir, output = write_case(case_root, base_objects, base_symbols, ["OBJ main", "ARC lib"], aliases)
        (input_dir / filename).write_text(replacement, encoding="utf-8")
        output.write_text("stale", encoding="utf-8")
        result = run_tool(input_dir, output)
        assert result.returncode == 2, name
        assert result.stderr.startswith("arcplan: "), name
        assert not output.exists(), name


def test_dynamic_variant_defeats_hardcoded_solution(tmp_path: Path) -> None:
    """Two fresh alias-driven plans must produce fresh names, correct events, and distinct digests."""
    visible_aliases, visible_objects, visible_symbols, visible_commands = read_visible_case()
    visible = reference_link(visible_objects, visible_symbols, visible_commands, visible_aliases)
    dynamic_reports: list[dict[str, Any]] = []

    for index, seed in enumerate(["quartz-17", "ember-29"]):
        suffix = hashlib.sha256(seed.encode()).hexdigest()[:10]
        main = f"root_{suffix}"
        first = f"first_{suffix}"
        second = f"second_{suffix}"
        early = f"early_{suffix}"
        optional = f"optional_{suffix}"
        lib_a = f"libA_{suffix}"
        lib_b = f"libB_{suffix}"
        public = f"public_{suffix}"
        middle = f"middle_{suffix}"
        sym_a = f"needA_{suffix}"
        sym_b = f"needB_{suffix}"
        sym_c = f"needC_{suffix}"
        weak = f"weak_{suffix}"
        aliases = [(public, middle), (middle, sym_a), (f"b_api_{suffix}", sym_b), (f"c_api_{suffix}", sym_c)]
        objects = [
            (main, "-", 0, "-"),
            (early, lib_a, 0, "-"),
            (first, lib_a, 1, "-"),
            (second, lib_b, 0, "-"),
            (optional, lib_b, 1, "-"),
        ]
        symbols = [
            (main, public, "REF", "-", 0),
            (main, weak, "WEAK_REF", "-", 0),
            (early, sym_c, "DEF", "COMMON", 7 + index),
            (first, sym_a, "DEF", "WEAK", 0),
            (first, f"b_api_{suffix}", "REF", "-", 0),
            (second, sym_b, "DEF", "STRONG", 0),
            (second, f"c_api_{suffix}", "REF", "-", 0),
            (optional, weak, "DEF", "STRONG", 0),
        ]
        commands = [
            f"OBJ {main}",
            "GROUP_BEGIN",
            f"ARC {lib_a}",
            f"NEED c_api_{suffix}",
            f"ARC {lib_b}",
            "GROUP_END",
        ]
        report = assert_case(tmp_path / seed, objects, symbols, commands, aliases)
        dynamic_reports.append(report)
        assert report["status"] == "ok"
        assert main in report["selected_units"]
        assert {first, second, early}.issubset(report["selected_units"])
        assert optional not in report["selected_units"]
        assert [item["unit"] for item in report["extracted_members"]] == [first, second, early]
        assert {sym_a, sym_b, sym_c}.issubset({item["name"] for item in report["symbols"]})
        assert report["plan_sha256"] != visible["plan_sha256"]
        assert len(report["selected_units"]) != len(visible["selected_units"])

    assert dynamic_reports[0]["plan_sha256"] != dynamic_reports[1]["plan_sha256"]
