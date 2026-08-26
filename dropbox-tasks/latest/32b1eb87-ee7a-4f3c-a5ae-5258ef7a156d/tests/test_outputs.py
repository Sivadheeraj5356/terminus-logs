"""Verifier for netplan-config-staleness observation pipeline."""

import json
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
OUT = APP / "output" / "n8_observations.json"
STATE = APP / "state"
LANE_STATE = STATE / "lane_ctx.dat"
OBS_ACCUM = STATE / "obs_accum.dat"

ROW_KEYS = frozenset(
    {
        "batch",
        "key",
        "gen",
        "gate_code",
        "cfg_mask",
        "sample_mask",
        "live_mask",
        "lane_digest",
    }
)
TOP_KEYS = frozenset({"profile", "rows", "lane_digest"})

BATCH_PLAN: list[tuple[str, str | None, bool]] = [
    ("w00", None, True),
    ("w01", "r_row_a", False),
    ("w02", "r_row_b", False),
    ("w03", "r_row_c", False),
    ("w04", "r_row_a2", False),
    ("w05", "r_row_b2", False),
    ("w06", "r_row_c2", False),
    ("w07", "r_row_a3", False),
    ("w08", "r_row_b3", False),
]

# Per-row expectations derived from fixtures and baseline warm rows.
# carrier=down rows reconcile to zero masks after carrier teardown.
EXPECTED_ROWS: list[tuple[str, str, int, str, int, int, int]] = [
    ("w00", "k0", 1, "A", 0x0A000001, 0x0A000001, 0x0A000001),
    ("w00", "k1", 1, "A", 0x0A000002, 0x0A000002, 0x0A000002),
    ("w01", "k_a", 1, "A", 0x0A010101, 0x0A010101, 0x0A010101),
    ("w01", "k_a", 2, "A", 0x0A010202, 0x0A010202, 0x0A010202),
    ("w02", "k_b", 1, "A", 0x0A020101, 0x0A020101, 0x0A020101),
    ("w02", "k_b", 2, "A", 0x0A020202, 0x0A020202, 0x0A020202),
    ("w02", "k_b", 3, "A", 0x0A020303, 0x0A020303, 0x0A020303),
    ("w03", "k_c", 1, "A", 0x0A030101, 0x0A030101, 0x0A030101),
    ("w03", "k_c", 2, "A", 0, 0, 0),
    ("w04", "k_a", 3, "A", 0x0A010303, 0x0A010303, 0x0A010303),
    ("w04", "k_a", 4, "A", 0x0A010404, 0x0A010404, 0x0A010404),
    ("w05", "k_b", 4, "A", 0x0A020404, 0x0A020404, 0x0A020404),
    ("w05", "k_b", 5, "A", 0x0A020505, 0x0A020505, 0x0A020505),
    ("w05", "k_b", 6, "A", 0x0A020606, 0x0A020606, 0x0A020606),
    ("w06", "k_c", 3, "A", 0x0A030303, 0x0A030303, 0x0A030303),
    ("w06", "k_c", 4, "A", 0, 0, 0),
    ("w07", "k_a", 5, "A", 0x0A010505, 0x0A010505, 0x0A010505),
    ("w07", "k_a", 6, "A", 0x0A010606, 0x0A010606, 0x0A010606),
    ("w08", "k_b", 7, "A", 0x0A020707, 0x0A020707, 0x0A020707),
    ("w08", "k_b", 8, "A", 0x0A020808, 0x0A020808, 0x0A020808),
    ("w08", "k_b", 9, "A", 0x0A020909, 0x0A020909, 0x0A020909),
]

# Final live lane entries after the full replay sequence: gen, cfg, sample, live.
EXPECTED_LANE: dict[str, tuple[int, int, int, int]] = {
    "k0": (1, 0x0A000001, 0x0A000001, 0x0A000001),
    "k1": (1, 0x0A000002, 0x0A000002, 0x0A000002),
    "k_a": (6, 0x0A010606, 0x0A010606, 0x0A010606),
    "k_b": (9, 0x0A020909, 0x0A020909, 0x0A020909),
    "k_c": (4, 0, 0, 0),
}

# LaneEntry / ListSnap layouts from environment/include/lane_ctx.h (x86_64/gcc).
# LANE_KEY_MAX=16, LANE_ROW_CAP=32; field widths follow the header order.
_KEY_MAX = 16
_ROW_CAP = 32
_U32 = 4
_LANE_ENTRY_SIZE = (
    _KEY_MAX
    + _U32  # gen
    + _U32  # cfg_mask
    + _U32  # sample_mask
    + _U32  # live_mask
    + _U32  # stamp
    + _U32  # reconfig_done
    + _U32  # reconfig_pending
    + _U32  # carrier_ticks
    + _U32  # link_up
    + _U32  # listing_cache_valid
    + _U32  # cached_listing_mask
)
_LANE_CTX_N_ROWS_OFF = _LANE_ENTRY_SIZE * _ROW_CAP
_LIST_SNAP_SIZE = (
    _U32  # n
    + _ROW_CAP * _KEY_MAX  # batches
    + _ROW_CAP * _KEY_MAX  # keys
    + _ROW_CAP * _U32  # gens
    + _ROW_CAP * _U32  # cfg_masks
    + _ROW_CAP * _U32  # sample_masks
    + _ROW_CAP * _U32  # live_masks
    + _ROW_CAP  # gate_codes
)


def _u32(data: bytes, off: int) -> int:
    return int.from_bytes(data[off : off + 4], "little")


def _i32(data: bytes, off: int) -> int:
    return int.from_bytes(data[off : off + 4], "little", signed=True)


def _cstr16(data: bytes, off: int) -> str:
    return data[off : off + 16].split(b"\x00", 1)[0].decode()


def _fnv32_step(h: int, v: int) -> int:
    h ^= v & 0xFFFFFFFF
    return (h * 16777619) & 0xFFFFFFFF


def _fnv32_bytes(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h = _fnv32_step(h, b)
    return h & 0xFFFFFFFF


def _row_digest(key: str, gen: int, cfg: int, sample: int, live: int, gate: str) -> int:
    h = _fnv32_bytes(key.encode())
    h = _fnv32_step(h, gen)
    h = _fnv32_step(h, cfg)
    h = _fnv32_step(h, sample)
    h = _fnv32_step(h, live)
    h = _fnv32_step(h, ord(gate))
    return h


def _bundle_digest(rows: list[dict[str, object]]) -> int:
    payload = "".join(
        f"{r['batch']}:{r['gen']}:{r['cfg_mask']}:{r['sample_mask']}:"
        f"{r['live_mask']}:{r['gate_code']};"
        for r in rows
    )
    return _fnv32_bytes(payload.encode())


def _rebuild_lab() -> None:
    subprocess.run(
        ["make", "-C", "/app/environment", "-j2"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _scrub_outputs() -> None:
    if OUT.exists():
        OUT.unlink()
    for path in (LANE_STATE, OBS_ACCUM):
        if path.exists():
            path.unlink()


def _run_batch(batch: str, fixture: str | None, reset: bool) -> None:
    cmd = ["/app/tools/n2_driver"]
    if reset:
        cmd.append("--reset")
    cmd.extend(["--batch", batch])
    if fixture:
        cmd.extend(["--fixture", fixture])
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _run_pipeline() -> dict[str, object]:
    _rebuild_lab()
    _scrub_outputs()
    STATE.mkdir(parents=True, exist_ok=True)
    (APP / "output").mkdir(parents=True, exist_ok=True)
    for batch, fixture, reset in BATCH_PLAN:
        _run_batch(batch, fixture, reset)
    subprocess.run(["/app/tools/w8_emit"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert OUT.exists(), "n8_observations.json missing after w8_emit"
    assert LANE_STATE.exists(), "lane_ctx.dat missing after replay"
    assert OBS_ACCUM.exists(), "obs_accum.dat missing after replay"
    return json.loads(OUT.read_text())


def _rows_by_batch(obs: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in obs["rows"]:  # type: ignore[index]
        grouped.setdefault(str(row["batch"]), []).append(row)  # type: ignore[arg-type]
    return grouped


_OFF_GEN = _KEY_MAX
_OFF_CFG = _OFF_GEN + _U32
_OFF_SAMPLE = _OFF_CFG + _U32
_OFF_LIVE = _OFF_SAMPLE + _U32
_OFF_BATCHES = _U32
_OFF_KEYS = _OFF_BATCHES + _ROW_CAP * _KEY_MAX
_OFF_GENS = _OFF_KEYS + _ROW_CAP * _KEY_MAX
_OFF_CFGS = _OFF_GENS + _ROW_CAP * _U32
_OFF_SAMPLES = _OFF_CFGS + _ROW_CAP * _U32
_OFF_LIVES = _OFF_SAMPLES + _ROW_CAP * _U32
_OFF_GATES = _OFF_LIVES + _ROW_CAP * _U32


def _load_lane_entries() -> dict[str, dict[str, int]]:
    data = LANE_STATE.read_bytes()
    assert len(data) >= _LANE_CTX_N_ROWS_OFF + _U32
    n_rows = _i32(data, _LANE_CTX_N_ROWS_OFF)
    assert 0 < n_rows <= _ROW_CAP
    entries: dict[str, dict[str, int]] = {}
    for i in range(n_rows):
        base = i * _LANE_ENTRY_SIZE
        key = _cstr16(data, base)
        entries[key] = {
            "gen": _u32(data, base + _OFF_GEN),
            "cfg_mask": _u32(data, base + _OFF_CFG),
            "sample_mask": _u32(data, base + _OFF_SAMPLE),
            "live_mask": _u32(data, base + _OFF_LIVE),
        }
    return entries


def _load_obs_accum() -> list[dict[str, object]]:
    data = OBS_ACCUM.read_bytes()
    rows: list[dict[str, object]] = []
    off = 0
    while off + _LIST_SNAP_SIZE <= len(data):
        n = _i32(data, off)
        if n >= 1:
            rows.append(
                {
                    "batch": _cstr16(data, off + _OFF_BATCHES),
                    "key": _cstr16(data, off + _OFF_KEYS),
                    "gen": _u32(data, off + _OFF_GENS),
                    "cfg_mask": _u32(data, off + _OFF_CFGS),
                    "sample_mask": _u32(data, off + _OFF_SAMPLES),
                    "live_mask": _u32(data, off + _OFF_LIVES),
                    "gate_code": chr(data[off + _OFF_GATES]),
                }
            )
        off += _LIST_SNAP_SIZE
    return rows


def _assert_schema(obs: dict[str, object]) -> None:
    assert frozenset(obs.keys()) == TOP_KEYS
    assert obs["profile"] == "concurrency_ordering"
    rows = obs["rows"]
    assert isinstance(rows, list) and rows
    for row in rows:
        assert isinstance(row, dict)
        assert frozenset(row.keys()) == ROW_KEYS
        assert row["gate_code"] in {"A", "D"}
        assert str(row["lane_digest"]).startswith("0x")
        expect = _row_digest(
            str(row["key"]),
            int(row["gen"]),
            int(row["cfg_mask"]),
            int(row["sample_mask"]),
            int(row["live_mask"]),
            str(row["gate_code"]),
        )
        assert row["lane_digest"] == f"0x{expect:08x}"
    bundle = _bundle_digest(rows)  # type: ignore[arg-type]
    assert obs["lane_digest"] == f"0x{bundle:08x}"


def _assert_expected_rows(obs: dict[str, object]) -> None:
    rows = obs["rows"]
    assert isinstance(rows, list)
    assert len(rows) == len(EXPECTED_ROWS)
    for row, expect in zip(rows, EXPECTED_ROWS, strict=True):
        batch, key, gen, gate, cfg, sample, live = expect
        assert row["batch"] == batch
        assert row["key"] == key
        assert int(row["gen"]) == gen
        assert row["gate_code"] == gate
        assert int(row["cfg_mask"]) == cfg
        assert int(row["sample_mask"]) == sample
        assert int(row["live_mask"]) == live


def _assert_lane_live_state() -> None:
    entries = _load_lane_entries()
    for key, (gen, cfg, sample, live) in EXPECTED_LANE.items():
        assert key in entries, f"missing live lane entry for {key}"
        entry = entries[key]
        assert entry["gen"] == gen
        assert entry["cfg_mask"] == cfg
        assert entry["sample_mask"] == sample
        assert entry["live_mask"] == live


def _assert_obs_accum_matches_json(obs: dict[str, object]) -> None:
    accum = _load_obs_accum()
    rows = obs["rows"]
    assert isinstance(rows, list)
    assert len(accum) == len(rows)
    for recorded, emitted in zip(accum, rows, strict=True):
        assert recorded["batch"] == emitted["batch"]
        assert recorded["key"] == emitted["key"]
        assert int(recorded["gen"]) == int(emitted["gen"])
        assert recorded["gate_code"] == emitted["gate_code"]
        # Emit must surface the live probe captured during replay, not invent masks.
        assert int(recorded["live_mask"]) == int(emitted["live_mask"])
        assert int(recorded["cfg_mask"]) == int(emitted["cfg_mask"])
        assert int(recorded["sample_mask"]) == int(emitted["sample_mask"])


def _assert_latest_rows_match_lane(obs: dict[str, object]) -> None:
    entries = _load_lane_entries()
    latest: dict[str, dict[str, object]] = {}
    for row in obs["rows"]:  # type: ignore[index]
        key = str(row["key"])
        prev = latest.get(key)
        if prev is None or int(row["gen"]) >= int(prev["gen"]):  # type: ignore[index]
            latest[key] = row  # type: ignore[assignment]
    for key, (gen, cfg, sample, live) in EXPECTED_LANE.items():
        row = latest[key]
        assert int(row["gen"]) == gen
        assert int(row["cfg_mask"]) == cfg
        assert int(row["sample_mask"]) == sample
        assert int(row["live_mask"]) == live
        entry = entries[key]
        assert entry["live_mask"] == int(row["live_mask"])
        assert entry["cfg_mask"] == int(row["cfg_mask"])
        assert entry["sample_mask"] == int(row["sample_mask"])


@pytest.fixture(autouse=True)
def _isolate_state() -> None:
    _scrub_outputs()
    yield
    _scrub_outputs()


def test_w00_a() -> None:
    """Full pipeline emits fixture-exact masks and digests, not merely equal columns."""
    obs = _run_pipeline()
    _assert_schema(obs)
    _assert_expected_rows(obs)


def test_w01_b() -> None:
    """Stamp-early w01 rows keep generation-specific live probes from r_row_a."""
    obs = _run_pipeline()
    stamp_rows = _rows_by_batch(obs)["w01"]
    assert [(r["gen"], int(r["live_mask"])) for r in stamp_rows] == [
        (1, 0x0A010101),
        (2, 0x0A010202),
    ]
    assert all(r["gate_code"] == "A" for r in stamp_rows)


def test_w02_c() -> None:
    """Rapid-apply w02 final row is generation 3 with live probe 0x0a020303."""
    obs = _run_pipeline()
    rapid_rows = _rows_by_batch(obs)["w02"]
    assert len(rapid_rows) == 3
    last = rapid_rows[-1]
    assert last["gate_code"] == "A"
    assert int(last["gen"]) == 3
    assert int(last["live_mask"]) == 0x0A020303
    assert int(last["cfg_mask"]) == int(last["sample_mask"]) == 0x0A020303


def test_w03_d() -> None:
    """Carrier-delay w03 final row reconciles to accepted zero masks after teardown."""
    obs = _run_pipeline()
    carrier_rows = _rows_by_batch(obs)["w03"]
    assert len(carrier_rows) == 2
    first, final = carrier_rows
    assert first["gate_code"] == "A"
    assert int(first["live_mask"]) == 0x0A030101
    assert final["gate_code"] == "A"
    assert int(final["cfg_mask"]) == int(final["sample_mask"]) == int(final["live_mask"]) == 0


def test_w04_e() -> None:
    """Live lane_ctx state matches the latest applied generation per key."""
    _run_pipeline()
    _assert_lane_live_state()


def test_w05_f() -> None:
    """Observation accumulator live probes match emitted JSON row-for-row."""
    obs = _run_pipeline()
    _assert_obs_accum_matches_json(obs)


def test_w06_g() -> None:
    """Latest emitted row per key agrees with live lane probe state."""
    obs = _run_pipeline()
    _assert_latest_rows_match_lane(obs)


def test_w07_h() -> None:
    """Idempotent full-pipeline replay preserves correct bundle digest and live lane state."""
    first = _run_pipeline()
    _assert_expected_rows(first)
    _assert_lane_live_state()
    lane_a = _load_lane_entries()
    digest = first["lane_digest"]
    _scrub_outputs()
    second = _run_pipeline()
    assert second["lane_digest"] == digest
    _assert_expected_rows(second)
    assert _load_lane_entries() == lane_a


def test_w08_i() -> None:
    """Continuation batches carry fixture-exact live masks, including carrier teardown zeros."""
    obs = _run_pipeline()
    grouped = _rows_by_batch(obs)
    assert [(int(r["gen"]), int(r["live_mask"])) for r in grouped["w04"]] == [
        (3, 0x0A010303),
        (4, 0x0A010404),
    ]
    assert [(int(r["gen"]), int(r["live_mask"])) for r in grouped["w05"]] == [
        (4, 0x0A020404),
        (5, 0x0A020505),
        (6, 0x0A020606),
    ]
    assert [(int(r["gen"]), int(r["live_mask"]), r["gate_code"]) for r in grouped["w06"]] == [
        (3, 0x0A030303, "A"),
        (4, 0, "A"),
    ]
    assert [(int(r["gen"]), int(r["live_mask"])) for r in grouped["w07"]] == [
        (5, 0x0A010505),
        (6, 0x0A010606),
    ]
    assert [(int(r["gen"]), int(r["live_mask"])) for r in grouped["w08"]] == [
        (7, 0x0A020707),
        (8, 0x0A020808),
        (9, 0x0A020909),
    ]
