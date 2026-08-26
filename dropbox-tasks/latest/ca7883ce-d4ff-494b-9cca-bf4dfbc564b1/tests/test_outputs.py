"""Independent verifier for this weather replay audit task."""

from __future__ import annotations

import random
import subprocess
from pathlib import Path

MOD = 1000000007
SCRIPT = Path("/app") / "radar_tilt_qc_patch_stack.R"
FIELDS = ['active_records', 'zone_load', 'snapshots', 'obs_count', 'correction_count', 'snap_count', 'vacuum_count', 'revoke_count', 'latest_rev_sum', 'trace_hash']


def clean_lines(text: str) -> list[str]:
    rows = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            rows.append(line)
    return rows


def hash_items(items: list[str]) -> str:
    h = 0
    for item in items:
        for byte in item.encode("utf-8"):
            h = (h * 137 + byte) % MOD
        h = (h * 137 + 31) % MOD
    return str(h)


def parse_output(stdout: str) -> dict[str, str]:
    rows = stdout.splitlines()
    assert len(rows) == len(FIELDS), rows
    got: dict[str, str] = {}
    for expected, row in zip(FIELDS, rows):
        assert row == row.strip() and row, row
        assert row.startswith(expected + "="), row
        key, value = row.split("=", 1)
        assert key not in got
        got[key] = value
    assert list(got) == FIELDS
    return got


def run_tool(tmp_path: Path, trace: str) -> dict[str, str]:
    trace_path = tmp_path / "trace.txt"
    trace_path.write_text(trace)
    proc = subprocess.run(
        ["Rscript", str(SCRIPT), str(trace_path)],
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stderr == ""
    return parse_output(proc.stdout)


def fmt_map(mapping: dict[str, int]) -> str:
    return "-" if not mapping else ";".join(f"{k}:{mapping[k]}" for k in sorted(mapping))


def simulate(trace: str) -> dict[str, str]:
    records: dict[str, dict[str, int | str]] = {}
    snapshots: list[str] = []
    events: list[str] = []
    obs_count = correction_count = snap_count = vacuum_count = revoke_count = 0
    for line in clean_lines(trace):
        parts = line.split()
        op = parts[0]
        if op == "OBS" and len(parts) == 7:
            rec_id, st, en, val, zone, rev = parts[1], int(parts[2]), int(parts[3]), int(parts[4]), parts[5], int(parts[6])
            if en > st and val > 0 and rev >= 0 and (rec_id not in records or rev >= int(records[rec_id]["rev"])):
                records[rec_id] = {"start": st, "end": en, "value": val, "zone": zone, "rev": rev}
                obs_count += 1
                events.append(f"obs:{rec_id}:{st}:{en}:{val}:{zone}:{rev}")
        elif op == "CORRECT" and len(parts) == 7:
            rec_id, st, en, val, zone, rev = parts[1], int(parts[2]), int(parts[3]), int(parts[4]), parts[5], int(parts[6])
            if rec_id in records and en > st and val > 0 and rev >= int(records[rec_id]["rev"]):
                records[rec_id] = {"start": st, "end": en, "value": val, "zone": zone, "rev": rev}
                correction_count += 1
                events.append(f"correct:{rec_id}:{st}:{en}:{val}:{zone}:{rev}")
        elif op == "SNAP" and len(parts) == 2:
            t = int(parts[1])
            zones: dict[str, int] = {}
            for rec in records.values():
                if int(rec["start"]) <= t < int(rec["end"]):
                    zones[str(rec["zone"])] = zones.get(str(rec["zone"]), 0) + int(rec["value"])
            snap = fmt_map(zones)
            snapshots.append(f"{t}|{snap}")
            snap_count += 1
            events.append(f"snap:{t}:{snap}")
        elif op == "VACUUM" and len(parts) == 2:
            cutoff = int(parts[1])
            for rec_id in sorted(list(records)):
                if int(records[rec_id]["end"]) <= cutoff:
                    en = int(records[rec_id]["end"])
                    del records[rec_id]
                    vacuum_count += 1
                    events.append(f"vacuum:{rec_id}:{en}")
        elif op == "REVOKE" and len(parts) == 3:
            rec_id, rev = parts[1], int(parts[2])
            if rec_id in records and rev >= int(records[rec_id]["rev"]):
                old = int(records[rec_id]["rev"])
                del records[rec_id]
                revoke_count += 1
                events.append(f"revoke:{rec_id}:{rev}:{old}")
    active = "-" if not records else ";".join(
        f"{k}:{records[k]['start']}:{records[k]['end']}:{records[k]['value']}:{records[k]['zone']}:{records[k]['rev']}"
        for k in sorted(records)
    )
    zones: dict[str, int] = {}
    for rec in records.values():
        zones[str(rec["zone"])] = zones.get(str(rec["zone"]), 0) + int(rec["value"])
    zone_s = fmt_map(zones)
    snap_s = "-" if not snapshots else ";".join(snapshots)
    rev_sum = sum(int(r["rev"]) for r in records.values())
    pre = [active, zone_s, snap_s, str(obs_count), str(correction_count), str(snap_count), str(vacuum_count), str(revoke_count), str(rev_sum)]
    return {
        "active_records": active,
        "zone_load": zone_s,
        "snapshots": snap_s,
        "obs_count": str(obs_count),
        "correction_count": str(correction_count),
        "snap_count": str(snap_count),
        "vacuum_count": str(vacuum_count),
        "revoke_count": str(revoke_count),
        "latest_rev_sum": str(rev_sum),
        "trace_hash": hash_items(pre + events),
    }


def generated_trace(seed: int) -> str:
    rng = random.Random(seed)
    ids = ["T1", "T2", "T3", "T4", "T5"]
    zones = ["N", "S", "E", "W"]
    rows = ["# generated patch snapshot trace"]
    for i in range(60):
        op = rng.randrange(5)
        rec_id = rng.choice(ids)
        st = rng.randint(0, 40)
        en = st + rng.randint(-2, 18)
        val = rng.randint(-1, 14)
        rev = rng.randint(0, 8)
        if op == 0:
            rows.append(f"OBS {rec_id} {st} {en} {val} {rng.choice(zones)} {rev}")
        elif op == 1:
            rows.append(f"CORRECT {rec_id} {st} {en} {val} {rng.choice(zones)} {rev}")
        elif op == 2:
            rows.append(f"SNAP {rng.randint(0, 55)}")
        elif op == 3:
            rows.append(f"VACUUM {rng.randint(0, 50)}")
        else:
            rows.append(f"REVOKE {rec_id} {rev}")
    return "\n".join(rows)


class TestWeatherAudit:
    def test_sample_contract(self, tmp_path: Path) -> None:
        """The tool handles late corrections, snapshots, revokes, and vacuum expiry."""
        trace = """
        OBS T1 0 10 5 N 1
        OBS T2 3 14 7 S 1
        SNAP 5
        CORRECT T1 0 12 8 E 2
        CORRECT missing 0 2 9 W 9
        REVOKE T2 0
        VACUUM 11
        SNAP 11
        """
        assert run_tool(tmp_path, trace) == simulate(trace)

    def test_comments_and_rejected_revisions(self, tmp_path: Path) -> None:
        """Blank lines, comments, lower revisions, and invalid intervals are ignored."""
        trace = """
        OBS A 2 9 4 W 3
        CORRECT A 2 8 6 W 2 # stale

        OBS B 4 4 10 E 1
        SNAP 3
        REVOKE A 3
        SNAP 3
        """
        assert run_tool(tmp_path, trace) == simulate(trace)

    def test_negative_observation_revision_is_ignored(self, tmp_path: Path) -> None:
        """A negative OBS revision is invalid and never creates a live record."""
        trace = """
        OBS NEG 0 10 50 N -1
        OBS A 0 8 6 E 0
        SNAP 4
        CORRECT NEG 0 10 60 W 0
        SNAP 4
        """
        assert run_tool(tmp_path, trace) == simulate(trace)

    def test_generated_stateful_traces(self, tmp_path: Path) -> None:
        """Generated traces exercise replacement ordering and inline hash events."""
        for seed in range(10):
            trace = generated_trace(seed)
            assert run_tool(tmp_path, trace) == simulate(trace)
