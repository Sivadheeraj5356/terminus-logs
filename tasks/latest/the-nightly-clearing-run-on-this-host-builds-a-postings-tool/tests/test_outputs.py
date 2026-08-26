"""Behavioural verifier for the clearing-tape postings build.

Every test drives the offline build the way an operator would: it runs
/app/build/run.sh over a binary tape and reads the report the build produces.
The expected report is computed by an independent big-endian model of the record
frame, so the checks depend only on observed behaviour, never on the text of the
vendored sources.
"""

import os
import random
import shutil
import struct
import subprocess
import tempfile

RUN_SH = "/app/build/run.sh"
RECFMT = "/app/vendor/reckit/recfmt.fs"
SHIPPED = "/app/data/records.bin"

RECORD_LEN = 8
AMOUNT_MAX = (1 << 48) - 1


def _frame(ledger, amount):
    """Encode one 8-byte record frame: 2-byte ledger + 6-byte amount, MSB first."""
    return struct.pack(">H", ledger) + struct.pack(">Q", amount)[2:]


def _tape(records):
    return b"".join(_frame(led, amt) for led, amt in records)


def _oracle(records):
    """Independent big-endian model of the report for a list of (ledger, amount)."""
    lines = [f"{led}\t{amt}" for led, amt in records]
    lines.append(f"TOTAL\t{sum(amt for _, amt in records)}")
    return lines


def _oracle_from_bytes(data):
    recs = []
    for i in range(0, len(data), RECORD_LEN):
        frame = data[i:i + RECORD_LEN]
        led = int.from_bytes(frame[0:2], "big")
        amt = int.from_bytes(frame[2:8], "big")
        recs.append((led, amt))
    return _oracle(recs)


def _read_lines(path):
    with open(path) as handle:
        return [line.rstrip("\n") for line in handle if line.strip() != ""]


def _build_and_run(tape_bytes):
    """Assemble and run the vendored build over ``tape_bytes``; return report lines."""
    work = tempfile.mkdtemp(prefix="tape_")
    in_path = os.path.join(work, "in.bin")
    out_path = os.path.join(work, "out.txt")
    with open(in_path, "wb") as handle:
        handle.write(tape_bytes)
    subprocess.run(
        ["bash", RUN_SH, in_path, out_path],
        check=True,
        capture_output=True,
        text=True,
    )
    return _read_lines(out_path)


def _rand_records(seed, count):
    """Deterministically generate records whose multi-byte fields are asymmetric."""
    rng = random.Random(seed)
    recs = []
    for _ in range(count):
        ledger = rng.randint(0, 0xFFFF)
        pick = rng.random()
        if pick < 0.15:
            amount = rng.randint(0, 255)          # single significant byte
        elif pick < 0.30:
            amount = AMOUNT_MAX                    # maximum width
        elif pick < 0.45:
            amount = 0                             # zero
        else:
            amount = rng.randint(1 << 20, AMOUNT_MAX)  # wide, generally asymmetric
        recs.append((ledger, amount))
    return recs


def test_shipped_tape_report_schema():
    """The build reproduces the shipped tape's report in the required schema."""
    with open(SHIPPED, "rb") as handle:
        data = handle.read()
    produced = _build_and_run(data)
    assert produced == _oracle_from_bytes(data)
    assert produced[-1].split("\t")[0] == "TOTAL"
    for line in produced:
        assert len(line.split("\t")) == 2


def test_wide_amounts_match_vendored_semantics():
    """Wide, byte-asymmetric amounts match the big-endian model, not a byte swap."""
    records = [
        (0x1234, 30000000000),
        (0x00FF, 275000000000),
        (0x0001, 999999999999),
        (0xABCD, AMOUNT_MAX),
    ]
    assert _build_and_run(_tape(records)) == _oracle(records)


def test_single_byte_and_zero_amounts():
    """Single-byte and zero amounts are read identically to the model."""
    records = [(0x0007, 0), (0x0100, 1), (0x00AB, 255), (0xFFFF, 256)]
    assert _build_and_run(_tape(records)) == _oracle(records)


def test_total_is_summed_over_all_frames():
    """The TOTAL line equals the summed amount across a large asymmetric tape."""
    records = _rand_records(seed=917, count=64)
    produced = _build_and_run(_tape(records))
    assert produced == _oracle(records)
    assert produced[-1] == f"TOTAL\t{sum(a for _, a in records)}"


def test_random_tapes_across_seeds():
    """Across many seeded asymmetric tapes the report matches the model every time."""
    for seed in range(2000, 2024):
        records = _rand_records(seed=seed, count=12)
        assert _build_and_run(_tape(records)) == _oracle(records), f"seed {seed}"


def test_report_reads_fields_through_vendored_library():
    """The report's field values must come from the vendored recfmt accessors.

    With the accessors in place the report matches the model. When the vendored
    accessors are replaced by ones that return a fixed sentinel, the report must
    change -- a build that reaches into the frame itself instead of using the
    library shows no such dependence.
    """
    records = [(0x1234, 30000000000), (0xABCD, 275000000000)]
    baseline = _build_and_run(_tape(records))
    assert baseline == _oracle(records)

    backup = RECFMT + ".bak"
    shutil.copyfile(RECFMT, backup)
    try:
        with open(RECFMT, "w") as handle:
            handle.write(
                ": fld-ledger ( addr -- u ) drop 0 ;\n"
                ": fld-amount ( addr -- u ) drop 0 ;\n"
            )
        perturbed = _build_and_run(_tape(records))
    finally:
        shutil.move(backup, RECFMT)

    assert perturbed != baseline
