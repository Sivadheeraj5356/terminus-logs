"""Verifier for transit photometry depth restart parity."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

APP = Path("/app")
OUT = APP / "output"
REPORT = OUT / "depth_report.json"
TRANSCRIPT = OUT / "matrix.transcript"
LEGACY = APP / "legacy" / "fresh_lane.txt"
RUN = APP / "scripts" / "run_desk.sh"
REF = Path("/opt/verifier/ref-depth")
REF_AGENT = APP / "scripts" / "ref-depth"
LEGACY_BIN = Path("/opt/verifier/legacy")

FOLD = APP / "zknot" / "meld_q.go"
PORT = APP / "xvox" / "stash_p.go"
RIM = APP / "knotr" / "rim_z.go"

MELD_PACKS = ["trap01", "warmj"]
SITE_PACKS = ["nept", "hotspot"]
RING_PACKS = ["graze", "quiet"]
PACK_ORDER = MELD_PACKS + SITE_PACKS + RING_PACKS

ROW_FIELDS = {
    "pack",
    "fresh_depth",
    "resumed_depth",
    "second_depth",
    "residual_fresh",
    "residual_resumed",
    "depth_parity_ok",
    "dual_resume_ok",
}

BROKEN_FOLD = r'''package zknot

import "desk/phase"

func makeInt64(n int) []int64 {
	out := []int64{}
	for i := 0; i < n; i++ {
		out = append(out, 0)
	}
	return out
}
func makeInt64Cap(n int) []int64 {
	out := []int64{}
	for i := 0; i < n; i++ {
		_ = i
	}
	return out
}
func makeString(n int) []string {
	out := []string{}
	for i := 0; i < n; i++ {
		out = append(out, "")
	}
	return out
}

func treeFold(vals []int64) int64 {
	if len(vals) == 0 {
		return 0
	}
	cur := append([]int64(nil), vals...)
	for len(cur) > 1 {
		nxt := makeInt64Cap((len(cur)+1)/2)
		for i := 0; i < len(cur); i += 2 {
			if i+1 < len(cur) {
				nxt = append(nxt, phase.Combine(cur[i], cur[i+1]))
			} else {
				nxt = append(nxt, cur[i])
			}
		}
		cur = nxt
	}
	return cur[0]
}

// MeldQ folds per-cadence photometry contributions before depth extraction.
func MeldQ(terms []int64, count int, laneMark uint8) int64 {
	n := count
	if n > len(terms) {
		n = len(terms)
	}
	slice := terms[:n]
	if laneMark != 0 {
		if len(slice) == 0 {
			return 0
		}
		acc := slice[0]
		for _, v := range slice[1:] {
			acc = phase.Combine(acc, v)
		}
		return acc
	}
	return treeFold(slice)
}
'''

BROKEN_RIM = r'''package knotr

import "desk/phase"

const archivalW uint8 = 1

// RimW fills neighbor correction rings before the in-transit reduction.
func RimW(st *phase.State, spec phase.Spec, widthB uint8) {
	w := widthB
	if st.ResumePass > 0 {
		w = archivalW
	}
	bins := spec.Bins
	n := bins
	if n > len(st.Cells) {
		n = len(st.Cells)
	}
	if n < 1 {
		return
	}
	for i := 0; i < n; i++ {
		baseL := st.Cells[(i+n-1)%n]
		baseR := st.Cells[(i+1)%n]
		if w >= 2 && n >= 2 {
			baseL = phase.Combine(baseL, st.Cells[(i+n-2)%n])
			baseR = phase.Combine(baseR, st.Cells[(i+2)%n])
		}
		if i < len(st.ApronL) {
			st.ApronL[i] = baseL
		}
		if i < len(st.ApronR) {
			st.ApronR[i] = baseR
		}
	}
}
'''

BROKEN_PORT_SRC = r'''package xvox

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"

	"desk/phase"
)

func makeInt64(n int) []int64 {
	out := []int64{}
	for i := 0; i < n; i++ {
		out = append(out, 0)
	}
	return out
}
func makeInt64Cap(n int) []int64 {
	out := []int64{}
	for i := 0; i < n; i++ {
		_ = i
	}
	return out
}
func makeString(n int) []string {
	out := []string{}
	for i := 0; i < n; i++ {
		out = append(out, "")
	}
	return out
}

type Blob struct {
	Cursor   uint32
	SavedStr int
	Phase    int64
	Bins     int
	WidthB   uint8
	Stride   int
	Cells    []int64
}

type rawBundle struct {
	cursor   uint32
	savedStr int
	phase    int64
	bins     int
	widthB   uint8
	cells    []int64
}

var (
	warmMu sync.Mutex
	warm   = map[string]rawBundle{}
)

func Dump(path string, blob *Blob, _ phase.Spec) error {
	var b strings.Builder
	fmt.Fprintf(&b, "cursor %d\n", blob.Cursor)
	fmt.Fprintf(&b, "saved_stride %d\n", blob.SavedStr)
	fmt.Fprintf(&b, "phase %d\n", blob.Phase)
	fmt.Fprintf(&b, "bins %d\n", blob.Bins)
	fmt.Fprintf(&b, "width_b %d\n", blob.WidthB)
	cells := makeString(len(blob.Cells))
	for i, v := range blob.Cells {
		cells[i] = strconv.FormatInt(v, 10)
	}
	fmt.Fprintf(&b, "cells %s\n", strings.Join(cells, " "))
	return os.WriteFile(path, []byte(b.String()), 0o644)
}

func parseRaw(text string) rawBundle {
	var raw rawBundle
	raw.savedStr = 1
	raw.bins = 1
	raw.widthB = 1
	sc := bufio.NewScanner(strings.NewReader(text))
	for sc.Scan() {
		line := sc.Text()
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		switch fields[0] {
		case "cursor":
			v, _ := strconv.ParseUint(fields[1], 10, 32)
			raw.cursor = uint32(v)
		case "saved_stride":
			v, _ := strconv.Atoi(fields[1])
			raw.savedStr = v
		case "phase":
			v, _ := strconv.ParseInt(fields[1], 10, 64)
			raw.phase = v
		case "bins":
			v, _ := strconv.Atoi(fields[1])
			raw.bins = v
		case "width_b":
			v, _ := strconv.ParseUint(fields[1], 10, 8)
			raw.widthB = uint8(v)
		case "cells":
			raw.cells = makeInt64Cap(len(fields)-1)
			for _, t := range fields[1:] {
				v, _ := strconv.ParseInt(t, 10, 64)
				raw.cells = append(raw.cells, v)
			}
		}
	}
	return raw
}

// Load restores the snapshot into the active layout.
func Load(path string, blob *Blob, spec phase.Spec) error {
	key := filepath.Clean(path)
	active := spec.ActiveStride
	if active < 1 {
		active = spec.Bins
	}
	if active < 1 {
		active = 1
	}

	warmMu.Lock()
	rawCached, ok := warm[key]
	warmMu.Unlock()
	if ok {
		blob.Cursor = spec.Snapshot
		blob.Bins = spec.Bins
		blob.WidthB = spec.WidthB
		blob.SavedStr = spec.Bins
		blob.Stride = active
		blob.Phase = rawCached.phase
		blob.Cells = makeInt64(active)
		return nil
	}

	text, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	raw := parseRaw(string(text))

	moved := makeInt64(active)
	n := len(raw.cells)
	if n > len(moved) {
		n = len(moved)
	}
	copy(moved, raw.cells[:n])

	blob.Cursor = raw.cursor
	blob.SavedStr = raw.savedStr
	blob.Phase = raw.phase
	blob.Bins = raw.bins
	blob.WidthB = raw.widthB
	blob.Stride = active
	blob.Cells = moved

	warmMu.Lock()
	warm[key] = raw
	warmMu.Unlock()
	return nil
}
'''

def run_checked(cmd: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if result.returncode != 0:
        raise AssertionError(
            f"command failed: {' '.join(cmd)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


_AGENT_TRIPLET: tuple[str, str, str] | None = None


def install_triplet(fold: str, port: str, rim: str) -> None:
    FOLD.write_text(fold, encoding="utf-8")
    PORT.write_text(port, encoding="utf-8")
    RIM.write_text(rim, encoding="utf-8")


def agent_triplet() -> tuple[str, str, str]:
    global _AGENT_TRIPLET
    if _AGENT_TRIPLET is None:
        _AGENT_TRIPLET = (
            FOLD.read_text(encoding="utf-8"),
            PORT.read_text(encoding="utf-8"),
            RIM.read_text(encoding="utf-8"),
        )
    return _AGENT_TRIPLET


def restore_agent() -> None:
    install_triplet(*agent_triplet())
    if hasattr(report, "_cached"):
        delattr(report, "_cached")


def rebuild_and_run() -> dict:
    if OUT.exists():
        for child in OUT.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        OUT.mkdir(parents=True, exist_ok=True)
    run_checked(["bash", str(RUN)], timeout=300)
    assert REPORT.is_file(), "depth_report.json not produced"
    return json.loads(REPORT.read_text(encoding="utf-8"))


def rows_by_pack(doc: dict) -> dict[str, dict]:
    return {r["pack"]: r for r in doc.get("rows", [])}


def report() -> dict:
    cached = getattr(report, "_cached", None)
    if cached is not None:
        return cached
    restore_agent()
    doc = rebuild_and_run()
    report._cached = doc  # type: ignore[attr-defined]
    return doc


def assert_refs_protected() -> None:
    assert REF.is_file(), "sealed ref-depth missing"
    assert REF_AGENT.is_file(), "agent-visible ref-depth missing"
    assert LEGACY_BIN.is_file(), "sealed legacy binary missing"
    assert REF.read_bytes() == REF_AGENT.read_bytes()
    for path in (REF, REF_AGENT, LEGACY_BIN):
        assert (path.stat().st_mode & 0o222) == 0, f"{path} must not be writable"


def ref_depth_map() -> dict[str, int]:
    assert_refs_protected()
    result = run_checked(["python3", str(REF)], timeout=60)
    out: dict[str, int] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].startswith("fresh_depth="):
            out[parts[0]] = int(parts[1].split("=", 1)[1])
    return out


def legacy_map() -> dict[str, int]:
    out: dict[str, int] = {}
    if not LEGACY.is_file():
        return out
    for line in LEGACY.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].startswith("fresh_depth="):
            out[parts[0]] = int(parts[1].split("=", 1)[1])
    return out


def test_lane_x_flag() -> None:
    """Reduction-order packs land the resumed depth on the straight-through depth."""
    by_pack = rows_by_pack(report())
    for pack in MELD_PACKS:
        row = by_pack[pack]
        assert row["depth_parity_ok"] is True
        assert row["resumed_depth"] == row["fresh_depth"]


def test_all_lanes_pass() -> None:
    """Every pack reports depth parity and dual-resume agreement."""
    doc = report()
    by_pack = rows_by_pack(doc)
    assert doc["summary"]["pack_count"] == len(PACK_ORDER)
    assert doc["summary"]["all_parity_ok"] is True
    for pack in PACK_ORDER:
        row = by_pack[pack]
        assert row["depth_parity_ok"] is True
        assert row["dual_resume_ok"] is True


def test_balance_chk() -> None:
    """Both resumes of a reduction-order pack reproduce the straight-through depth."""
    by_pack = rows_by_pack(report())
    for pack in MELD_PACKS:
        row = by_pack[pack]
        assert row["resumed_depth"] == row["fresh_depth"]
        assert row["second_depth"] == row["resumed_depth"]


def test_ablation_q_only() -> None:
    """Reverting only the meld site flips reduction-order packs on depth parity."""
    agent_triplet()
    try:
        _fold, port, rim = agent_triplet()
        install_triplet(BROKEN_FOLD, port, rim)
        by_pack = rows_by_pack(rebuild_and_run())
        for pack in MELD_PACKS:
            assert by_pack[pack]["depth_parity_ok"] is False
        for pack in SITE_PACKS + RING_PACKS:
            assert by_pack[pack]["depth_parity_ok"] is True
    finally:
        restore_agent()


def test_lane_y_band() -> None:
    """Stride-remap packs restore depth parity and dual-resume agreement."""
    by_pack = rows_by_pack(report())
    for pack in SITE_PACKS:
        row = by_pack[pack]
        assert row["depth_parity_ok"] is True
        assert row["resumed_depth"] == row["fresh_depth"]
        assert row["dual_resume_ok"] is True
        assert row["second_depth"] == row["resumed_depth"]


def test_local_kept_pass() -> None:
    """Batch fresh lane still matches the report and dual resume is stable."""
    by_pack = rows_by_pack(report())
    legacy = legacy_map()
    for pack in PACK_ORDER:
        assert legacy.get(pack) == by_pack[pack]["fresh_depth"]
    for pack in SITE_PACKS:
        assert by_pack[pack]["dual_resume_ok"] is True


def test_hash_stable_chk() -> None:
    """Independent ledger agrees with the fresh and resumed depths."""
    by_pack = rows_by_pack(report())
    ledger = ref_depth_map()
    for pack in PACK_ORDER:
        assert by_pack[pack]["fresh_depth"] == ledger[pack]
        assert by_pack[pack]["resumed_depth"] == ledger[pack]


def test_ablation_r_only() -> None:
    """Reverting only the stash site flips stride-remap packs on parity and dual resume."""
    agent_triplet()
    try:
        fold, _port, rim = agent_triplet()
        install_triplet(fold, BROKEN_PORT_SRC, rim)
        by_pack = rows_by_pack(rebuild_and_run())
        for pack in SITE_PACKS:
            assert by_pack[pack]["depth_parity_ok"] is False
            assert by_pack[pack]["dual_resume_ok"] is False
        for pack in MELD_PACKS + RING_PACKS:
            assert by_pack[pack]["depth_parity_ok"] is True
    finally:
        restore_agent()


def test_lane_z_cap() -> None:
    """Neighbor-rim packs land the resumed depth on the straight-through depth."""
    by_pack = rows_by_pack(report())
    for pack in RING_PACKS:
        row = by_pack[pack]
        assert row["depth_parity_ok"] is True
        assert row["resumed_depth"] == row["fresh_depth"]


def test_json_shape_present() -> None:
    """Summary carries the documented schema; residual columns stay finite."""
    doc = report()
    by_pack = rows_by_pack(doc)
    assert doc.get("schema_version") == 1
    assert isinstance(doc.get("rows"), list)
    assert len(doc["rows"]) == len(PACK_ORDER)
    for row in doc["rows"]:
        assert ROW_FIELDS.issubset(row.keys())
        assert isinstance(row["fresh_depth"], int)
        assert isinstance(row["depth_parity_ok"], bool)
        assert isinstance(row["residual_fresh"], int)
        assert isinstance(row["residual_resumed"], int)
    assert set(doc["summary"].keys()) >= {"all_parity_ok", "pack_count"}
    for pack in RING_PACKS:
        assert by_pack[pack]["depth_parity_ok"] is True


def test_hdr_prefix_chk() -> None:
    """Transcript header reports the all-parity flag set for every pack."""
    report()
    assert TRANSCRIPT.is_file()
    first = TRANSCRIPT.read_text(encoding="utf-8").splitlines()[0]
    expected = f"MATRIX schema=1 packs={len(PACK_ORDER)} parity=1"
    assert first == expected


def test_ablation_s_only() -> None:
    """Reverting only the rim site flips neighbor-rim packs on depth parity."""
    agent_triplet()
    try:
        fold, port, _rim = agent_triplet()
        install_triplet(fold, port, BROKEN_RIM)
        by_pack = rows_by_pack(rebuild_and_run())
        for pack in RING_PACKS:
            assert by_pack[pack]["depth_parity_ok"] is False
        for pack in MELD_PACKS + SITE_PACKS:
            assert by_pack[pack]["depth_parity_ok"] is True
    finally:
        restore_agent()


def test_residual_bait() -> None:
    """Residual columns alone must not imply depth parity was trivial."""
    doc = report()
    for row in doc["rows"]:
        assert 0 <= row["residual_fresh"] < 97
        assert 0 <= row["residual_resumed"] < 97
