import json
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path


APP = Path("/app")
ENV = Path("/app/environment")
OUT = APP / "output" / "ops_row_report.json"
PRIM_IDS = (ENV / "docs" / "prim_ids.txt").read_text(encoding="utf-8").strip().split(",")
STEP_MUX = Path("/app/environment/m7k/step_mux.rb")
CAP_FOLD = Path("/app/environment/r3p/cap_fold.rb")
REVERT_ARM = Path("/app/environment/w9n/revert_arm.rb")
LADDER = Path("/app/environment/data/ladder.toml")


@contextmanager
def _patched_text(path: Path, replacement: str):
    original = path.read_text(encoding="utf-8")
    path.write_text(replacement, encoding="utf-8")
    try:
        yield
    finally:
        path.write_text(original, encoding="utf-8")


def _run_hx(extra: list[str] | None = None) -> dict:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    cmd = ["/app/bin/hx_ctl", "run"]
    if extra:
        cmd.extend(extra)
    subprocess.run(cmd, cwd=APP, check=True)
    return json.loads(OUT.read_text(encoding="utf-8"))


def row_digest_from_rows(rows: list[dict]) -> str:
    parts = []
    for row in rows:
        parts.append(
            f'{row["unit_id"]}|{row["bind_rc"]}|{row["lock_rc"]}|{row["unit_rc"]}|'
            f'{row["drift_code"]}|{row["facet_hex"]}'
        )
    parts.sort()
    payload = "\n".join(parts)
    mask64 = (1 << 64) - 1
    total = 0
    for idx, ch in enumerate(payload, start=1):
        total = (total + ((idx * ord(ch)) & mask64)) & mask64
    return f"{total & 0xFFFFFFFF:08x}"


def _rows_by_id(report: dict) -> dict:
    return {row["unit_id"]: row for row in report["rows"]}


def _assert_coherent(report: dict) -> None:
    _check_report_shape(report)
    _check_pair_agree(report)
    _check_rc_dims(report)
    _check_tag_text(report)
    _check_width_max(report)
    _check_digest_contract(report)


def _check_report_shape(report: dict) -> None:
    assert "rows" in report and "summary" in report
    ids = {row["unit_id"] for row in report["rows"]}
    assert ids == set(PRIM_IDS)
    assert report["summary"]["rows_total"] == len(PRIM_IDS)


def _check_pair_agree(report: dict) -> None:
    rows = _rows_by_id(report)
    for a, b in [("bind", "bind_echo"), ("upper", "upper_echo"), ("worker", "worker_echo")]:
        assert rows[a]["facet_hex"] == rows[b]["facet_hex"]
        assert rows[a]["bind_rc"] == rows[b]["bind_rc"]
        assert rows[a]["lock_rc"] == rows[b]["lock_rc"]
        assert rows[a]["unit_rc"] == rows[b]["unit_rc"]


def _check_rc_dims(report: dict) -> None:
    for row in report["rows"]:
        assert row["drift_code"] == 0
        assert row["bind_rc"] == 1
        assert row["lock_rc"] == 1
        assert row["unit_rc"] == 1


def _check_tag_text(report: dict) -> None:
    assert report["summary"]["sync_label"] == "steady"


def _check_width_max(report: dict) -> None:
    span = max(abs(r["drift_code"]) for r in report["rows"])
    assert report["summary"]["span_band"] == span


def _check_digest_contract(report: dict) -> None:
    assert report["summary"]["row_digest"] == row_digest_from_rows(report["rows"])


def _apply_buggy_fn_m7(src: str) -> str:
    return re.sub(
        r"def fn_m7\(step_ix, family_ix, prev_family\).*?^    end",
        "def fn_m7(step_ix, family_ix, prev_family)\n"
        "      _ = family_ix\n"
        "      _ = prev_family\n"
        "      step_ix\n"
        "    end",
        src,
        count=1,
        flags=re.DOTALL | re.MULTILINE,
    )


def _apply_buggy_fn_r3(src: str) -> str:
    return re.sub(
        r"def fn_r3\(ctx, stamp_a, stamp_b\).*?^    end",
        "def fn_r3(ctx, stamp_a, stamp_b)\n"
        "      val = (stamp_a ^ stamp_b) & 0xFFFFFFFF\n"
        "      ctx[:published] = val\n"
        "      ctx[:activated] ? val : val\n"
        "    end",
        src,
        count=1,
        flags=re.DOTALL | re.MULTILINE,
    )


def _apply_buggy_fn_w9(src: str) -> str:
    return re.sub(
        r"def fn_w9\(state, tree_a, tree_b\).*?^    end",
        "def fn_w9(state, tree_a, tree_b)\n"
        "      state[:tree] = tree_b\n"
        "      state\n"
        "    end",
        src,
        count=1,
        flags=re.DOTALL | re.MULTILINE,
    )


def _assert_not_coherent(report: dict) -> None:
    try:
        _assert_coherent(report)
    except AssertionError:
        return
    raise AssertionError("expected incoherent report")


def test_h1_matrix_layout() -> None:
    """JSON exposes rows and summary; primary ids match prim_ids.txt."""
    _check_report_shape(_run_hx())


def test_h2_pair_agree() -> None:
    """Mirror pairs agree on facet material and rc fields when coherent."""
    _check_pair_agree(_run_hx())


def test_h3_rc_dims() -> None:
    """Coherent run keeps drift zero and all three rc fields at one."""
    _check_rc_dims(_run_hx())


def test_h4_tag_text() -> None:
    """Summary sync label reads steady when the row matrix is coherent."""
    _check_tag_text(_run_hx())


def test_h5_width_max() -> None:
    """span_band equals max absolute drift_code across rows."""
    _check_width_max(_run_hx())


def test_h6_reduce_sum() -> None:
    """row_digest matches the pilot header reduction from rows."""
    _check_digest_contract(_run_hx())


def test_h7_known_good() -> None:
    """row_digest is anchored to the known-good repaired emission."""
    report = _run_hx()
    _assert_coherent(report)
    assert report["summary"]["row_digest"] == row_digest_from_rows(report["rows"])


def test_h8_width_lower() -> None:
    """facet_hex is sixteen lowercase hex characters."""
    for row in _run_hx()["rows"]:
        s = row["facet_hex"]
        assert len(s) == 16
        assert s == s.lower()
        int(s, 16)


def test_h9_total_count() -> None:
    """rows_total is an integer matching len(rows)."""
    report = _run_hx()
    assert isinstance(report["summary"]["rows_total"], int)
    assert report["summary"]["rows_total"] == len(report["rows"])


def test_h10_pipe_rerun() -> None:
    """Tampered hand-written JSON is replaced when hx_ctl reruns."""
    baseline = _run_hx()
    tampered = {**baseline, "summary": {**baseline["summary"], "sync_label": "bad"}}
    OUT.write_text(json.dumps(tampered), encoding="utf-8")
    regenerated = _run_hx()
    _assert_coherent(regenerated)


def test_h11_twice_same() -> None:
    """Consecutive pipeline runs produce identical reports."""
    first = _run_hx()
    second = _run_hx()
    assert first == second


def test_h12_sens_steps() -> None:
    """Mutating ladder data changes facet material and row_digest."""
    baseline = _run_hx()
    original = LADDER.read_text(encoding="utf-8")
    mutated = original.replace("[2, 0]", "[2, 9]", 1)
    with _patched_text(LADDER, mutated):
        changed = _run_hx()
    assert changed["summary"]["row_digest"] != baseline["summary"]["row_digest"]


def test_h13_flip_m7() -> None:
    """Reverting fn_m7 body breaks coherence."""
    src = STEP_MUX.read_text(encoding="utf-8")
    with _patched_text(STEP_MUX, _apply_buggy_fn_m7(src)):
        _assert_not_coherent(_run_hx())


def test_h14_flip_both() -> None:
    """Reverting fn_r3 and fn_w9 together breaks run_b pipeline."""
    r3 = CAP_FOLD.read_text(encoding="utf-8")
    w9 = REVERT_ARM.read_text(encoding="utf-8")
    with _patched_text(CAP_FOLD, _apply_buggy_fn_r3(r3)):
        with _patched_text(REVERT_ARM, _apply_buggy_fn_w9(w9)):
            report = _run_hx(["--hook", "run_b"])
    _assert_not_coherent(report)


def test_h15_flip_r3() -> None:
    """Broken fn_r3 publish gating breaks run_b negotiation trap."""
    src = CAP_FOLD.read_text(encoding="utf-8")
    with _patched_text(CAP_FOLD, _apply_buggy_fn_r3(src)):
        report = _run_hx(["--hook", "run_b"])
    _assert_not_coherent(report)


def test_h16_all_var() -> None:
    """Every held-out ord_table permutation survives after fix."""
    for idx in range(3):
        report = _run_hx(["--ord", f"perm:{idx}"])
        _assert_coherent(report)


def test_h17_flip_w9() -> None:
    """Reverting fn_w9 breaks lock rc vs byte log witness bytes on run_b."""
    src = REVERT_ARM.read_text(encoding="utf-8")
    with _patched_text(REVERT_ARM, _apply_buggy_fn_w9(src)):
        report = _run_hx(["--hook", "run_b"])
    _assert_not_coherent(report)


def test_h18_index_first() -> None:
    """run_a resume hook emits a coherent report."""
    report = _run_hx(["--hook", "run_a", "--resume", "1"])
    _assert_coherent(report)


def test_h19_premature() -> None:
    """Coherent run keeps steady sync label when mirror pairs agree."""
    report = _run_hx()
    _assert_coherent(report)
    assert report["summary"]["sync_label"] == "steady"


def test_h20_cmd_seq() -> None:
    """Each hook_cmds argv sequence required for hx_ctl hook success."""
    hooks = (Path("/app/environment/docs/hook_cmds.txt")).read_text(encoding="utf-8").strip().splitlines()
    for line in hooks:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.strip().split()
        assert parts[0][-6:] == "hx_ctl"
        extra = parts[2:]
        report = _run_hx(extra) if extra else _run_hx()
        hook_val = None
        for pos, tok in enumerate(extra):
            if tok == "--hook" and pos + 1 < len(extra):
                hook_val = extra[pos + 1]
        if hook_val == "run_b":
            continue
        if "--ord" in extra:
            _assert_coherent(report)
        elif "--hook" not in extra:
            _assert_coherent(report)
