"""Behavioral checks for static-pod hash feasibility certification."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ENV = Path("/app/environment")
OUT = Path("/app/output/feasibility_certificate.json")
STAGE = Path("/app/output/stage")
SETS = ENV / "fixtures" / "q2_sets"
SLICE = ENV / "fixtures" / "slices" / "q46.txt"
PROFILES = ENV / "profiles"

EMPTY_TIP = "811c9dc5"


def _fnv1a32(text: str) -> int:
    h = 2166136261
    for c in text.encode():
        h ^= c
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _hex32(value: int) -> str:
    return f"{value:08x}"


def _slice_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in SLICE.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        out[key] = val
    return out


def _scope_letter(band: str) -> str:
    text = (PROFILES / f"{band}.toml").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("scope_letter"):
            return line.split("=", 1)[1].strip().strip('"')
    raise AssertionError(f"missing scope_letter for {band}")


def _base_tag(item: dict, annex_on: bool, prefix: str, order: str) -> str:
    annex: list[str] = []
    labels: list[str] = []
    if annex_on:
        for key, val in item.get("annotations", {}).items():
            if key.startswith(prefix):
                annex.append(f"{key}={val}")
        annex.sort()
    for key, val in item.get("labels", {}).items():
        labels.append(f"{key}={val}")
    labels.sort()
    if order == "annex_before_labels":
        return ",".join(annex + labels)
    return ",".join(labels + annex)


def _tip_chain(blob: str) -> str:
    concat = ""
    at = 0
    while at < len(blob):
        nl = blob.find("\n", at)
        if nl < 0:
            break
        line = blob[at : nl + 1]
        concat += _hex32(_fnv1a32(line))
        at = nl + 1
    return _hex32(_fnv1a32(concat))


def _replay_rows(
    *,
    matrix_dir: Path = SETS,
    prior_journals: dict[str, str] | None = None,
    prior_cache: dict[str, tuple[int, int, int]] | None = None,
) -> list[dict]:
    """Replay matrix order from public fixtures, profiles, and slice constants."""
    slice_kv = _slice_map()
    prefix = slice_kv["ANNEX_PREFIX"]
    order = slice_kv["ORDER"]
    table = slice_kv["SEAL_TABLE"].split(",")
    mod = int(slice_kv["WINDOW_MOD"])
    journals: dict[str, list[str]] = {}
    if prior_journals:
        for mid, blob in prior_journals.items():
            journals[mid] = [ln + "\n" for ln in blob.splitlines() if ln]
    cache: dict[str, tuple[int, int, int]] = dict(prior_cache or {})
    out: list[dict] = []
    for path in sorted(matrix_dir.glob("*.json")):
        window_id = _fnv1a32(path.stem) % mod
        for item in json.loads(path.read_text(encoding="utf-8")):
            mid = item["manifest_id"]
            ns = item.get("namespace", "")
            for band, annex in (("p7", False), ("p8", True)):
                base = _base_tag(item, annex, prefix, order)
                frames = journals.setdefault(mid, [])
                parent_tip = _tip_chain("".join(frames))
                rev = len(frames) + 1
                line = f"GEN={rev}|BAND={band}|BODY={base}\n"
                frames.append(line)
                tag = f"{base},rev={rev}" if base else f"rev={rev}"
                annex_flag = 1 if annex else 0
                if mid not in cache:
                    epoch = 1
                else:
                    last_a, last_w, epoch = cache[mid]
                    if last_a != annex_flag or last_w != window_id:
                        epoch += 1
                cache[mid] = (annex_flag, window_id, epoch)
                letter = _scope_letter(band)
                seal = table[(window_id + rev) % len(table)]
                wire = f"{mid}|{tag}|{letter}|W{window_id}"
                secondary = tag + mid + ns + seal + str(epoch) + parent_tip + "W" + str(window_id)
                digest = _hex32(_fnv1a32(wire)) + _hex32(_fnv1a32(secondary))
                out.append(
                    {
                        "manifest_id": mid,
                        "scope_band": band,
                        "unit_tag": tag,
                        "canonical_byte_digest": digest,
                        "cache_epoch": epoch,
                        "journal_tip_hex": _tip_chain("".join(frames)),
                        "seal_window": window_id,
                        "parent_tip": parent_tip,
                        "ns": ns,
                        "gen": rev,
                    }
                )
    return out


def _wrong_seal_digest(row: dict, parent_tip: str) -> str:
    """Digest using window-only seal index (ignores GEN mix)."""
    slice_kv = _slice_map()
    table = slice_kv["SEAL_TABLE"].split(",")
    seal = table[row["seal_window"] % len(table)]
    tag = row["unit_tag"]
    mid = row["manifest_id"]
    ns = row["ns"]
    epoch = str(row["cache_epoch"])
    window_s = str(row["seal_window"])
    letter = _scope_letter(row["scope_band"])
    wire = f"{mid}|{tag}|{letter}|W{window_s}"
    secondary = tag + mid + ns + seal + epoch + parent_tip + "W" + window_s
    return _hex32(_fnv1a32(wire)) + _hex32(_fnv1a32(secondary))


def _unsalted_digest(row: dict, parent_tip: str) -> str:
    """Digest that omits parent_tip."""
    slice_kv = _slice_map()
    table = slice_kv["SEAL_TABLE"].split(",")
    seal = table[(row["seal_window"] + row["gen"]) % len(table)]
    tag = row["unit_tag"]
    mid = row["manifest_id"]
    ns = row["ns"]
    epoch = str(row["cache_epoch"])
    window_s = str(row["seal_window"])
    letter = _scope_letter(row["scope_band"])
    wire = f"{mid}|{tag}|{letter}|W{window_s}"
    wrong = tag + mid + ns + seal + epoch + "W" + window_s
    right = tag + mid + ns + seal + epoch + parent_tip + "W" + window_s
    assert _hex32(_fnv1a32(wrong)) != _hex32(_fnv1a32(right)) or parent_tip == ""
    return _hex32(_fnv1a32(wire)) + _hex32(_fnv1a32(wrong))


def _run_checked(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {label}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def _wipe() -> None:
    wipe = subprocess.run(
        ["bash", "/app/environment/migrations/wipe7.sh"],
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    _run_checked(wipe, "wipe7")


def _bake() -> None:
    bake = subprocess.run(
        ["bash", "/app/environment/scripts/bake_ws.sh"],
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    _run_checked(bake, "bake_ws")


def _run_drive(
    matrix_dir: Path = SETS,
    *,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(extra_env or {})
    return subprocess.run(
        [
            "/app/environment/build/spw_run",
            "--matrix",
            str(matrix_dir),
            "--out",
            str(OUT),
        ],
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
        env=env,
    )


def _drive(matrix_dir: Path = SETS) -> dict:
    drive = _run_drive(matrix_dir)
    _run_checked(drive, "spw_run")
    return json.loads(OUT.read_text(encoding="utf-8"))


def _certify() -> dict:
    _wipe()
    _bake()
    return _drive()


def _raw_tip(mid: str) -> str:
    path = STAGE / "journal" / f"{mid}.frames"
    if not path.exists():
        return _hex32(_fnv1a32(""))
    return _hex32(_fnv1a32(path.read_text(encoding="utf-8")))


def test_full_matrix_matches_closed_reduction() -> None:
    """Full matrix emit matches the closed reduction from fixtures and docs."""
    want = _replay_rows()
    cert = _certify()
    assert cert["violations"] == 0
    assert len(cert["rows"]) == len(want)
    for got, exp in zip(cert["rows"], want, strict=True):
        assert got["manifest_id"] == exp["manifest_id"]
        assert got["scope_band"] == exp["scope_band"]
        assert got["unit_tag"] == exp["unit_tag"]
        assert got["canonical_byte_digest"] == exp["canonical_byte_digest"]
        assert got["cache_epoch"] == exp["cache_epoch"]
        assert got["journal_tip_hex"] == exp["journal_tip_hex"]
        assert got["seal_window"] == exp["seal_window"]
        assert len(got["canonical_byte_digest"]) == 16
        assert len(got["journal_tip_hex"]) == 8
        assert got["journal_tip_hex"] != exp["parent_tip"] or exp["parent_tip"] == EMPTY_TIP


def test_parent_tip_salts_secondary_digest() -> None:
    """Secondary digest half mixes pre-append tip; omitting the salt fails."""
    want = _replay_rows()
    cert = _certify()
    first = next(r for r in want if r["manifest_id"] == "e3-canary" and r["scope_band"] == "p7")
    second = next(r for r in want if r["manifest_id"] == "e3-canary" and r["scope_band"] == "p8")
    assert first["parent_tip"] == EMPTY_TIP
    assert second["parent_tip"] != EMPTY_TIP
    assert second["parent_tip"] == first["journal_tip_hex"]
    got_first = next(
        r for r in cert["rows"] if r["manifest_id"] == "e3-canary" and r["scope_band"] == "p7"
    )
    got_second = next(
        r for r in cert["rows"] if r["manifest_id"] == "e3-canary" and r["scope_band"] == "p8"
    )
    assert got_first["canonical_byte_digest"] == first["canonical_byte_digest"]
    assert got_second["canonical_byte_digest"] == second["canonical_byte_digest"]
    assert got_second["canonical_byte_digest"] != _unsalted_digest(second, second["parent_tip"])
    assert got_first["journal_tip_hex"] == first["journal_tip_hex"]
    assert got_second["journal_tip_hex"] == second["journal_tip_hex"]
    assert got_second["journal_tip_hex"] != second["parent_tip"]


def test_tip_chain_uses_per_line_hashing() -> None:
    """Graded tips follow the per-line chain, not a single raw-file FNV."""
    want = _replay_rows()
    cert = _certify()
    mid = "e3-canary"
    row = next(r for r in cert["rows"] if r["manifest_id"] == mid and r["scope_band"] == "p8")
    exp = next(r for r in want if r["manifest_id"] == mid and r["scope_band"] == "p8")
    assert row["journal_tip_hex"] == exp["journal_tip_hex"]
    assert row["journal_tip_hex"] != _raw_tip(mid)
    blob = (STAGE / "journal" / f"{mid}.frames").read_text(encoding="utf-8")
    assert row["journal_tip_hex"] == _tip_chain(blob)
    for got, target in zip(cert["rows"], want, strict=True):
        assert got["journal_tip_hex"] == target["journal_tip_hex"]
        assert got["canonical_byte_digest"] == target["canonical_byte_digest"]


def test_gen_fence_and_rev_token() -> None:
    """Journal lines carry GEN fences; unit_tag rev tokens stay aligned."""
    cert = _certify()
    mid = "e3-canary"
    frames = (STAGE / "journal" / f"{mid}.frames").read_text(encoding="utf-8").splitlines()
    assert frames[0].startswith("GEN=1|BAND=p7|BODY=")
    assert frames[1].startswith("GEN=2|BAND=p8|BODY=")
    p8 = next(r for r in cert["rows"] if r["manifest_id"] == mid and r["scope_band"] == "p8")
    assert "rev=2" in p8["unit_tag"]
    assert any(tok.startswith("q46.") for tok in p8["unit_tag"].split(","))


def test_seal_window_varies_by_set_stem() -> None:
    """Rematerialized manifests under later set stems select a new seal window."""
    want = _replay_rows()
    cert = _certify()
    got = [r for r in cert["rows"] if r["manifest_id"] == "c1-alpha"]
    exp = [r for r in want if r["manifest_id"] == "c1-alpha"]
    assert len(got) == 4
    assert got[0]["seal_window"] != got[2]["seal_window"]
    for g, e in zip(got, exp, strict=True):
        assert g["seal_window"] == e["seal_window"]
        assert g["canonical_byte_digest"] == e["canonical_byte_digest"]
        assert g["journal_tip_hex"] == e["journal_tip_hex"]
        assert g["cache_epoch"] == e["cache_epoch"]


def test_gen_mixes_seal_token_and_namespace_salt() -> None:
    """Seal token follows (window+GEN); secondary mixes fixture namespace."""
    want = _replay_rows()
    cert = _certify()
    p7 = next(r for r in want if r["manifest_id"] == "e3-canary" and r["scope_band"] == "p7")
    p8 = next(r for r in want if r["manifest_id"] == "e3-canary" and r["scope_band"] == "p8")
    assert p7["seal_window"] == p8["seal_window"]
    assert p7["gen"] != p8["gen"]
    assert p7["ns"] == "canary"
    got_p7 = next(
        r for r in cert["rows"] if r["manifest_id"] == "e3-canary" and r["scope_band"] == "p7"
    )
    got_p8 = next(
        r for r in cert["rows"] if r["manifest_id"] == "e3-canary" and r["scope_band"] == "p8"
    )
    assert got_p7["canonical_byte_digest"] == p7["canonical_byte_digest"]
    assert got_p8["canonical_byte_digest"] == p8["canonical_byte_digest"]
    assert got_p7["canonical_byte_digest"] != _wrong_seal_digest(p7, p7["parent_tip"])
    assert got_p8["canonical_byte_digest"] != _wrong_seal_digest(p8, p8["parent_tip"])
    assert got_p7["canonical_byte_digest"] != got_p8["canonical_byte_digest"]


def test_epoch_advances_on_annex_and_window() -> None:
    """Durable epoch advances across annex flips and seal-window rematerialization."""
    want = _replay_rows()
    cert = _certify()
    got = [r for r in cert["rows"] if r["manifest_id"] == "c1-alpha"]
    exp = [r for r in want if r["manifest_id"] == "c1-alpha"]
    assert [r["cache_epoch"] for r in got] == [r["cache_epoch"] for r in exp]
    assert got[1]["cache_epoch"] > got[0]["cache_epoch"]
    assert got[2]["cache_epoch"] > got[1]["cache_epoch"]
    assert got[3]["cache_epoch"] > got[2]["cache_epoch"]
    for g, e in zip(got, exp, strict=True):
        assert g["canonical_byte_digest"] == e["canonical_byte_digest"]


def test_crash_torn_tail_mended_before_seal() -> None:
    """Incomplete journal tails without a final newline are cleared before emit."""
    want = _replay_rows()
    _wipe()
    _bake()
    torn = STAGE / "journal" / "e3-canary.frames"
    marker = "BODY=partial-no-newline"
    torn.write_text(f"GEN=1|BAND=p7|{marker}", encoding="utf-8")
    cert = _drive()
    assert cert["violations"] == 0
    body = torn.read_text(encoding="utf-8")
    assert marker not in body
    assert body.startswith("GEN=1|BAND=p7|BODY=")
    for got, exp in zip(cert["rows"], want, strict=True):
        assert got["journal_tip_hex"] == exp["journal_tip_hex"]
        assert got["canonical_byte_digest"] == exp["canonical_byte_digest"]
        assert got["unit_tag"] == exp["unit_tag"]
        assert got["cache_epoch"] == exp["cache_epoch"]
        assert got["seal_window"] == exp["seal_window"]


def _prior_e3_p7_line() -> tuple[str, str]:
    """Build a surviving GEN=1 p7 journal line for e3-canary from public fixtures."""
    slice_kv = _slice_map()
    item = json.loads((SETS / "e3.json").read_text(encoding="utf-8"))[0]
    base = _base_tag(item, False, slice_kv["ANNEX_PREFIX"], slice_kv["ORDER"])
    body = f"GEN=1|BAND=p7|BODY={base}"
    return body, body + "\n"


def test_surviving_prior_line_continues_lineage() -> None:
    """A complete prior journal line survives mend and salts later digests via parent_tip."""
    prior_body, prior_line = _prior_e3_p7_line()
    prior_tip = _tip_chain(prior_line)
    want = _replay_rows(prior_journals={"e3-canary": prior_body})
    _wipe()
    _bake()
    planted = STAGE / "journal" / "e3-canary.frames"
    planted.write_text(prior_line, encoding="utf-8")
    cert = _drive()
    assert cert["violations"] == 0
    frames = planted.read_text(encoding="utf-8").splitlines()
    assert frames[0] == prior_body
    assert frames[1].startswith("GEN=2|")
    assert "|BAND=p7|" in frames[1]
    assert "|BODY=" in frames[1]
    e3 = [r for r in cert["rows"] if r["manifest_id"] == "e3-canary"]
    exp = [r for r in want if r["manifest_id"] == "e3-canary"]
    assert len(e3) == len(exp)
    assert exp[0]["parent_tip"] == prior_tip
    assert "rev=2" in exp[0]["unit_tag"]
    for got, target in zip(e3, exp, strict=True):
        assert got["unit_tag"] == target["unit_tag"]
        assert got["canonical_byte_digest"] == target["canonical_byte_digest"]
        assert got["journal_tip_hex"] == target["journal_tip_hex"]
        assert got["cache_epoch"] == target["cache_epoch"]
        assert got["seal_window"] == target["seal_window"]
    # Unsalted or empty-parent implementations diverge once lineage exists.
    assert e3[0]["canonical_byte_digest"] != _unsalted_digest(exp[0], prior_tip)


def test_wipe_replay_byte_stability() -> None:
    """Triple wipe+emit keeps digests, tips, and windows byte-stable."""
    want = _replay_rows()
    a = _certify()["rows"]
    b = _certify()["rows"]
    c = _certify()["rows"]
    assert len(a) == len(want)
    for i, exp in enumerate(want):
        assert a[i]["canonical_byte_digest"] == b[i]["canonical_byte_digest"] == c[i]["canonical_byte_digest"] == exp["canonical_byte_digest"]
        assert a[i]["journal_tip_hex"] == b[i]["journal_tip_hex"] == c[i]["journal_tip_hex"] == exp["journal_tip_hex"]
        assert a[i]["seal_window"] == b[i]["seal_window"] == c[i]["seal_window"] == exp["seal_window"]
        assert a[i]["cache_epoch"] == b[i]["cache_epoch"] == c[i]["cache_epoch"] == exp["cache_epoch"]
        assert a[i]["unit_tag"] == b[i]["unit_tag"] == c[i]["unit_tag"] == exp["unit_tag"]


def test_cache_kv_and_journal_hygiene() -> None:
    """Durable cache kv files and GEN fences stay coherent with certificate rows."""
    want = _replay_rows()
    cert = _certify()
    assert any((STAGE / "journal").glob("*.frames"))
    assert any((STAGE / "cache").glob("*.kv"))
    q3 = json.loads((ENV / "fixtures" / "q_counts" / "q3.json").read_text(encoding="utf-8"))
    assert isinstance(q3, dict)
    assert cert["violations"] == 0
    assert len(cert["rows"]) == len(want)
    for row, exp in zip(cert["rows"], want, strict=True):
        mid = row["manifest_id"]
        jpath = STAGE / "journal" / f"{mid}.frames"
        cpath = STAGE / "cache" / f"{mid}.kv"
        lines = jpath.read_text(encoding="utf-8").splitlines()
        assert len(lines) >= 1
        for idx, line in enumerate(lines, start=1):
            assert line.startswith(f"GEN={idx}|BAND=")
            assert "|BODY=" in line
        blob = cpath.read_text(encoding="utf-8")
        assert "EPOCH=" in blob
        assert "ANNEX_LAST=" in blob
        assert "WINDOW_LAST=" in blob
        assert row["canonical_byte_digest"] == exp["canonical_byte_digest"]
        assert row["journal_tip_hex"] == exp["journal_tip_hex"]
        assert row["unit_tag"] == exp["unit_tag"]
        assert row["cache_epoch"] == exp["cache_epoch"]
        assert row["seal_window"] == exp["seal_window"]
        assert row["journal_tip_hex"] != row["canonical_byte_digest"][:8]


def _stage_bytes() -> dict[str, bytes]:
    return {
        str(path.relative_to(STAGE)): path.read_bytes()
        for path in sorted(STAGE.rglob("*"))
        if path.is_file()
    }


def test_unchanged_snapshot_is_stage_noop() -> None:
    """An identical emit restores output without replaying durable state."""
    first = _certify()
    before = _stage_bytes()
    OUT.unlink()
    second = _drive()
    assert second == first
    assert OUT.exists()
    assert _stage_bytes() == before


def _committed_replay_state() -> tuple[
    dict[str, str], dict[str, tuple[int, int, int]]
]:
    initial_want = _replay_rows()
    prior_journals = {
        path.stem: path.read_text(encoding="utf-8")
        for path in (STAGE / "journal").glob("*.frames")
    }
    prior_cache: dict[str, tuple[int, int, int]] = {}
    for row in initial_want:
        prior_cache[row["manifest_id"]] = (
            1 if row["scope_band"] == "p8" else 0,
            row["seal_window"],
            row["cache_epoch"],
        )
    return prior_journals, prior_cache


def _changed_matrix(tmp_path: Path) -> Path:
    changed = json.loads((SETS / "e3.json").read_text(encoding="utf-8"))
    changed[0]["labels"]["rollout"] = "v2"
    matrix = tmp_path / "matrix"
    matrix.mkdir()
    (matrix / "e3.json").write_text(json.dumps(changed), encoding="utf-8")
    return matrix


def _escaped_matrix(tmp_path: Path) -> Path:
    matrix = tmp_path / "matrix"
    matrix.mkdir()
    item = {
        "manifest_id": "json-edge",
        "name": "quoted-watcher",
        "namespace": "edge",
        "labels": {
            "path": r"C:\static\pods",
            "quote": 'say "proceed"',
            "rollout": "blue}canary",
        },
        "annotations": {
            "q46.note": r"brace{kept}\quoted",
            "other.note": "excluded",
        },
    }
    # Compact encoding ensures braces and escaped quotes occur inside the object
    # scanner's input rather than being hidden by line-oriented formatting.
    (matrix / "e3.json").write_text(
        json.dumps([item], ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return matrix


def test_changed_snapshot_continues_then_stabilizes(tmp_path: Path) -> None:
    """Changed content advances lineage once; its immediate replay is a no-op."""
    _certify()
    prior_journals, prior_cache = _committed_replay_state()
    matrix = _changed_matrix(tmp_path)
    want = _replay_rows(
        matrix_dir=matrix,
        prior_journals=prior_journals,
        prior_cache=prior_cache,
    )
    got = _drive(matrix)
    assert got["violations"] == 0
    assert len(got["rows"]) == len(want)
    for row, exp in zip(got["rows"], want, strict=True):
        assert row["manifest_id"] == exp["manifest_id"]
        assert row["scope_band"] == exp["scope_band"]
        assert row["unit_tag"] == exp["unit_tag"]
        assert row["canonical_byte_digest"] == exp["canonical_byte_digest"]
        assert row["cache_epoch"] == exp["cache_epoch"]
        assert row["journal_tip_hex"] == exp["journal_tip_hex"]
        assert row["seal_window"] == exp["seal_window"]

    assert [row["gen"] for row in want] == [3, 4]
    before = _stage_bytes()
    OUT.unlink()
    repeated = _drive(matrix)
    assert repeated == got
    assert _stage_bytes() == before


def test_json_string_boundaries_survive_snapshot_reduction(tmp_path: Path) -> None:
    """JSON string escapes and braces are data, not object framing."""
    _certify()
    prior_journals, prior_cache = _committed_replay_state()
    matrix = _escaped_matrix(tmp_path)
    want = _replay_rows(
        matrix_dir=matrix,
        prior_journals=prior_journals,
        prior_cache=prior_cache,
    )
    got = _drive(matrix)
    assert got["violations"] == 0
    assert len(got["rows"]) == 2
    assert len(want) == 2
    for row, exp in zip(got["rows"], want, strict=True):
        assert row["manifest_id"] == exp["manifest_id"]
        assert row["unit_tag"] == exp["unit_tag"]
        assert row["canonical_byte_digest"] == exp["canonical_byte_digest"]
        assert row["cache_epoch"] == exp["cache_epoch"]
        assert row["journal_tip_hex"] == exp["journal_tip_hex"]
        assert row["seal_window"] == exp["seal_window"]


def test_failed_snapshot_rolls_back_before_retry(tmp_path: Path) -> None:
    """Injected partial work cannot become durable lineage on the retry."""
    original = _certify()
    original_output = OUT.read_bytes()
    original_stage = _stage_bytes()
    prior_journals, prior_cache = _committed_replay_state()
    matrix = _changed_matrix(tmp_path)
    want = _replay_rows(
        matrix_dir=matrix,
        prior_journals=prior_journals,
        prior_cache=prior_cache,
    )

    failed = _run_drive(matrix, extra_env={"SPW_FAIL_AFTER_ROWS": "1"})
    assert failed.returncode == 86
    assert OUT.read_bytes() == original_output
    assert (STAGE / ".txn").is_dir()
    assert _stage_bytes() != original_stage

    recovered = _drive(matrix)
    assert recovered["violations"] == 0
    assert not (STAGE / ".txn").exists()
    assert recovered != original
    for row, exp in zip(recovered["rows"], want, strict=True):
        assert row["unit_tag"] == exp["unit_tag"]
        assert row["canonical_byte_digest"] == exp["canonical_byte_digest"]
        assert row["cache_epoch"] == exp["cache_epoch"]
        assert row["journal_tip_hex"] == exp["journal_tip_hex"]
        assert row["seal_window"] == exp["seal_window"]
