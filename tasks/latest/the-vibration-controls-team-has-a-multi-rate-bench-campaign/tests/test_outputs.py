"""Behavioral checks for exact multi-rate harmonic source recovery."""

from __future__ import annotations

import hashlib
import itertools
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest


SOURCE = Path("/app/src/harmonic_recovery.cpp")
BINARY = Path("/app/build/harmonic-recovery")
VISIBLE_LAB = Path("/app/plant_lab")
VISIBLE_OUTPUT = Path("/app/source_spectrum.json")

EXPECTED_INPUT_TREE_SHA256 = "87e4cd1bd7c8198891540e831555730c88259ea662d268c898d63c840ebd0f9c"
EXPECTED_FIELD_HASHES = {
    "selected_sources": "1c50691235b4775d960dc8b496cd3463675c2d7cf60096767ac447edc8c7c7f8",
    "folded_tracks": "216ca9b03ee939c0345e6b8aaffd7ba51f2e55459e1249ecee78a9bb22558c5b",
    "sensitivity_values": "60347db3a3f1cde9c5650ca4488cabe0ac3f06ff3c5e0c7f0b8aa3ea2a5dbb39",
    "source_contributions": "9bc8d09c847cceca94db31bbe8a8495f956c5fdaac08be9cd5283a8915aa8dc0",
    "reconstructed_bins": "4b8356866901cbe7a68b17113f88c8efbd61d1c2e046ae74f1d967c9064a030b",
    "residual_balance": "b2e545a970975e17128d5e12baca4a0500c8148d8c1e0d6b2b9c77115ec544ff",
    "recovery_certificate": "8e35dc636f8e5d786586b93fb93df07ab3a2e31f735613b799de4221b53fd679",
}

TOP_LEVEL_KEYS = set(EXPECTED_FIELD_HASHES)


def compact_hash(value) -> str:
    """Hash parsed JSON with a stable, whitespace-independent encoding."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def tree_hash(root: Path) -> str:
    """Bind relative names and bytes for every regular campaign file."""
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def frac(value) -> Fraction:
    """Parse the required reduced-fraction object."""
    assert isinstance(value, dict) and set(value) == {"n", "d"}
    assert isinstance(value["n"], str) and isinstance(value["d"], str)
    result = Fraction(int(value["n"]), int(value["d"]))
    assert result.denominator > 0
    assert str(result.numerator) == value["n"]
    assert str(result.denominator) == value["d"]
    return result


def jf(value: Fraction | int) -> dict[str, str]:
    """Encode one exact fraction in its required canonical form."""
    value = Fraction(value)
    return {"n": str(value.numerator), "d": str(value.denominator)}


def cadd(a, b):
    return a[0] + b[0], a[1] + b[1]


def cmul(a, b):
    return a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0]


def cdiv(a, b):
    scale = b[0] * b[0] + b[1] * b[1]
    assert scale
    return (
        (a[0] * b[0] + a[1] * b[1]) / scale,
        (a[1] * b[0] - a[0] * b[1]) / scale,
    )


def poly(coefficients, omega):
    value = (Fraction(0), Fraction(0))
    jw = (Fraction(0), Fraction(omega))
    for coefficient in reversed(coefficients):
        value = cadd(cmul(value, jw), (coefficient, Fraction(0)))
    return value


def path_value(path, omega):
    return cdiv(poly(path["numerator"], omega), poly(path["denominator"], omega))


def rotate(cosine, sine, quarters):
    quarters %= 4
    if quarters == 0:
        return cosine, sine
    if quarters == 1:
        return sine, -cosine
    if quarters == 2:
        return -cosine, -sine
    return -sine, cosine


def fold(omega, sample_rate):
    residue = omega % sample_rate
    if residue > sample_rate // 2:
        return sample_rate - residue, -1
    folded = residue
    if folded == 0 or (sample_rate % 2 == 0 and folded == sample_rate // 2):
        return folded, 0
    return folded, 1


def load_lab(root: Path):
    """Read a campaign into normalized dictionaries without relying on file order."""
    campaign = json.loads((root / "campaign.json").read_text())
    sources = sorted(campaign["sources"])
    probes = sorted(campaign["probes"])
    tones = []
    for path in sorted((root / "tones").glob("*.json")):
        row = json.loads(path.read_text())
        tones.append({"tone_id": row["tone_id"], "omega": row["omega"]})
    tones.sort(key=lambda row: row["tone_id"])
    paths = {}
    for file in sorted((root / "paths").glob("*.json")):
        row = json.loads(file.read_text())
        paths[(row["source_id"], row["probe_id"])] = {
            "numerator": [frac(value) for value in row["numerator"]],
            "denominator": [frac(value) for value in row["denominator"]],
        }
    captures = []
    for file in sorted((root / "captures").glob("*.json")):
        raw = json.loads(file.read_text())
        probes_rows = []
        for probe in sorted(raw["probes"], key=lambda row: row["probe_id"]):
            bins = []
            for item in sorted(probe["bins"], key=lambda row: row["bin"]):
                bins.append(
                    {
                        "bin": item["bin"],
                        "expected_cos": frac(item["expected"]["cos"]),
                        "expected_sin": frac(item["expected"]["sin"]),
                        "measured_cos": frac(item["measured"]["cos"]),
                        "measured_sin": frac(item["measured"]["sin"]),
                    }
                )
            probes_rows.append({"probe_id": probe["probe_id"], "bins": bins})
        captures.append(
            {
                "capture_id": raw["capture_id"],
                "sample_rate": raw["sample_rate"],
                "trigger_quarters": raw["trigger_quarters"],
                "probes": probes_rows,
            }
        )
    captures.sort(key=lambda row: row["capture_id"])
    return {
        "sources": sources,
        "probes": probes,
        "tones": tones,
        "paths": paths,
        "captures": captures,
        "max_active": campaign["max_active_sources"],
    }


def one_contribution(lab, tone, source, capture, probe, cosine, sine):
    """Apply phase, calibrated response, and sample folding to one source line."""
    phase = (tone["omega"] * capture["trigger_quarters"]) % 4
    rotated_cos, rotated_sin = rotate(cosine, sine, phase)
    real, imag = path_value(lab["paths"][(source, probe)], tone["omega"])
    output_cos = real * rotated_cos + imag * rotated_sin
    output_sin = real * rotated_sin - imag * rotated_cos
    bin_id, sine_sign = fold(tone["omega"], capture["sample_rate"])
    return {
        "phase": phase,
        "bin": bin_id,
        "sine_sign": sine_sign,
        "cos": output_cos,
        "sin": output_sin * sine_sign,
    }


def scalar_rows(lab):
    """Return the complete measured-minus-expected coordinate vector."""
    keys = []
    values = []
    for capture in lab["captures"]:
        for probe in capture["probes"]:
            for item in probe["bins"]:
                keys.append((capture["capture_id"], probe["probe_id"], item["bin"], "cos"))
                values.append(item["measured_cos"] - item["expected_cos"])
                keys.append((capture["capture_id"], probe["probe_id"], item["bin"], "sin"))
                values.append(item["measured_sin"] - item["expected_sin"])
    return keys, values


def candidate_items(lab):
    return [
        (tone["tone_id"], source)
        for tone in lab["tones"]
        for source in lab["sources"]
    ]


def tone_by_id(lab, tone_id):
    return next(tone for tone in lab["tones"] if tone["tone_id"] == tone_id)


def column(lab, candidate, sine_basis):
    tone = tone_by_id(lab, candidate[0])
    values = []
    source_cos, source_sin = ((0, 1) if sine_basis else (1, 0))
    for capture in lab["captures"]:
        for probe in capture["probes"]:
            part = one_contribution(
                lab,
                tone,
                candidate[1],
                capture,
                probe["probe_id"],
                Fraction(source_cos),
                Fraction(source_sin),
            )
            for item in probe["bins"]:
                if item["bin"] == part["bin"]:
                    values.extend([part["cos"], part["sin"]])
                else:
                    values.extend([Fraction(0), Fraction(0)])
    return values


def unique_fit(columns, target):
    """Return the unique exact coordinate vector, or None for no fit/non-uniqueness."""
    width = len(columns)
    if width == 0:
        return [] if all(value == 0 for value in target) else None
    matrix = [
        [columns[col][row] for col in range(width)] + [target[row]]
        for row in range(len(target))
    ]
    pivot_row = 0
    pivot_for = {}
    for col in range(width):
        pivot = next(
            (row for row in range(pivot_row, len(matrix)) if matrix[row][col]),
            None,
        )
        if pivot is None:
            continue
        matrix[pivot_row], matrix[pivot] = matrix[pivot], matrix[pivot_row]
        scale = matrix[pivot_row][col]
        matrix[pivot_row] = [value / scale for value in matrix[pivot_row]]
        for row in range(len(matrix)):
            if row == pivot_row or not matrix[row][col]:
                continue
            factor = matrix[row][col]
            matrix[row] = [
                matrix[row][j] - factor * matrix[pivot_row][j]
                for j in range(width + 1)
            ]
        pivot_for[col] = pivot_row
        pivot_row += 1
    for row in matrix:
        if all(value == 0 for value in row[:width]) and row[-1] != 0:
            return None
    if len(pivot_for) != width:
        return None
    values = [matrix[pivot_for[col]][-1] for col in range(width)]
    if any(values[index] == values[index + 1] == 0 for index in range(0, width, 2)):
        return None
    return values


def recover_small(lab):
    """Independently select the canonical support for compact generated campaigns."""
    _, target = scalar_rows(lab)
    candidates = candidate_items(lab)
    cos_columns = [column(lab, item, False) for item in candidates]
    sin_columns = [column(lab, item, True) for item in candidates]
    for size in range(lab["max_active"] + 1):
        for support_indices in itertools.combinations(range(len(candidates)), size):
            columns = []
            for index in support_indices:
                columns.extend([cos_columns[index], sin_columns[index]])
            coordinates = unique_fit(columns, target)
            if coordinates is not None:
                return [candidates[index] for index in support_indices], coordinates
    raise ValueError("no admissible recovery")


def product_from_recovery(lab, support, coordinates):
    """Derive the seven products directly from the normative equations."""
    selected_sources = []
    folded_tracks = []
    sensitivity_values = []
    source_contributions = []
    predicted = {}

    for position, candidate in enumerate(support):
        tone = tone_by_id(lab, candidate[0])
        source = candidate[1]
        cosine = coordinates[position * 2]
        sine = coordinates[position * 2 + 1]
        selected_sources.append(
            {
                "tone_id": tone["tone_id"],
                "source_id": source,
                "omega": tone["omega"],
                "cos": jf(cosine),
                "sin": jf(sine),
                "energy": jf(cosine * cosine + sine * sine),
            }
        )
        for capture in lab["captures"]:
            bin_id, sine_sign = fold(tone["omega"], capture["sample_rate"])
            folded_tracks.append(
                {
                    "tone_id": tone["tone_id"],
                    "source_id": source,
                    "capture_id": capture["capture_id"],
                    "sample_rate": capture["sample_rate"],
                    "trigger_quarters": capture["trigger_quarters"],
                    "phase_quarters": (tone["omega"] * capture["trigger_quarters"]) % 4,
                    "folded_bin": bin_id,
                    "sine_sign": sine_sign,
                }
            )
        for probe_id in lab["probes"]:
            real, imag = path_value(lab["paths"][(source, probe_id)], tone["omega"])
            sensitivity_values.append(
                {
                    "tone_id": tone["tone_id"],
                    "source_id": source,
                    "probe_id": probe_id,
                    "real": jf(real),
                    "imag": jf(imag),
                }
            )
        for capture in lab["captures"]:
            for probe in capture["probes"]:
                part = one_contribution(
                    lab, tone, source, capture, probe["probe_id"], cosine, sine
                )
                source_contributions.append(
                    {
                        "tone_id": tone["tone_id"],
                        "source_id": source,
                        "capture_id": capture["capture_id"],
                        "probe_id": probe["probe_id"],
                        "bin": part["bin"],
                        "cos": jf(part["cos"]),
                        "sin": jf(part["sin"]),
                    }
                )
                key = (capture["capture_id"], probe["probe_id"], part["bin"])
                old = predicted.get(key, (Fraction(0), Fraction(0)))
                predicted[key] = (old[0] + part["cos"], old[1] + part["sin"])

    reconstructed_bins = []
    residual_balance = []
    equation_count = 0
    for capture in lab["captures"]:
        for probe in capture["probes"]:
            for item in probe["bins"]:
                key = (capture["capture_id"], probe["probe_id"], item["bin"])
                predicted_pair = predicted.get(key, (Fraction(0), Fraction(0)))
                observed = (
                    item["measured_cos"] - item["expected_cos"],
                    item["measured_sin"] - item["expected_sin"],
                )
                reconstructed_bins.append(
                    {
                        "capture_id": key[0],
                        "probe_id": key[1],
                        "bin": key[2],
                        "cos": jf(predicted_pair[0]),
                        "sin": jf(predicted_pair[1]),
                    }
                )
                residual_balance.append(
                    {
                        "capture_id": key[0],
                        "probe_id": key[1],
                        "bin": key[2],
                        "observed": {"cos": jf(observed[0]), "sin": jf(observed[1])},
                        "predicted": {
                            "cos": jf(predicted_pair[0]),
                            "sin": jf(predicted_pair[1]),
                        },
                        "error": {
                            "cos": jf(observed[0] - predicted_pair[0]),
                            "sin": jf(observed[1] - predicted_pair[1]),
                        },
                    }
                )
                equation_count += 2
    support_key = [f"{tone_id}@{source}" for tone_id, source in support]
    return {
        "selected_sources": selected_sources,
        "folded_tracks": folded_tracks,
        "sensitivity_values": sensitivity_values,
        "source_contributions": source_contributions,
        "reconstructed_bins": reconstructed_bins,
        "residual_balance": residual_balance,
        "recovery_certificate": {
            "support_size": len(support),
            "scalar_unknowns": len(support) * 2,
            "scalar_equations": equation_count,
            "matrix_rank": len(support) * 2,
            "exact_fit": True,
            "support_key": support_key,
        },
    }


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def make_lab(root, sources, probes, tones, path_specs, captures, active, max_active):
    """Create a compact conforming campaign with exact generated measurements."""
    write_json(
        root / "campaign.json",
        {
            "format": "harmonic-source-bench/v1",
            "max_active_sources": max_active,
            "sources": sources,
            "probes": probes,
        },
    )
    write_json(
        root / "sources.json",
        {
            "sources": [
                {"source_id": source, "description": f"calibrated {source} injection"}
                for source in sources
            ]
        },
    )
    for tone_id, omega in tones:
        write_json(root / "tones" / f"{tone_id}.json", {"tone_id": tone_id, "omega": omega})
    for source in sources:
        for probe in probes:
            numerator, denominator = path_specs[(source, probe)]
            write_json(
                root / "paths" / f"{source}--{probe}.json",
                {
                    "source_id": source,
                    "probe_id": probe,
                    "numerator": [jf(value) for value in numerator],
                    "denominator": [jf(value) for value in denominator],
                },
            )
    omega_by_tone = dict(tones)
    normalized_paths = {
        key: {
            "numerator": [Fraction(value) for value in spec[0]],
            "denominator": [Fraction(value) for value in spec[1]],
        }
        for key, spec in path_specs.items()
    }
    lab_stub = {"paths": normalized_paths}
    for capture_index, (capture_id, sample_rate, trigger_quarters) in enumerate(captures):
        probe_rows = []
        for probe_index, probe in enumerate(probes):
            bins = []
            for bin_id in range(sample_rate // 2 + 1):
                expected = (
                    Fraction((capture_index + 2) * (probe_index + 1) - bin_id, 19),
                    Fraction((capture_index + 1) * (bin_id + 2) - probe_index, 23),
                )
                residual = [Fraction(0), Fraction(0)]
                for (tone_id, source), (cosine, sine) in active.items():
                    tone = {"tone_id": tone_id, "omega": omega_by_tone[tone_id]}
                    capture_stub = {
                        "sample_rate": sample_rate,
                        "trigger_quarters": trigger_quarters,
                    }
                    part = one_contribution(
                        lab_stub,
                        tone,
                        source,
                        capture_stub,
                        probe,
                        Fraction(cosine),
                        Fraction(sine),
                    )
                    if part["bin"] == bin_id:
                        residual[0] += part["cos"]
                        residual[1] += part["sin"]
                bins.append(
                    {
                        "bin": bin_id,
                        "expected": {"cos": jf(expected[0]), "sin": jf(expected[1])},
                        "measured": {
                            "cos": jf(expected[0] + residual[0]),
                            "sin": jf(expected[1] + residual[1]),
                        },
                    }
                )
            probe_rows.append({"probe_id": probe, "bins": bins})
        write_json(
            root / "captures" / f"{capture_id}.json",
            {
                "capture_id": capture_id,
                "sample_rate": sample_rate,
                "trigger_quarters": trigger_quarters,
                "probes": probe_rows,
            },
        )


def make_minimal_lab(root):
    """Create a small valid campaign used to isolate input-contract failures."""
    make_lab(
        root,
        ["shaft"],
        ["tip"],
        [("M1", 1)],
        {("shaft", "tip"): ([0, 1], [1, 1, 1])},
        [("M1", 5, 0), ("M2", 6, 1)],
        {("M1", "shaft"): (Fraction(3, 2), Fraction(-2, 5))},
        1,
    )


def invalidate_minimal_lab(root, case):
    """Apply one documented invalid-input condition to a valid compact campaign."""
    if case == "malformed_json":
        (root / "campaign.json").write_text("{")
    elif case == "trailing_json_content":
        path = root / "campaign.json"
        path.write_text(path.read_text() + "trailing")
    elif case == "duplicate_identifier":
        path = root / "campaign.json"
        value = json.loads(path.read_text())
        value["sources"] = ["shaft", "shaft"]
        write_json(path, value)
    elif case == "invalid_identifier_syntax":
        path = root / "campaign.json"
        value = json.loads(path.read_text())
        value["sources"] = ["shaft@drive"]
        write_json(path, value)
    elif case == "empty_sources":
        path = root / "campaign.json"
        value = json.loads(path.read_text())
        value["sources"] = []
        write_json(path, value)
    elif case == "unknown_identifier":
        path = next((root / "paths").glob("*.json"))
        value = json.loads(path.read_text())
        value["source_id"] = "ghost"
        write_json(path, value)
    elif case == "missing_path":
        next((root / "paths").glob("*.json")).unlink()
    elif case == "duplicate_path":
        path = next((root / "paths").glob("*.json"))
        shutil.copyfile(path, path.with_name("duplicate.json"))
    elif case == "nonpositive_tone":
        path = next((root / "tones").glob("*.json"))
        value = json.loads(path.read_text())
        value["omega"] = 0
        write_json(path, value)
    elif case == "tone_above_limit":
        path = next((root / "tones").glob("*.json"))
        value = json.loads(path.read_text())
        value["omega"] = 1000001
        write_json(path, value)
    elif case == "nonpositive_sample_rate":
        path = next((root / "captures").glob("*.json"))
        value = json.loads(path.read_text())
        value["sample_rate"] = 0
        write_json(path, value)
    elif case == "sample_rate_above_limit":
        path = next((root / "captures").glob("*.json"))
        value = json.loads(path.read_text())
        value["sample_rate"] = 1000001
        write_json(path, value)
    elif case == "out_of_range_limit":
        path = root / "campaign.json"
        value = json.loads(path.read_text())
        value["max_active_sources"] = 2
        write_json(path, value)
    elif case == "incomplete_bin_grid":
        path = next((root / "captures").glob("*.json"))
        value = json.loads(path.read_text())
        value["probes"][0]["bins"].pop()
        write_json(path, value)
    elif case == "incomplete_probe_grid":
        path = next((root / "captures").glob("*.json"))
        value = json.loads(path.read_text())
        value["probes"] = []
        write_json(path, value)
    elif case == "zero_path_denominator":
        path = next((root / "paths").glob("*.json"))
        value = json.loads(path.read_text())
        value["denominator"] = [jf(1), jf(0), jf(1)]
        write_json(path, value)
    else:
        raise AssertionError(f"unknown invalid case: {case}")


def run_product(lab: Path, output: Path, check=True):
    return subprocess.run(
        [str(BINARY), str(lab), str(output)],
        text=True,
        capture_output=True,
        check=check,
    )


@pytest.fixture(scope="session")
def visible_product():
    """Rebuild the submitted C++ source and run the published campaign once."""
    assert SOURCE.is_file(), f"missing required source: {SOURCE}"
    BINARY.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "g++",
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-pedantic",
            str(SOURCE),
            "-o",
            str(BINARY),
        ],
        check=True,
        timeout=120,
    )
    run_product(VISIBLE_LAB, VISIBLE_OUTPUT)
    return json.loads(VISIBLE_OUTPUT.read_text())


def test_required_cpp_artifacts_are_runnable(visible_product):
    """The graded artifact is a native ELF rebuilt from the required C++ source."""
    assert SOURCE.is_file()
    assert BINARY.read_bytes()[:4] == b"\x7fELF"
    assert visible_product


def test_published_campaign_tree_is_unchanged(visible_product):
    """The visible campaign remains byte-for-byte identical to the authored fixture."""
    assert tree_hash(VISIBLE_LAB) == EXPECTED_INPUT_TREE_SHA256


def test_top_level_product_shape(visible_product):
    """The destination has exactly the seven domain products and required container types."""
    assert set(visible_product) == TOP_LEVEL_KEYS
    for key in TOP_LEVEL_KEYS - {"recovery_certificate"}:
        assert isinstance(visible_product[key], list)
    assert isinstance(visible_product["recovery_certificate"], dict)


@pytest.mark.parametrize("field", sorted(EXPECTED_FIELD_HASHES))
def test_visible_field_hashes(visible_product, field):
    """Each published product matches its fully specified canonical content."""
    assert compact_hash(visible_product[field]) == EXPECTED_FIELD_HASHES[field]


def test_selected_sources_use_reduced_nonzero_coordinates(visible_product):
    """Selected rows are canonical, nonzero, and carry exact energy identities."""
    rows = visible_product["selected_sources"]
    assert [(row["tone_id"], row["source_id"]) for row in rows] == sorted(
        (row["tone_id"], row["source_id"]) for row in rows
    )
    for row in rows:
        cosine, sine, energy = frac(row["cos"]), frac(row["sin"]), frac(row["energy"])
        assert cosine or sine
        assert energy == cosine * cosine + sine * sine


def test_visible_tracks_match_multirate_rules(visible_product):
    """Every selected line has the exact trigger phase, fold, and sine orientation."""
    lab = load_lab(VISIBLE_LAB)
    expected = product_from_recovery(
        lab,
        [(row["tone_id"], row["source_id"]) for row in visible_product["selected_sources"]],
        list(
            itertools.chain.from_iterable(
                (frac(row["cos"]), frac(row["sin"]))
                for row in visible_product["selected_sources"]
            )
        ),
    )
    assert visible_product["folded_tracks"] == expected["folded_tracks"]


def test_visible_sensitivity_and_contributions(visible_product):
    """Path values and per-source capture contributions follow the exact bench equations."""
    lab = load_lab(VISIBLE_LAB)
    support = [(row["tone_id"], row["source_id"]) for row in visible_product["selected_sources"]]
    coordinates = list(
        itertools.chain.from_iterable(
            (frac(row["cos"]), frac(row["sin"]))
            for row in visible_product["selected_sources"]
        )
    )
    expected = product_from_recovery(lab, support, coordinates)
    assert visible_product["sensitivity_values"] == expected["sensitivity_values"]
    assert visible_product["source_contributions"] == expected["source_contributions"]


def test_visible_reconstruction_and_balance(visible_product):
    """Collision sums reproduce every measured-minus-expected coordinate with zero error."""
    lab = load_lab(VISIBLE_LAB)
    support = [(row["tone_id"], row["source_id"]) for row in visible_product["selected_sources"]]
    coordinates = list(
        itertools.chain.from_iterable(
            (frac(row["cos"]), frac(row["sin"]))
            for row in visible_product["selected_sources"]
        )
    )
    expected = product_from_recovery(lab, support, coordinates)
    assert visible_product["reconstructed_bins"] == expected["reconstructed_bins"]
    assert visible_product["residual_balance"] == expected["residual_balance"]
    assert all(
        frac(row["error"]["cos"]) == frac(row["error"]["sin"]) == 0
        for row in visible_product["residual_balance"]
    )


def test_visible_certificate_is_self_consistent(visible_product):
    """The certificate counts the selected support and complete scalar coordinate grid."""
    certificate = visible_product["recovery_certificate"]
    support_key = [
        f'{row["tone_id"]}@{row["source_id"]}'
        for row in visible_product["selected_sources"]
    ]
    assert certificate == {
        "support_size": len(support_key),
        "scalar_unknowns": 2 * len(support_key),
        "scalar_equations": 2 * len(visible_product["reconstructed_bins"]),
        "matrix_rank": 2 * len(support_key),
        "exact_fit": True,
        "support_key": support_key,
    }


def test_visible_rerun_is_deterministic(visible_product, tmp_path):
    """A second run emits the same parsed product regardless of destination name."""
    output = tmp_path / "repeat.json"
    run_product(VISIBLE_LAB, output)
    assert json.loads(output.read_text()) == visible_product


def test_hidden_reflected_aliases_and_phase_rotation(tmp_path, visible_product):
    """A hidden campaign separates lines that collide in one capture but not the others."""
    root = tmp_path / "alias-campaign"
    sources = ["mount", "drive"]
    probes = ["head", "base"]
    tones = [("A7", 7), ("A1", 1), ("A5", 5), ("A3", 3)]
    paths = {
        ("drive", "base"): ([0, 1], [1, 1, 1]),
        ("drive", "head"): ([1, 1], [2, 1, 1]),
        ("mount", "base"): ([1], [3, 1, 1]),
        ("mount", "head"): ([1, -1], [2, 2, 1]),
    }
    active = {
        ("A1", "drive"): (Fraction(3, 2), Fraction(1, 3)),
        ("A7", "mount"): (Fraction(-2, 5), Fraction(4, 3)),
    }
    make_lab(
        root,
        sources,
        probes,
        tones,
        paths,
        [("H1", 8, 1), ("H2", 9, -3), ("H3", 10, 9223372036854775807)],
        active,
        2,
    )
    lab = load_lab(root)
    support, coordinates = recover_small(lab)
    expected = product_from_recovery(lab, support, coordinates)
    output = tmp_path / "alias.json"
    run_product(root, output)
    assert json.loads(output.read_text()) == expected


def test_hidden_nyquist_collapse_is_not_global(tmp_path, visible_product):
    """A sine coordinate hidden at Nyquist remains recoverable from other sample rates."""
    root = tmp_path / "nyquist-campaign"
    sources = ["shaft"]
    probes = ["case", "tip"]
    tones = [("N2", 2), ("N4", 4), ("N6", 6)]
    paths = {
        ("shaft", "case"): ([0, 1], [1, 1, 1]),
        ("shaft", "tip"): ([1, 2], [3, 1, 1]),
    }
    active = {("N4", "shaft"): (Fraction(2, 3), Fraction(5, 4))}
    make_lab(root, sources, probes, tones, paths, [("N1", 8, 0), ("N2", 9, 1), ("N3", 10, 2)], active, 1)
    lab = load_lab(root)
    support, coordinates = recover_small(lab)
    expected = product_from_recovery(lab, support, coordinates)
    output = tmp_path / "nyquist.json"
    run_product(root, output)
    actual = json.loads(output.read_text())
    assert actual == expected
    collapsed = [
        row for row in actual["folded_tracks"]
        if row["capture_id"] == "N1" and row["tone_id"] == "N4"
    ]
    assert collapsed == [
        {
            "tone_id": "N4",
            "source_id": "shaft",
            "capture_id": "N1",
            "sample_rate": 8,
            "trigger_quarters": 0,
            "phase_quarters": 0,
            "folded_bin": 4,
            "sine_sign": 0,
        }
    ]


def test_hidden_quiet_campaign_selects_empty_support(tmp_path, visible_product):
    """An all-command-response campaign has the unique empty recovery."""
    root = tmp_path / "quiet-campaign"
    sources = ["mount"]
    probes = ["tip"]
    tones = [("Q1", 1), ("Q2", 2)]
    paths = {("mount", "tip"): ([0, 1], [1, 1, 1])}
    make_lab(root, sources, probes, tones, paths, [("Q1", 5, 0), ("Q2", 6, 1)], {}, 2)
    output = tmp_path / "quiet.json"
    run_product(root, output)
    product = json.loads(output.read_text())
    lab = load_lab(root)
    assert product == product_from_recovery(lab, [], [])
    assert product["recovery_certificate"]["support_size"] == 0


def test_hidden_equal_supports_use_candidate_identity_order(tmp_path, visible_product):
    """Two exact one-line recoveries are resolved by the documented ASCII support key."""
    root = tmp_path / "tie-campaign"
    sources = ["alpha", "beta"]
    probes = ["tip"]
    tones = [("T1", 1)]
    paths = {
        ("alpha", "tip"): ([0, 1], [1, 1, 1]),
        ("beta", "tip"): ([0, 1], [1, 1, 1]),
    }
    active = {("T1", "beta"): (Fraction(7, 4), Fraction(-3, 5))}
    make_lab(root, sources, probes, tones, paths, [("T1", 5, 0), ("T2", 6, 1)], active, 1)
    output = tmp_path / "tie.json"
    run_product(root, output)
    product = json.loads(output.read_text())
    assert product["recovery_certificate"]["support_key"] == ["T1@alpha"]
    lab = load_lab(root)
    support, coordinates = recover_small(lab)
    assert product == product_from_recovery(lab, support, coordinates)


def test_inconsistent_campaign_preserves_existing_destination(tmp_path, visible_product):
    """A residual outside every allowed source span fails without replacing prior bytes."""
    root = tmp_path / "inconsistent-campaign"
    sources = ["shaft"]
    probes = ["tip"]
    tones = [("I1", 1)]
    paths = {("shaft", "tip"): ([0, 1], [1, 1, 1])}
    active = {("I1", "shaft"): (Fraction(2), Fraction(1))}
    make_lab(root, sources, probes, tones, paths, [("I1", 5, 0), ("I2", 6, 1)], active, 1)
    capture = root / "captures" / "I2.json"
    value = json.loads(capture.read_text())
    current = frac(value["probes"][0]["bins"][0]["measured"]["cos"])
    value["probes"][0]["bins"][0]["measured"]["cos"] = jf(current + Fraction(1, 29))
    write_json(capture, value)
    before_tree = tree_hash(root)
    output = tmp_path / "existing.json"
    output.write_bytes(b"keep-this-product\n")
    result = run_product(root, output, check=False)
    assert result.returncode != 0
    assert output.read_bytes() == b"keep-this-product\n"
    assert tree_hash(root) == before_tree


def test_invalid_fraction_preserves_existing_destination(tmp_path, visible_product):
    """A non-reduced campaign fraction is rejected before any destination replacement."""
    root = tmp_path / "invalid-campaign"
    shutil.copytree(VISIBLE_LAB, root)
    capture = next((root / "captures").glob("*.json"))
    value = json.loads(capture.read_text())
    value["probes"][0]["bins"][0]["expected"]["cos"] = {"n": "2", "d": "2"}
    write_json(capture, value)
    output = tmp_path / "prior.json"
    output.write_bytes(b"prior\n")
    before_tree = tree_hash(root)
    result = run_product(root, output, check=False)
    assert result.returncode != 0
    assert output.read_bytes() == b"prior\n"
    assert tree_hash(root) == before_tree


@pytest.mark.parametrize(
    "case",
    [
        "malformed_json",
        "trailing_json_content",
        "duplicate_identifier",
        "invalid_identifier_syntax",
        "empty_sources",
        "unknown_identifier",
        "missing_path",
        "duplicate_path",
        "nonpositive_tone",
        "tone_above_limit",
        "nonpositive_sample_rate",
        "sample_rate_above_limit",
        "out_of_range_limit",
        "incomplete_bin_grid",
        "incomplete_probe_grid",
        "zero_path_denominator",
    ],
)
def test_documented_invalid_campaigns_preserve_destination(tmp_path, visible_product, case):
    """Every documented campaign-validation family fails before replacement."""
    root = tmp_path / f"invalid-{case}"
    make_minimal_lab(root)
    invalidate_minimal_lab(root, case)
    before_tree = tree_hash(root)
    output = tmp_path / f"{case}.json"
    output.write_bytes(b"standing-product\n")
    result = run_product(root, output, check=False)
    assert result.returncode != 0
    assert output.read_bytes() == b"standing-product\n"
    assert tree_hash(root) == before_tree


def test_trailing_argument_preserves_destination(tmp_path, visible_product):
    """Wrong positional-argument counts fail without touching prior destination bytes."""
    root = tmp_path / "trailing-argument"
    make_minimal_lab(root)
    output = tmp_path / "trailing.json"
    output.write_bytes(b"standing-product\n")
    result = subprocess.run(
        [str(BINARY), str(root), str(output), "extra"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert output.read_bytes() == b"standing-product\n"
    missing = subprocess.run(
        [str(BINARY), str(root)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert missing.returncode != 0
    assert output.read_bytes() == b"standing-product\n"


def test_destination_inside_campaign_is_rejected(tmp_path, visible_product):
    """A destination beneath the read-only campaign tree is rejected without mutation."""
    root = tmp_path / "inside-destination"
    make_minimal_lab(root)
    before_tree = tree_hash(root)
    output = root / "source-spectrum.json"
    result = run_product(root, output, check=False)
    assert result.returncode != 0
    assert not output.exists()
    assert tree_hash(root) == before_tree


def test_success_replaces_existing_destination_cleanly(tmp_path, visible_product):
    """A valid compact campaign replaces prior bytes and leaves no temporary product."""
    root = tmp_path / "successful-replacement"
    make_minimal_lab(root)
    lab = load_lab(root)
    support, coordinates = recover_small(lab)
    expected = product_from_recovery(lab, support, coordinates)
    before_tree = tree_hash(root)
    output = tmp_path / "replace.json"
    output.write_bytes(b"standing-product\n")
    run_product(root, output)
    assert json.loads(output.read_text()) == expected
    assert not output.with_name(output.name + ".tmp").exists()
    assert tree_hash(root) == before_tree


def test_visible_inputs_remain_unchanged_after_all_runs(visible_product):
    """Repeated visible and hidden executions never alter the published campaign tree."""
    assert tree_hash(VISIBLE_LAB) == EXPECTED_INPUT_TREE_SHA256
