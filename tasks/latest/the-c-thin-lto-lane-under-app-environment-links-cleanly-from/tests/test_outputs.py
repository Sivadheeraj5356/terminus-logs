"""Checks for thin LTO observation records under /app."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path("/app/environment")
RUNTIME = Path("/app")
HARNESS = APP / "ci" / "harness"
OBSERVATION = RUNTIME / "output" / "lto_observation.json"
BINARY = RUNTIME / "work" / "bin" / "matrix_app"
LTO_ROOT = RUNTIME / "work" / "lto"
OBJ_ROOT = RUNTIME / "work" / "obj"
SRC_ROOT = APP / "src"
WORK_ROOT = RUNTIME / "work"
STAMP_PATH = WORK_ROOT / "gen" / "abi_stamp.txt"
SEQUENCES = APP / "ci" / "sequences.json"
STEP_MAP = {
    "pass0": str(HARNESS / "pass0.sh"),
    "pass1": str(HARNESS / "pass1.sh"),
    "pass2": str(HARNESS / "pass2.sh"),
    "pass3": str(HARNESS / "pass3.sh"),
    "pass4": str(HARNESS / "pass4.sh"),
}
GEN_SENSITIVE = {"dispatch", "consumer", "gate_abi", "main"}

_PRISTINE_PROFILE = """{
  "profile": "release",
  "abi_tag": "lane-alpha",
  "dispatch_seed": 17
}
"""

_PRISTINE_TEMPLATE = """#ifndef GATE_ABI_H
#define GATE_ABI_H

#define ABI_TAG_VALUE "@@ABI_TAG@@"
#define GATE_DISPATCH_SEED @@SEED@@

extern "C" const char *gate_abi_tag(void);

#endif
"""


def _pristine_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def pristine_tree() -> list[tuple[Path, str]]:
    return [
        (APP / "gen" / "templates" / "gate_abi.h.tpl", _PRISTINE_TEMPLATE),
        (APP / "gen" / "abi_profile.json", _PRISTINE_PROFILE),
        (APP / "lto" / "graph_digest.py", _pristine_text(APP / "lto" / "graph_digest.py")),
        (APP / "lto" / "sidecar_store.py", _pristine_text(APP / "lto" / "sidecar_store.py")),
        (APP / "auxiliary" / "drift_scan.py", _pristine_text(APP / "auxiliary" / "drift_scan.py")),
        (APP / "auxiliary" / "epoch_courier.py", _pristine_text(APP / "auxiliary" / "epoch_courier.py")),
        (APP / "auxiliary" / "tu_orchestrator.py", _pristine_text(APP / "auxiliary" / "tu_orchestrator.py")),
        (APP / "compile" / "toolchain.cmake", _pristine_text(APP / "compile" / "toolchain.cmake")),
        (APP / "src" / "anchor.cpp", _pristine_text(APP / "src" / "anchor.cpp")),
    ]


@pytest.fixture(autouse=True)
def reset_tree(pristine_tree: list[tuple[Path, str]]) -> None:
    shutil.rmtree(RUNTIME / "work", ignore_errors=True)
    shutil.rmtree(RUNTIME / "output", ignore_errors=True)
    for path, content in pristine_tree:
        path.write_text(content, encoding="utf-8")
    yield
    shutil.rmtree(RUNTIME / "work", ignore_errors=True)
    shutil.rmtree(RUNTIME / "output", ignore_errors=True)
    for path, content in pristine_tree:
        path.write_text(content, encoding="utf-8")


def _run(bash: list[str], check: bool = True, **kwargs: object) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    extra = kwargs.pop("env", None)
    if isinstance(extra, dict):
        env.update(extra)
    return subprocess.run(
        bash,
        cwd=str(RUNTIME),
        text=True,
        capture_output=True,
        check=check,
        env=env,
        **kwargs,
    )


def _fake_bin_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = f"{APP / 'ci' / 'fake_bin'}:{env.get('PATH', '')}"
    env["PYTHONPATH"] = str(APP)
    return env


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_observation() -> dict[str, object]:
    assert OBSERVATION.is_file(), "lto_observation.json missing"
    return _read_json(OBSERVATION)


def _matrix_row(payload: dict[str, object], scenario: str) -> dict[str, object]:
    matrix = payload.get("matrix")
    assert isinstance(matrix, list)
    for row in matrix:
        assert isinstance(row, dict)
        if row.get("scenario") == scenario:
            return row
    raise AssertionError(f"missing matrix row for {scenario}")


def _nm_symbols(binary: Path) -> list[str]:
    proc = _run(["nm", "--defined-only", "--format=posix", str(binary)], check=True)
    symbols: list[str] = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] in {"T", "t", "W", "w", "D", "d", "B", "b"}:
            symbols.append(parts[0])
    return sorted(set(symbols))


def _probe_dict(binary: Path) -> dict[str, int | str]:
    proc = _run([str(binary), "--probe"], check=True)
    line = proc.stdout.strip().splitlines()[0]
    parts = {}
    for token in line.split():
        if "=" in token:
            key, value = token.split("=", 1)
            parts[key] = value
    return {
        "lane": int(parts["lane"]),
        "abi_tag": str(parts["abi"]),
        "seed": int(parts["seed"]),
        "mixed": int(parts["mixed"]),
    }


def _live_import_hashes() -> dict[str, str]:
    sys.path.insert(0, str(APP))
    from lto.graph_digest import import_hash
    from lto.module_index import all_modules

    return {module: import_hash(module, SRC_ROOT, WORK_ROOT) for module in all_modules()}


def _journal_generation() -> int:
    path = LTO_ROOT / "epoch_journal.json"
    assert path.is_file(), "epoch_journal.json missing"
    payload = _read_json(path)
    return int(payload.get("generation", 0))


def _import_sensitive_epochs() -> dict[str, int]:
    epochs: dict[str, int] = {}
    for module in sorted(GEN_SENSITIVE):
        sidecar = _read_sidecar(module)
        epochs[module] = int(sidecar.get("link_epoch", 0))
    return epochs


def _assert_epoch_coherence() -> None:
    generation = _journal_generation()
    epochs = _import_sensitive_epochs()
    assert generation > 0, "journal generation must be positive after build"
    assert len(set(epochs.values())) == 1, f"import-sensitive link_epoch mismatch: {epochs}"
    assert next(iter(epochs.values())) == generation


def _read_sidecar(module: str) -> dict[str, object]:
    path = LTO_ROOT / f"{module}.summary.json"
    assert path.is_file(), f"missing summary sidecar for {module}"
    payload = _read_json(path)
    assert isinstance(payload, dict)
    return payload


def _run_incremental_report() -> dict[str, object]:
    report_path = RUNTIME / "output" / "link_report.json"
    _run(
        [
            "python3",
            str(APP / "auxiliary" / "tu_orchestrator.py"),
            "--mode",
            "incremental",
            "--profile",
            "release",
            "--report",
            str(report_path),
        ],
        check=True,
        env=_fake_bin_env(),
    )
    return _read_json(report_path)


def _emit_pass(scenario: str, append: bool = False) -> None:
    args = ["python3", str(APP / "ci" / "observation_emit.py"), "--pass", scenario]
    if append:
        args.append("--append")
    _run(args, check=True, env=_fake_bin_env())


def _clean_rebuild_row() -> dict[str, object]:
    shutil.rmtree(RUNTIME / "work", ignore_errors=True)
    _run(["bash", STEP_MAP["pass0"]], check=True)
    return _matrix_row(_read_observation(), "cold")


def _object_has_thin_lto(obj: Path) -> bool:
    proc = _run(["llvm-readobj", "--sections", str(obj)], check=True)
    lowered = proc.stdout.lower()
    if "llvm_lto" in lowered or ".llvm.lto" in lowered:
        return True
    readelf = _run(["readelf", "-S", str(obj)], check=False)
    if "llvm bitcode" in readelf.stderr.lower():
        return True
    return obj.read_bytes()[:2] == b"BC"


def _touch_template_seed() -> None:
    profile = APP / "gen" / "abi_profile.json"
    data = _read_json(profile)
    data["dispatch_seed"] = int(data["dispatch_seed"]) + 1
    profile.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_z01() -> None:
    """Cold pass must emit a release matrix row aligned with the linked binary and pristine profile."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    payload = _read_observation()
    assert payload.get("report_version") == 1
    row = _matrix_row(payload, "cold")
    assert row.get("profile") == "release"
    profile = _read_json(APP / "gen" / "abi_profile.json")
    assert int(profile.get("dispatch_seed", 0)) == 17
    summary = row.get("summary_hash")
    assert isinstance(summary, dict) and summary
    symbols = row.get("linked_symbol_set")
    assert isinstance(symbols, list) and symbols
    assert symbols == _nm_symbols(BINARY)
    assert row.get("binary_sha256") == _sha256(BINARY)
    probe = row.get("probe")
    assert isinstance(probe, dict)
    assert probe == _probe_dict(BINARY)
    assert int(probe["seed"]) == int(profile["dispatch_seed"])
    assert _journal_generation() == 1
    _assert_epoch_coherence()


def test_z02() -> None:
    """Header-touch incremental pass must move import-sensitive summary hashes and binary bytes."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    before = _matrix_row(_read_observation(), "cold")
    _run(["bash", STEP_MAP["pass1"]], check=True)
    after = _matrix_row(_read_observation(), "header_touch")
    before_hash = before.get("summary_hash")
    after_hash = after.get("summary_hash")
    assert isinstance(before_hash, dict) and isinstance(after_hash, dict)
    moved = [
        module
        for module in GEN_SENSITIVE
        if before_hash.get(module) != after_hash.get(module)
    ]
    assert moved, "expected import-sensitive summary hash movement"
    assert after.get("binary_sha256") != before.get("binary_sha256")
    after_probe = after.get("probe")
    assert isinstance(after_probe, dict)
    clean_probe = _clean_rebuild_row().get("probe")
    assert isinstance(clean_probe, dict)
    assert after_probe["seed"] == clean_probe["seed"]
    assert after_probe["mixed"] == clean_probe["mixed"]


def test_z03() -> None:
    """Incremental and clean rebuilds must match after header touch."""
    base_profile = _PRISTINE_PROFILE
    (APP / "gen" / "abi_profile.json").write_text(base_profile, encoding="utf-8")
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    incremental = _matrix_row(_read_observation(), "header_touch")
    touched_profile = (APP / "gen" / "abi_profile.json").read_text(encoding="utf-8")
    shutil.rmtree(RUNTIME / "work", ignore_errors=True)
    (APP / "gen" / "abi_profile.json").write_text(base_profile, encoding="utf-8")
    _run(["bash", STEP_MAP["pass0"]], check=True)
    (APP / "gen" / "abi_profile.json").write_text(touched_profile, encoding="utf-8")
    _run_incremental_report()
    _emit_pass("header_touch", append=True)
    clean = _matrix_row(_read_observation(), "header_touch")
    for key in ("summary_hash", "linked_symbol_set", "binary_sha256"):
        assert incremental.get(key) == clean.get(key)


def test_z04() -> None:
    """Summary sidecars must track live import hashes and trimmed ABI stamps for import-sensitive modules."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    assert STAMP_PATH.is_file(), "abi_stamp.txt missing after header touch"
    stamp = STAMP_PATH.read_text(encoding="utf-8").strip()
    live = _live_import_hashes()
    for module in GEN_SENSITIVE:
        sidecar = _read_sidecar(module)
        assert sidecar.get("import_hash") == live[module]
        assert sidecar.get("abi_tag") == stamp
    _assert_epoch_coherence()
    anchor = _read_sidecar("anchor")
    assert anchor.get("import_hash") == live["anchor"]
    assert anchor.get("abi_tag") in ("", None)


def test_z05() -> None:
    """ABI profile touch from a cold workspace must revise probe output and epoch journal."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    cold = _matrix_row(_read_observation(), "cold")
    cold_probe = cold.get("probe")
    cold_hash = cold.get("summary_hash")
    _run(["bash", STEP_MAP["pass2"]], check=True)
    abi = _matrix_row(_read_observation(), "abi_touch")
    abi_probe = abi.get("probe")
    abi_hash = abi.get("summary_hash")
    assert isinstance(cold_probe, dict) and isinstance(abi_probe, dict)
    assert isinstance(cold_hash, dict) and isinstance(abi_hash, dict)
    assert abi_probe["abi_tag"] != cold_probe["abi_tag"]
    assert str(abi_probe["abi_tag"]).endswith("-rev")
    moved = [
        module
        for module in GEN_SENSITIVE
        if cold_hash.get(module) != abi_hash.get(module)
    ]
    assert len(moved) == len(GEN_SENSITIVE)
    assert _journal_generation() == 2
    _assert_epoch_coherence()


def test_z06() -> None:
    """Sequence entries must replay pass scripts and emit coherent matrix rows."""
    sequences = _read_json(SEQUENCES).get("sequences")
    assert isinstance(sequences, list)
    for entry in sequences:
        assert isinstance(entry, dict)
        steps = entry.get("steps")
        assert isinstance(steps, list)
        shutil.rmtree(RUNTIME / "work", ignore_errors=True)
        shutil.rmtree(RUNTIME / "output", ignore_errors=True)
        for step in steps:
            script = STEP_MAP.get(str(step))
            assert script, f"unknown step {step}"
            _run(["bash", script], check=True)
        payload = _read_observation()
        matrix = payload.get("matrix")
        assert isinstance(matrix, list) and matrix
        last = matrix[-1]
        assert isinstance(last, dict)
        assert last.get("binary_sha256") == _sha256(BINARY)
        probe = last.get("probe")
        assert isinstance(probe, dict)
        assert probe == _probe_dict(BINARY)
        if entry.get("id") in {"abi_chain", "full_chain", "replay_abi_chain"}:
            _assert_epoch_coherence()


def test_z07() -> None:
    """Release builds must retain thin-LTO sections and reject disable attempts at runtime."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    dispatch_obj = OBJ_ROOT / "dispatch.o"
    assert dispatch_obj.is_file(), "dispatch.o missing after incremental pass"
    assert _object_has_thin_lto(dispatch_obj)
    proc = _run(
        ["clang-wrap", "-fno-lto", "-c", str(SRC_ROOT / "anchor.cpp"), "-o", "/tmp/x.o"],
        check=False,
        env=_fake_bin_env(),
    )
    assert proc.returncode != 0
    assert "thin-lto disable blocked" in proc.stderr


def test_z08() -> None:
    """Removing object and binary outputs while sidecars remain must rebuild on the next incremental pass."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    profile_snap = (APP / "gen" / "abi_profile.json").read_text(encoding="utf-8")
    shutil.rmtree(OBJ_ROOT, ignore_errors=True)
    shutil.rmtree(WORK_ROOT / "bin", ignore_errors=True)
    _run_incremental_report()
    assert BINARY.is_file(), "matrix_app missing after object wipe recovery"
    recovered_probe = _probe_dict(BINARY)
    recovered_symbols = _nm_symbols(BINARY)
    shutil.rmtree(RUNTIME / "work", ignore_errors=True)
    (APP / "gen" / "abi_profile.json").write_text(profile_snap, encoding="utf-8")
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run_incremental_report()
    clean_probe = _probe_dict(BINARY)
    clean_symbols = _nm_symbols(BINARY)
    assert recovered_probe == clean_probe
    assert recovered_symbols == clean_symbols


def test_z09() -> None:
    """Stale import_hash in a summary sidecar must trigger relink and restore binary parity."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    expected_sha = _sha256(BINARY)
    expected_probe = _probe_dict(BINARY)
    sidecar_path = LTO_ROOT / "dispatch.summary.json"
    sidecar = _read_json(sidecar_path)
    sidecar["import_hash"] = "0" * 64
    sidecar_path.write_text(json.dumps(sidecar, sort_keys=True) + "\n", encoding="utf-8")
    _run_incremental_report()
    assert _sha256(BINARY) == expected_sha
    assert _probe_dict(BINARY) == expected_probe
    restored = _read_sidecar("dispatch")
    assert restored.get("import_hash") == _live_import_hashes()["dispatch"]


def test_z10() -> None:
    """Unchanged workspace state must not relink modules on repeated incremental passes."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    before_sha = _sha256(BINARY)
    first = _run_incremental_report()
    second = _run_incremental_report()
    relinked_first = first.get("relinked_modules")
    relinked_second = second.get("relinked_modules")
    assert isinstance(relinked_first, list) and relinked_first == []
    assert isinstance(relinked_second, list) and relinked_second == []
    assert _sha256(BINARY) == before_sha


def test_z11() -> None:
    """Full header then ABI chain must preserve dispatch seed while revising abi_tag."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    cold = _matrix_row(_read_observation(), "cold")
    _run(["bash", STEP_MAP["pass1"]], check=True)
    header = _matrix_row(_read_observation(), "header_touch")
    _run(["bash", STEP_MAP["pass2"]], check=True)
    abi = _matrix_row(_read_observation(), "abi_touch")
    cold_probe = cold.get("probe")
    header_probe = header.get("probe")
    abi_probe = abi.get("probe")
    assert isinstance(cold_probe, dict)
    assert isinstance(header_probe, dict)
    assert isinstance(abi_probe, dict)
    assert header_probe["seed"] != cold_probe["seed"]
    assert abi_probe["seed"] == header_probe["seed"]
    assert abi_probe["mixed"] == header_probe["mixed"]
    assert str(abi_probe["abi_tag"]).endswith("-rev")
    assert abi_probe["abi_tag"] != header_probe["abi_tag"]
    payload = _read_observation()
    transcript = payload.get("incremental_transcript")
    assert isinstance(transcript, list) and len(transcript) >= 3
    scenarios = [row.get("scenario") for row in payload.get("matrix", []) if isinstance(row, dict)]
    assert scenarios.count("cold") == 1
    assert "header_touch" in scenarios
    assert "abi_touch" in scenarios


def test_z12() -> None:
    """Anchor-only source edits must relink anchor without desynchronizing import-sensitive sidecars."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    before_mixed = _probe_dict(BINARY)["mixed"]
    anchor_path = SRC_ROOT / "anchor.cpp"
    anchor_path.write_text(
        anchor_path.read_text(encoding="utf-8").replace("return 3;", "return 9;"),
        encoding="utf-8",
    )
    report = _run_incremental_report()
    relinked = report.get("relinked_modules")
    assert isinstance(relinked, list)
    assert relinked == ["anchor"]
    after_mixed = _probe_dict(BINARY)["mixed"]
    assert after_mixed != before_mixed
    live = _live_import_hashes()
    for module in GEN_SENSITIVE:
        sidecar = _read_sidecar(module)
        assert sidecar.get("import_hash") == live[module]


def _live_matrix_fields() -> dict[str, object]:
    sys.path.insert(0, str(APP))
    from lto.module_index import all_modules
    from lto.summary_read import summary_hash_map
    from probes.symbol_probe import linked_symbol_set

    modules = all_modules()
    return {
        "summary_hash": summary_hash_map(LTO_ROOT, modules),
        "linked_symbol_set": linked_symbol_set(BINARY),
        "binary_sha256": _sha256(BINARY),
        "probe": _probe_dict(BINARY),
    }


def test_z13() -> None:
    """Sidecar checkpoint replay after workspace wipe must match a direct incremental seed bump."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    _run(["bash", STEP_MAP["pass3"]], check=True)
    replay = _matrix_row(_read_observation(), "sidecar_replay")
    shutil.rmtree(RUNTIME / "work", ignore_errors=True)
    shutil.rmtree(RUNTIME / "output", ignore_errors=True)
    (APP / "gen" / "abi_profile.json").write_text(_PRISTINE_PROFILE, encoding="utf-8")
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    _touch_template_seed()
    _run_incremental_report()
    direct = _live_matrix_fields()
    for key in ("summary_hash", "linked_symbol_set", "binary_sha256", "probe"):
        assert replay.get(key) == direct.get(key)


def test_z14() -> None:
    """Stale abi_tag on a non-dispatch import-sensitive sidecar must heal on incremental pass."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    stamp = STAMP_PATH.read_text(encoding="utf-8").strip()
    path = LTO_ROOT / "consumer.summary.json"
    payload = _read_json(path)
    payload["abi_tag"] = stamp[::-1]
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    _run_incremental_report()
    assert _read_sidecar("consumer").get("abi_tag") == stamp
    live = _live_import_hashes()
    assert _read_sidecar("consumer").get("import_hash") == live["consumer"]
    _assert_epoch_coherence()


def test_z15() -> None:
    """ABI-only chain must realign import hashes, epochs, and probe without a header-touch pass."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    cold = _matrix_row(_read_observation(), "cold")
    _run(["bash", STEP_MAP["pass2"]], check=True)
    abi = _matrix_row(_read_observation(), "abi_touch")
    cold_hash = cold.get("summary_hash")
    abi_hash = abi.get("summary_hash")
    assert isinstance(cold_hash, dict) and isinstance(abi_hash, dict)
    for module in GEN_SENSITIVE:
        assert cold_hash.get(module) != abi_hash.get(module)
    abi_probe = abi.get("probe")
    assert isinstance(abi_probe, dict)
    assert str(abi_probe["abi_tag"]).endswith("-rev")
    assert abi_probe["seed"] == _probe_dict(BINARY)["seed"]
    assert _journal_generation() == 2
    _assert_epoch_coherence()
    shutil.rmtree(RUNTIME / "work", ignore_errors=True)
    shutil.rmtree(RUNTIME / "output", ignore_errors=True)
    _run(["bash", STEP_MAP["pass0"]], check=True)
    profile = APP / "gen" / "abi_profile.json"
    data = _read_json(profile)
    tag = str(data["abi_tag"])
    if not tag.endswith("-rev"):
        data["abi_tag"] = tag + "-rev"
    profile.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _run_incremental_report()
    _emit_pass("abi_touch", append=True)
    clean = _matrix_row(_read_observation(), "abi_touch")
    for key in ("summary_hash", "linked_symbol_set", "binary_sha256", "probe"):
        assert abi.get(key) == clean.get(key)


def test_z16() -> None:
    """A lagging link_epoch on one import-sensitive sidecar must heal without disturbing probe output."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    expected_probe = _probe_dict(BINARY)
    expected_sha = _sha256(BINARY)
    journal_path = LTO_ROOT / "epoch_journal.json"
    journal_path.write_text(json.dumps({"generation": 2}, sort_keys=True) + "\n", encoding="utf-8")
    consumer_path = LTO_ROOT / "consumer.summary.json"
    consumer = _read_json(consumer_path)
    consumer["link_epoch"] = 0
    consumer_path.write_text(json.dumps(consumer, sort_keys=True) + "\n", encoding="utf-8")
    report = _run_incremental_report()
    relinked = report.get("relinked_modules")
    assert isinstance(relinked, list)
    assert "consumer" in relinked
    assert _probe_dict(BINARY) == expected_probe
    assert _sha256(BINARY) == expected_sha
    assert _read_sidecar("consumer").get("link_epoch") == 2
    _assert_epoch_coherence()


def test_z17() -> None:
    """On-disk object bytes that disagree with sidecar object_sha256 must trigger relink and heal."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    expected_probe = _probe_dict(BINARY)
    expected_sha = _sha256(BINARY)
    dispatch_obj = OBJ_ROOT / "dispatch.o"
    dispatch_obj.write_bytes(b"\x00" * max(64, dispatch_obj.stat().st_size))
    report = _run_incremental_report()
    relinked = report.get("relinked_modules")
    assert isinstance(relinked, list)
    assert "dispatch" in relinked
    assert _probe_dict(BINARY) == expected_probe
    assert _sha256(BINARY) == expected_sha
    sidecar = _read_sidecar("dispatch")
    assert sidecar.get("object_sha256") == _sha256(dispatch_obj)
    _assert_epoch_coherence()


def test_z18() -> None:
    """Replay-then-ABI chain must stay coherent when observations are re-emitted from the same workspace."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    _run(["bash", STEP_MAP["pass3"]], check=True)
    _run(["bash", STEP_MAP["pass2"]], check=True)
    replay_abi = _matrix_row(_read_observation(), "abi_touch")
    shutil.rmtree(RUNTIME / "output", ignore_errors=True)
    _emit_pass("abi_touch", append=False)
    reemitted = _matrix_row(_read_observation(), "abi_touch")
    for key in ("summary_hash", "linked_symbol_set", "binary_sha256", "probe"):
        assert replay_abi.get(key) == reemitted.get(key)
    _assert_epoch_coherence()


def _read_manifest() -> dict[str, object]:
    path = WORK_ROOT / "checkpoint" / "manifest.json"
    assert path.is_file(), "checkpoint manifest missing"
    return _read_json(path)


def test_z19() -> None:
    """Sidecar replay must write a checkpoint manifest aligned with the active journal."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    _run(["bash", STEP_MAP["pass3"]], check=True)
    manifest = _read_manifest()
    assert int(manifest.get("replay_seq", 0)) == 1
    assert int(manifest.get("journal_generation", 0)) == 2
    assert _journal_generation() >= int(manifest.get("journal_generation", 0))
    _assert_epoch_coherence()


def test_z20() -> None:
    """Double replay must advance replay_seq and heal a missing journal from the manifest."""
    sequences = _read_json(SEQUENCES).get("sequences")
    assert isinstance(sequences, list)
    entry = next(item for item in sequences if isinstance(item, dict) and item.get("id") == "double_replay")
    steps = entry.get("steps")
    assert isinstance(steps, list)
    shutil.rmtree(RUNTIME / "work", ignore_errors=True)
    shutil.rmtree(RUNTIME / "output", ignore_errors=True)
    for step in steps:
        script = STEP_MAP.get(str(step))
        assert script, f"unknown step {step}"
        _run(["bash", script], check=True)
    manifest = _read_manifest()
    assert int(manifest.get("replay_seq", 0)) == 2
    generation = int(manifest.get("journal_generation", 0))
    assert generation >= 2
    assert _journal_generation() >= generation
    journal_path = LTO_ROOT / "epoch_journal.json"
    before_epochs = _import_sensitive_epochs()
    journal_path.unlink()
    _run_incremental_report()
    assert _journal_generation() == generation
    assert _import_sensitive_epochs() == before_epochs


def test_z21() -> None:
    """Header touch must move consumer import hash without editing consumer.cpp."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    cold_hash = _read_sidecar("consumer").get("import_hash")
    consumer_src = SRC_ROOT / "consumer.cpp"
    before_mtime = consumer_src.stat().st_mtime
    _run(["bash", STEP_MAP["pass1"]], check=True)
    after_hash = _read_sidecar("consumer").get("import_hash")
    assert cold_hash != after_hash
    assert consumer_src.stat().st_mtime == before_mtime


def test_z22() -> None:
    """Replay restore must reconcile journal from manifest before relink evaluation."""
    _run(["bash", STEP_MAP["pass0"]], check=True)
    _run(["bash", STEP_MAP["pass1"]], check=True)
    _run(["bash", STEP_MAP["pass3"]], check=True)
    manifest = _read_manifest()
    expected = int(manifest.get("journal_generation", 0))
    journal_path = LTO_ROOT / "epoch_journal.json"
    before_epochs = _import_sensitive_epochs()
    journal_path.unlink()
    _run_incremental_report()
    assert _journal_generation() == expected
    assert _import_sensitive_epochs() == before_epochs
