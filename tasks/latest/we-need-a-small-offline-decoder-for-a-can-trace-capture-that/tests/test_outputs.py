"""Verifier for the CAN trace decoder task."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
from pathlib import Path


APP = Path("/app")
DEFAULT_NETWORK = APP / "task_file" / "network.json"
DEFAULT_TRACE = APP / "task_file" / "public_trace.bin"
DEFAULT_REPORT = APP / "out" / "report.json"
BIN = APP / "cantrace"
PUBLIC_TRACE_SHA256 = "a4d8f5ee549d7c919b0119b5f1b628d5673bb7be83a54cfcf354a1192dec3710"


def set_bits(payload: bytearray, start: int, length: int, value: int) -> None:
    """Set a little-endian signal field in an eight-byte payload."""
    mask = (1 << length) - 1
    value &= mask
    for i in range(length):
        bit = (value >> i) & 1
        pos = start + i
        if bit:
            payload[pos // 8] |= 1 << (pos % 8)
        else:
            payload[pos // 8] &= ~(1 << (pos % 8))


def set_big_bits(payload: bytearray, start: int, length: int, value: int) -> None:
    """Set a big-endian signal field using the documented MSB-first bit numbering."""
    mask = (1 << length) - 1
    value &= mask
    for i in range(length):
        bit = (value >> (length - 1 - i)) & 1
        pos = start + i
        byte_index = pos // 8
        bit_index = 7 - (pos % 8)
        if bit:
            payload[byte_index] |= 1 << bit_index
        else:
            payload[byte_index] &= ~(1 << bit_index)


def encode_record(
    timestamp: int, can_id: int, dlc: int, payload: bytes, flags: int = 0
) -> bytes:
    """Encode one binary CAN trace record."""
    assert len(payload) == 8
    return struct.pack("<I H B B 8s", timestamp, can_id, dlc, flags, payload)


def checksum_value(payload: bytes | bytearray, dlc: int, checksum: dict) -> int | None:
    """Calculate the documented checksum value for supported modes."""
    checksum_byte = checksum["byte"]
    seed = int(checksum.get("seed", 0))
    if checksum["mode"] == "sum8":
        return (seed + sum(payload[i] for i in range(dlc) if i != checksum_byte)) % 256
    if checksum["mode"] == "xor8":
        value = seed
        for i in range(dlc):
            if i != checksum_byte:
                value ^= payload[i]
        return value & 0xFF
    if checksum["mode"] == "crc8":
        value = seed & 0xFF
        for i in range(dlc):
            if i == checksum_byte:
                continue
            value ^= payload[i]
            for _ in range(8):
                if value & 0x80:
                    value = ((value << 1) ^ 0x1D) & 0xFF
                else:
                    value = (value << 1) & 0xFF
        return (value ^ int(checksum.get("final_xor", 0))) & 0xFF
    return None


def apply_checksum(
    payload: bytearray, dlc: int, checksum: dict, bad_delta: int = 0
) -> None:
    """Write a generated checksum byte using the public checksum contract."""
    expected = checksum_value(payload, dlc, checksum)
    assert expected is not None
    payload[checksum["byte"]] = (expected + bad_delta) % 256


def sum8(
    payload: bytes | bytearray, dlc: int, checksum_byte: int, seed: int = 0
) -> int:
    """Calculate the documented sum8 checksum."""
    return (seed + sum(payload[i] for i in range(dlc) if i != checksum_byte)) % 256


def payload_from_fields(
    fields: list[tuple[int, int, int]], checksum: tuple[int, int] | None = None
) -> bytes:
    """Build an eight-byte payload from little-endian bit fields."""
    payload = bytearray(8)
    for start, length, value in fields:
        set_bits(payload, start, length, value)
    if checksum is not None:
        dlc, byte_index = checksum
        payload[byte_index] = sum8(payload, dlc, byte_index)
    return bytes(payload)


def run_tool(network: Path, trace: Path, output: Path, explicit: bool = True) -> dict:
    """Run /app/cantrace and parse its JSON report."""
    if output.exists():
        output.unlink()
    cmd = [str(BIN), str(network), str(trace), str(output)] if explicit else [str(BIN)]
    result = subprocess.run(cmd, cwd=APP, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert output.exists(), f"{output} was not created"
    with output.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def reference_decode(network: dict, trace: bytes) -> dict:
    """Decode a trace according to the public task specification."""
    assert len(trace) % 16 == 0
    report = {"bus": network["bus"], "messages": [], "unknown_frames": []}
    message_index = {}
    counter_state: dict[tuple[str, int | str], int] = {}
    counter_scope: list[tuple[str, int | str] | None] = []
    valid_timestamps: list[int | None] = []
    signal_stats: list[list[dict]] = []

    for index, message in enumerate(network["messages"]):
        message_index[message["id"]] = index
        report["messages"].append(
            {
                "id": message["id"],
                "name": message["name"],
                "frames": 0,
                "valid_frames": 0,
                "warnings": [],
                "signals": [
                    {
                        "name": signal["name"],
                        "unit": signal["unit"],
                        "count": 0,
                        "min": None,
                        "max": None,
                        "last": None,
                        "last_timestamp_ms": None,
                    }
                    for signal in message["signals"]
                ],
            }
        )
        if message["counter"] is None:
            counter_scope.append(None)
        elif message.get("counter_group"):
            counter_scope.append(("group", message["counter_group"]))
        else:
            counter_scope.append(("message", index))
        valid_timestamps.append(None)
        signal_stats.append(report["messages"][index]["signals"])

    for offset in range(0, len(trace), 16):
        timestamp, can_id, dlc, flags, payload = struct.unpack(
            "<I H B B 8s", trace[offset : offset + 16]
        )
        if can_id not in message_index:
            report["unknown_frames"].append(
                {
                    "timestamp_ms": timestamp,
                    "id": can_id,
                    "dlc": dlc,
                    "reason": "unknown_id",
                }
            )
            continue

        msg_i = message_index[can_id]
        message = network["messages"][msg_i]
        out = report["messages"][msg_i]
        out["frames"] += 1

        if dlc != message["expected_dlc"] or dlc > 8:
            out["warnings"].append(
                {"timestamp_ms": timestamp, "reason": "dlc_mismatch", "detail": ""}
            )
            continue

        checksum = message["checksum"]
        if checksum is not None:
            expected = checksum_value(payload, dlc, checksum)
            if expected is None or payload[checksum["byte"]] != expected:
                out["warnings"].append(
                    {"timestamp_ms": timestamp, "reason": "bad_checksum", "detail": ""}
                )
                continue

        out["valid_frames"] += 1
        max_gap_ms = message.get("max_gap_ms")
        if max_gap_ms is not None:
            previous_ts = valid_timestamps[msg_i]
            if previous_ts is not None and timestamp - previous_ts > max_gap_ms:
                out["warnings"].append(
                    {"timestamp_ms": timestamp, "reason": "stale_gap", "detail": ""}
                )
            valid_timestamps[msg_i] = timestamp
        counter_hold = message.get("counter_hold_flags", False) and flags & 0x02
        if counter_hold:
            out["warnings"].append(
                {"timestamp_ms": timestamp, "reason": "counter_hold", "detail": ""}
            )
        counter = message["counter"]
        if counter is not None and not counter_hold:
            observed = (payload[counter["byte"]] & counter["mask"]) >> counter["shift"]
            reset = counter_reset_matches(payload, message.get("counter_reset"))
            scope = counter_scope[msg_i]
            assert scope is not None
            previous = counter_state.get(scope)
            if (
                not reset
                and previous is not None
                and observed != (previous + 1) % counter["modulo"]
            ):
                out["warnings"].append(
                    {"timestamp_ms": timestamp, "reason": "counter_jump", "detail": ""}
                )
            counter_state[scope] = observed

        if message.get("stats_reset_flags", False) and flags & 0x04:
            out["warnings"].append(
                {"timestamp_ms": timestamp, "reason": "stats_reset", "detail": ""}
            )
            reset_signal_stats(signal_stats[msg_i])

        if message.get("listen_only_flags", False) and flags & 0x01:
            out["warnings"].append(
                {"timestamp_ms": timestamp, "reason": "listen_only", "detail": ""}
            )
            continue

        for sig_i, signal in enumerate(message["signals"]):
            mux = signal.get("mux")
            if mux is not None and (payload[mux["byte"]] & mux["mask"]) != mux["value"]:
                continue
            raw = raw_value(payload, signal)
            if raw in set(signal.get("invalid_raw", [])):
                continue
            value = physical_from_raw(raw, signal)
            max_delta = signal.get("max_delta")
            stats = signal_stats[msg_i][sig_i]
            if (
                max_delta is not None
                and stats["count"] > 0
                and abs(value - stats["last"]) > max_delta
            ):
                out["warnings"].append(
                    {"timestamp_ms": timestamp, "reason": "signal_jump", "detail": ""}
                )
            update_stats(signal_stats[msg_i][sig_i], value, timestamp)

    return report


def counter_reset_matches(payload: bytes, reset: dict | None) -> bool:
    """Return whether a valid frame carries a documented counter reset marker."""
    if reset is None:
        return False
    return (payload[reset["byte"]] & reset["mask"]) == reset["value"]


def raw_value(payload: bytes, signal: dict) -> int:
    """Decode one signal's unsigned raw bit pattern."""
    raw = 0
    if signal["endian"] == "big":
        for i in range(signal["length"]):
            pos = signal["start_bit"] + i
            bit = 1 if payload[pos // 8] & (1 << (7 - (pos % 8))) else 0
            raw = (raw << 1) | bit
    else:
        for i in range(signal["length"]):
            pos = signal["start_bit"] + i
            if payload[pos // 8] & (1 << (pos % 8)):
                raw |= 1 << i
    return raw


def physical_from_raw(raw: int, signal: dict) -> float:
    """Convert a raw bit pattern to a physical signal value."""
    if signal["signed"] and signal["length"] and raw & (1 << (signal["length"] - 1)):
        raw -= 1 << signal["length"]
    value = raw * signal["scale"] + signal["offset"]
    return 0 if value == 0 else value


def update_stats(stats: dict, value: float, timestamp: int) -> None:
    """Update aggregate fields for one decoded signal sample."""
    if stats["count"] == 0:
        stats["min"] = value
        stats["max"] = value
    else:
        stats["min"] = min(stats["min"], value)
        stats["max"] = max(stats["max"], value)
    stats["count"] += 1
    stats["last"] = value
    stats["last_timestamp_ms"] = timestamp


def reset_signal_stats(stats_list: list[dict]) -> None:
    """Clear aggregate fields for every signal in one message."""
    for stats in stats_list:
        stats["count"] = 0
        stats["min"] = None
        stats["max"] = None
        stats["last"] = None
        stats["last_timestamp_ms"] = None


def write_variant(
    tmp_path: Path, name: str, network: dict, records: list[bytes]
) -> tuple[Path, Path]:
    """Write a generated network and trace variant to disk."""
    network_path = tmp_path / f"{name}.json"
    trace_path = tmp_path / f"{name}.bin"
    network_path.write_text(
        json.dumps(network, separators=(",", ":")), encoding="utf-8"
    )
    trace_path.write_bytes(b"".join(records))
    return network_path, trace_path


def base_network(
    name: str,
    message_id: int,
    counter: dict | None,
    checksum: dict | None,
    max_gap_ms: int | None = None,
) -> dict:
    """Create a compatible network fixture with mixed signal types."""
    return {
        "bus": name,
        "messages": [
            {
                "id": message_id,
                "name": "Drive",
                "expected_dlc": 8,
                "max_gap_ms": max_gap_ms,
                "counter": counter,
                "checksum": checksum,
                "signals": [
                    {
                        "name": "speed",
                        "start_bit": 0,
                        "length": 12,
                        "endian": "little",
                        "signed": False,
                        "scale": 0.125,
                        "offset": 0,
                        "unit": "kph",
                    },
                    {
                        "name": "slip",
                        "start_bit": 12,
                        "length": 10,
                        "endian": "little",
                        "signed": True,
                        "scale": 0.5,
                        "offset": -12,
                        "unit": "pct",
                    },
                    {
                        "name": "boost",
                        "start_bit": 32,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 2,
                        "offset": -20,
                        "unit": "kpa",
                        "mux": {"byte": 3, "mask": 3, "value": 2},
                    },
                ],
            }
        ],
    }


def make_drive_payload(
    speed_raw: int,
    slip_raw: int,
    mux_value: int,
    boost_raw: int,
    counter_value: int | None,
    counter_cfg: dict | None,
    checksum_cfg: dict | None,
    bad_checksum: bool = False,
) -> bytes:
    """Create a generated Drive payload using the documented field layout."""
    fields = [
        (0, 12, speed_raw),
        (12, 10, slip_raw),
        (24, 2, mux_value),
        (32, 8, boost_raw),
    ]
    payload = bytearray(payload_from_fields(fields))
    if counter_cfg is not None and counter_value is not None:
        byte_index = counter_cfg["byte"]
        payload[byte_index] &= ~counter_cfg["mask"] & 0xFF
        payload[byte_index] |= (counter_value << counter_cfg["shift"]) & counter_cfg[
            "mask"
        ]
    if checksum_cfg is not None:
        apply_checksum(payload, 8, checksum_cfg, 23 if bad_checksum else 0)
    return bytes(payload)


def test_public_input_integrity_is_unchanged() -> None:
    """Verify the public trace fixture was not altered to match a shortcut solution."""
    digest = hashlib.sha256(DEFAULT_TRACE.read_bytes()).hexdigest()
    assert digest == PUBLIC_TRACE_SHA256
    network = json.loads(DEFAULT_NETWORK.read_text(encoding="utf-8"))
    assert network["bus"] == "bench-rig-a"
    assert [message["name"] for message in network["messages"]] == [
        "Engine",
        "Battery",
        "Cabin",
    ]


def test_cantrace_is_compiled_go_binary() -> None:
    """Verify /app/cantrace is a compiled Go executable, not a script shim."""
    assert BIN.exists(), "/app/cantrace must exist"
    result = subprocess.run(
        ["go", "version", "-m", str(BIN)],
        cwd=APP,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert str(BIN) in result.stdout


def test_default_cli_contract_and_public_report() -> None:
    """Verify no-argument CLI mode reads and writes the required absolute paths."""
    network = json.loads(DEFAULT_NETWORK.read_text(encoding="utf-8"))
    expected = reference_decode(network, DEFAULT_TRACE.read_bytes())
    actual = run_tool(DEFAULT_NETWORK, DEFAULT_TRACE, DEFAULT_REPORT, explicit=False)
    assert actual == expected


def test_report_schema_nulls_and_ordering_on_public_capture() -> None:
    """Verify report fields, null signal stats, message order, warning order, and unknown frame order."""
    actual = run_tool(
        DEFAULT_NETWORK, DEFAULT_TRACE, APP / "out" / "schema_public.json"
    )
    assert list(actual) == ["bus", "messages", "unknown_frames"]
    assert [message["name"] for message in actual["messages"]] == [
        "Engine",
        "Battery",
        "Cabin",
    ]
    engine = actual["messages"][0]
    assert [warning["reason"] for warning in engine["warnings"]] == [
        "bad_checksum",
        "stale_gap",
        "counter_jump",
        "dlc_mismatch",
    ]
    cabin = actual["messages"][2]
    assert cabin["warnings"] == [
        {"timestamp_ms": 310, "reason": "counter_jump", "detail": ""}
    ]
    assert actual["unknown_frames"] == [
        {"timestamp_ms": 330, "id": 1110, "dlc": 8, "reason": "unknown_id"}
    ]
    empty_signals = [
        signal for signal in actual["messages"][1]["signals"] if signal["count"] == 0
    ]
    assert empty_signals == []


def test_empty_trace_keeps_configured_messages_and_null_signal_stats(
    tmp_path: Path,
) -> None:
    """Verify empty traces still emit every configured message and every signal with null aggregate fields."""
    network = json.loads(DEFAULT_NETWORK.read_text(encoding="utf-8"))
    network_path, trace_path = write_variant(tmp_path, "empty", network, [])
    output = tmp_path / "empty_report.json"
    actual = run_tool(network_path, trace_path, output)
    assert actual == reference_decode(network, b"")
    assert all(
        message["frames"] == 0 and message["valid_frames"] == 0
        for message in actual["messages"]
    )
    for message in actual["messages"]:
        for signal in message["signals"]:
            assert signal["count"] == 0
            assert signal["min"] is None
            assert signal["max"] is None
            assert signal["last"] is None
            assert signal["last_timestamp_ms"] is None


def test_malformed_trace_length_is_rejected(tmp_path: Path) -> None:
    """Verify trace files whose byte length is not a multiple of 16 are rejected."""
    trace_path = tmp_path / "malformed_trace.bin"
    output_path = tmp_path / "malformed" / "report.json"
    trace_path.write_bytes(encode_record(1, 0x120, 8, bytes(8)) + b"x")
    result = subprocess.run(
        [str(BIN), str(DEFAULT_NETWORK), str(trace_path), str(output_path)],
        cwd=APP,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert not output_path.exists()
    assert "multiple of 16" in result.stderr.lower()


def test_generated_compatibility_matrix(tmp_path: Path) -> None:
    """Verify compatible generated captures across checksum, counter, mux, signed, and ordering variants."""
    variants: list[tuple[str, dict, list[bytes]]] = []
    counter_a = {"byte": 7, "mask": 15, "shift": 0, "modulo": 16}
    counter_b = {"byte": 6, "mask": 112, "shift": 4, "modulo": 8}
    checksum_a = {"byte": 5, "mode": "sum8", "seed": 11}
    checksum_b = {"byte": 7, "mode": "xor8", "seed": 0xA7}

    for i in range(16):
        counter = [counter_a, counter_b, None, counter_a][i % 4]
        checksum = [checksum_a, checksum_b, None, checksum_a][(i // 2) % 4]
        if (
            counter is not None
            and checksum is not None
            and counter["byte"] == checksum["byte"]
        ):
            checksum = checksum_a
        max_gap_ms = [None, 20, 45, 2][i % 4]
        message_id = 0x340 + i * 3
        network = base_network(
            f"generated-{i}", message_id, counter, checksum, max_gap_ms=max_gap_ms
        )
        records: list[bytes] = []
        sequence = (
            [14, 15, 0, 2] if counter and counter.get("modulo") == 16 else [5, 6, 0, 1]
        )
        step = 35 if i % 4 == 1 else 1
        for frame_i in range(4):
            dlc = 7 if i % 5 == 0 and frame_i == 2 else 8
            bad_checksum = checksum is not None and i % 3 == 1 and frame_i == 1
            mux = 2 if frame_i % 2 == 0 else 1
            counter_value = sequence[frame_i] if counter is not None else None
            payload = make_drive_payload(
                400 + i * 11 + frame_i,
                -20 + frame_i * 7,
                mux,
                30 + i + frame_i,
                counter_value,
                counter,
                checksum,
                bad_checksum,
            )
            records.append(
                encode_record(1000 + i * 80 + frame_i * step, message_id, dlc, payload)
            )
        if i % 4 == 2:
            records.insert(1, encode_record(1200 + i, 0x7A0 + i, 8, bytes([i] * 8)))
        variants.append((f"variant_{i}", network, records))

    for name, network, records in variants:
        network_path, trace_path = write_variant(tmp_path, name, network, records)
        output = tmp_path / f"{name}_report.json"
        actual = run_tool(network_path, trace_path, output)
        expected = reference_decode(network, b"".join(records))
        assert actual == expected, name


def test_counter_rollover_and_jump_does_not_drop_signals(tmp_path: Path) -> None:
    """Verify counter rollover and counter_jump warnings still keep the frame's decoded signals."""
    counter = {"byte": 7, "mask": 15, "shift": 0, "modulo": 16}
    checksum = {"byte": 5, "mode": "sum8"}
    network = base_network("rollover", 0x456, counter, checksum, max_gap_ms=50)
    records = [
        encode_record(
            10, 0x456, 8, make_drive_payload(100, 0, 2, 10, 14, counter, checksum)
        ),
        encode_record(
            11, 0x456, 8, make_drive_payload(101, 1, 2, 11, 15, counter, checksum)
        ),
        encode_record(
            12, 0x456, 8, make_drive_payload(102, 2, 2, 12, 0, counter, checksum)
        ),
        encode_record(
            13, 0x456, 8, make_drive_payload(103, 3, 2, 13, 3, counter, checksum)
        ),
    ]
    network_path, trace_path = write_variant(tmp_path, "rollover", network, records)
    actual = run_tool(network_path, trace_path, tmp_path / "rollover_report.json")
    assert actual == reference_decode(network, b"".join(records))
    assert actual["messages"][0]["warnings"] == [
        {"timestamp_ms": 13, "reason": "counter_jump", "detail": ""}
    ]
    assert actual["messages"][0]["signals"][0]["count"] == 4


def test_counter_reset_and_invalid_raw_samples_compose_with_gates(
    tmp_path: Path,
) -> None:
    """Verify counter reset markers and invalid raw signal values compose with gates."""
    message_id = 0x531
    counter = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 8}
    reset = {"byte": 5, "mask": 0x80, "value": 0x80}
    checksum = {"byte": 6, "mode": "sum8"}
    network = {
        "bus": "reset-invalid",
        "messages": [
            {
                "id": message_id,
                "name": "ResetState",
                "expected_dlc": 8,
                "max_gap_ms": 4,
                "counter": counter,
                "counter_reset": reset,
                "checksum": checksum,
                "signals": [
                    {
                        "name": "speed",
                        "start_bit": 0,
                        "length": 12,
                        "endian": "little",
                        "signed": False,
                        "scale": 0.25,
                        "offset": 0,
                        "unit": "kph",
                        "invalid_raw": [4095],
                    },
                    {
                        "name": "trim",
                        "start_bit": 12,
                        "length": 10,
                        "endian": "little",
                        "signed": True,
                        "scale": 0.5,
                        "offset": -2,
                        "unit": "pct",
                        "invalid_raw": [1023],
                    },
                    {
                        "name": "muxed_diag",
                        "start_bit": 32,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "code",
                        "mux": {"byte": 4, "mask": 0x03, "value": 0x02},
                        "invalid_raw": [255],
                    },
                ],
            }
        ],
    }

    def payload(
        speed_raw: int,
        trim_raw: int,
        mux_bits: int,
        muxed_raw: int,
        counter_value: int,
        reset_marker: bool = False,
        bad_checksum: bool = False,
    ) -> bytes:
        data = bytearray(
            payload_from_fields(
                [(0, 12, speed_raw), (12, 10, trim_raw), (32, 8, muxed_raw)]
            )
        )
        data[4] = (data[4] & ~0x03) | mux_bits
        if reset_marker:
            data[5] |= 0x80
        data[counter["byte"]] &= ~counter["mask"] & 0xFF
        data[counter["byte"]] |= counter_value & counter["mask"]
        apply_checksum(data, 8, checksum, 29 if bad_checksum else 0)
        return bytes(data)

    records = [
        encode_record(10, message_id, 8, payload(100, 10, 2, 20, 1)),
        encode_record(
            20, message_id, 8, payload(4095, 11, 2, 21, 7, reset_marker=True)
        ),
        encode_record(21, message_id, 8, payload(120, 12, 1, 22, 0)),
        encode_record(
            30, message_id, 8, payload(130, 1023, 2, 255, 3, bad_checksum=True)
        ),
        encode_record(31, message_id, 8, payload(140, 13, 2, 23, 1, reset_marker=True)),
        encode_record(32, message_id, 8, payload(150, 14, 2, 24, 2)),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "reset_invalid", network, records
    )
    actual = run_tool(network_path, trace_path, tmp_path / "reset_invalid_report.json")
    expected = reference_decode(network, b"".join(records))
    assert actual == expected
    message = actual["messages"][0]
    assert [warning["reason"] for warning in message["warnings"]] == [
        "stale_gap",
        "bad_checksum",
        "stale_gap",
    ]
    assert message["valid_frames"] == 5
    assert message["signals"][0]["count"] == 4
    assert message["signals"][1]["count"] == 5
    assert message["signals"][2]["count"] == 4


def test_dlc_and_checksum_are_gates_before_counter_and_signals(tmp_path: Path) -> None:
    """Verify DLC and checksum failures do not update counters, gap state, or signal aggregates."""
    counter = {"byte": 7, "mask": 15, "shift": 0, "modulo": 16}
    checksum = {"byte": 5, "mode": "sum8"}
    network = base_network("gates", 0x520, counter, checksum, max_gap_ms=2)
    records = [
        encode_record(
            20, 0x520, 8, make_drive_payload(200, 0, 2, 10, 1, counter, checksum)
        ),
        encode_record(
            21, 0x520, 7, make_drive_payload(250, 0, 2, 10, 2, counter, checksum)
        ),
        encode_record(
            22,
            0x520,
            8,
            make_drive_payload(260, 0, 2, 10, 2, counter, checksum, bad_checksum=True),
        ),
        encode_record(
            24, 0x520, 8, make_drive_payload(300, 0, 2, 10, 2, counter, checksum)
        ),
    ]
    network_path, trace_path = write_variant(tmp_path, "gates", network, records)
    actual = run_tool(network_path, trace_path, tmp_path / "gates_report.json")
    assert actual == reference_decode(network, b"".join(records))
    assert [warning["reason"] for warning in actual["messages"][0]["warnings"]] == [
        "dlc_mismatch",
        "bad_checksum",
        "stale_gap",
    ]
    assert actual["messages"][0]["valid_frames"] == 2
    assert actual["messages"][0]["signals"][0]["count"] == 2


def test_interleaved_short_dlc_flags_mux_nulls_and_non_power_counter(
    tmp_path: Path,
) -> None:
    """Verify mixed messages with short DLC checksum, flags, mux nulls, and modulo-5 counters."""
    diag_id = 0x612
    status_id = 0x201
    dormant_id = 0x355
    counter = {"byte": 1, "mask": 0xE0, "shift": 5, "modulo": 5}
    checksum = {"byte": 3, "mode": "sum8"}
    network = {
        "bus": "mixed-hard",
        "messages": [
            {
                "id": diag_id,
                "name": "Diag",
                "expected_dlc": 4,
                "max_gap_ms": 5,
                "counter": counter,
                "checksum": checksum,
                "signals": [
                    {
                        "name": "signed_nibble",
                        "start_bit": 0,
                        "length": 5,
                        "endian": "little",
                        "signed": True,
                        "scale": -1.5,
                        "offset": 4,
                        "unit": "deg",
                    },
                    {
                        "name": "low_byte",
                        "start_bit": 8,
                        "length": 5,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "cnt",
                    },
                    {
                        "name": "never_mux",
                        "start_bit": 16,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 0.25,
                        "offset": 0,
                        "unit": "raw",
                        "mux": {"byte": 2, "mask": 3, "value": 3},
                    },
                ],
            },
            {
                "id": status_id,
                "name": "Status",
                "expected_dlc": 8,
                "max_gap_ms": None,
                "counter": None,
                "checksum": None,
                "signals": [
                    {
                        "name": "wide_signed",
                        "start_bit": 7,
                        "length": 13,
                        "endian": "little",
                        "signed": True,
                        "scale": 0.1,
                        "offset": -2,
                        "unit": "v",
                    },
                    {
                        "name": "mux_on",
                        "start_bit": 32,
                        "length": 12,
                        "endian": "little",
                        "signed": False,
                        "scale": 0.5,
                        "offset": 10,
                        "unit": "pct",
                        "mux": {"byte": 0, "mask": 0x80, "value": 0x80},
                    },
                ],
            },
            {
                "id": dormant_id,
                "name": "Dormant",
                "expected_dlc": 8,
                "max_gap_ms": None,
                "counter": None,
                "checksum": None,
                "signals": [
                    {
                        "name": "idle",
                        "start_bit": 0,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "state",
                    }
                ],
            },
        ],
    }

    def diag_payload(
        signed_raw: int,
        low_byte: int,
        mux_value: int,
        muxed_raw: int,
        counter_value: int,
        bad_checksum: bool = False,
    ) -> bytes:
        payload = bytearray(
            payload_from_fields(
                [(0, 5, signed_raw), (8, 5, low_byte), (16, 8, muxed_raw)]
            )
        )
        payload[2] = (payload[2] & ~0x03) | mux_value
        payload[counter["byte"]] &= ~counter["mask"] & 0xFF
        payload[counter["byte"]] |= (counter_value << counter["shift"]) & counter[
            "mask"
        ]
        apply_checksum(payload, 4, checksum, 1 if bad_checksum else 0)
        return bytes(payload)

    def status_payload(raw_value: int, mux_on: bool, muxed_raw: int) -> bytes:
        payload = bytearray(
            payload_from_fields([(7, 13, raw_value), (32, 12, muxed_raw)])
        )
        if mux_on:
            payload[0] |= 0x80
        else:
            payload[0] &= 0x7F
        return bytes(payload)

    records = [
        encode_record(5, status_id, 8, status_payload(0x1FFE, True, 80), flags=0xA5),
        encode_record(10, diag_id, 4, diag_payload(0x1F, 17, 0, 55, 3), flags=0x7E),
        encode_record(11, 0x7EE, 8, bytes([0x44] * 8), flags=0x99),
        encode_record(13, diag_id, 4, diag_payload(1, 18, 1, 56, 4)),
        encode_record(14, diag_id, 4, diag_payload(2, 19, 2, 57, 0, bad_checksum=True)),
        encode_record(15, diag_id, 5, diag_payload(3, 20, 0, 58, 0)),
        encode_record(16, status_id, 8, status_payload(0x0055, False, 81), flags=0x01),
        encode_record(21, diag_id, 4, diag_payload(4, 21, 1, 59, 1)),
        encode_record(30, status_id, 8, status_payload(0x1001, True, 82)),
    ]
    network_path, trace_path = write_variant(tmp_path, "mixed_short", network, records)
    actual = run_tool(network_path, trace_path, tmp_path / "mixed_short_report.json")
    assert actual == reference_decode(network, b"".join(records))
    assert [message["name"] for message in actual["messages"]] == [
        "Diag",
        "Status",
        "Dormant",
    ]
    diag = actual["messages"][0]
    assert [warning["reason"] for warning in diag["warnings"]] == [
        "bad_checksum",
        "dlc_mismatch",
        "stale_gap",
        "counter_jump",
    ]
    assert diag["valid_frames"] == 3
    assert diag["signals"][2]["count"] == 0
    assert diag["signals"][2]["last"] is None
    status = actual["messages"][1]
    assert status["signals"][0]["count"] == 3
    assert status["signals"][1]["count"] == 2
    dormant = actual["messages"][2]
    assert dormant["frames"] == 0
    assert dormant["signals"][0]["min"] is None
    assert actual["unknown_frames"] == [
        {"timestamp_ms": 11, "id": 0x7EE, "dlc": 8, "reason": "unknown_id"}
    ]


def test_dense_multimessage_state_machine_matrix(tmp_path: Path) -> None:
    """Verify independent state across unsorted IDs, empty signals, gated frames, and odd counters."""
    alpha_id = 0x710
    beta_id = 0x100
    gamma_id = 0x701
    alpha_counter = {"byte": 4, "mask": 0x70, "shift": 4, "modulo": 5}
    beta_counter = {"byte": 0, "mask": 0x03, "shift": 0, "modulo": 3}
    alpha_checksum = {"byte": 5, "mode": "sum8"}
    gamma_checksum = {"byte": 7, "mode": "sum8"}
    network = {
        "bus": "dense-state",
        "messages": [
            {
                "id": alpha_id,
                "name": "Alpha",
                "expected_dlc": 6,
                "max_gap_ms": 12,
                "counter": alpha_counter,
                "checksum": alpha_checksum,
                "signals": [
                    {
                        "name": "temp_delta",
                        "start_bit": 0,
                        "length": 12,
                        "endian": "little",
                        "signed": True,
                        "scale": 0.25,
                        "offset": -20,
                        "unit": "c",
                    },
                    {
                        "name": "mode_bits",
                        "start_bit": 16,
                        "length": 6,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "mode",
                    },
                    {
                        "name": "muxed_load",
                        "start_bit": 24,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 0.5,
                        "offset": -5,
                        "unit": "pct",
                        "mux": {"byte": 2, "mask": 0xC0, "value": 0x80},
                    },
                ],
            },
            {
                "id": gamma_id,
                "name": "Gamma",
                "expected_dlc": 8,
                "max_gap_ms": None,
                "counter": None,
                "checksum": gamma_checksum,
                "signals": [],
            },
            {
                "id": beta_id,
                "name": "Beta",
                "expected_dlc": 8,
                "max_gap_ms": 4,
                "counter": beta_counter,
                "checksum": None,
                "signals": [
                    {
                        "name": "wide_signed",
                        "start_bit": 9,
                        "length": 17,
                        "endian": "little",
                        "signed": True,
                        "scale": 0.125,
                        "offset": 1,
                        "unit": "v",
                    },
                    {
                        "name": "mux_byte",
                        "start_bit": 48,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 2,
                        "offset": -7,
                        "unit": "pct",
                        "mux": {"byte": 4, "mask": 0x0F, "value": 0x0A},
                    },
                ],
            },
        ],
    }

    def alpha_payload(
        temp_raw: int,
        mode_raw: int,
        mux_masked_value: int,
        load_raw: int,
        counter_value: int,
        bad_checksum: bool = False,
    ) -> bytes:
        payload = bytearray(
            payload_from_fields(
                [(0, 12, temp_raw), (16, 6, mode_raw), (24, 8, load_raw)]
            )
        )
        payload[2] = (payload[2] & 0x3F) | mux_masked_value
        payload[alpha_counter["byte"]] &= ~alpha_counter["mask"] & 0xFF
        payload[alpha_counter["byte"]] |= (
            counter_value << alpha_counter["shift"]
        ) & alpha_counter["mask"]
        apply_checksum(payload, 6, alpha_checksum, 17 if bad_checksum else 0)
        return bytes(payload)

    def beta_payload(
        wide_raw: int,
        mux_nibble: int,
        mux_raw: int,
        counter_value: int,
    ) -> bytes:
        payload = bytearray(payload_from_fields([(9, 17, wide_raw), (48, 8, mux_raw)]))
        payload[4] = (payload[4] & 0xF0) | mux_nibble
        payload[beta_counter["byte"]] &= ~beta_counter["mask"] & 0xFF
        payload[beta_counter["byte"]] |= (
            counter_value << beta_counter["shift"]
        ) & beta_counter["mask"]
        return bytes(payload)

    def gamma_payload(seed: int, bad_checksum: bool = False) -> bytes:
        payload = bytearray(((seed + offset * 7) % 256 for offset in range(8)))
        apply_checksum(payload, 8, gamma_checksum, 9 if bad_checksum else 0)
        return bytes(payload)

    records = [
        encode_record(
            100, alpha_id, 6, alpha_payload((1 << 12) - 8, 9, 0x80, 30, 3), flags=0x55
        ),
        encode_record(
            101, beta_id, 8, beta_payload((1 << 17) - 10, 0x0A, 20, 1), flags=0x10
        ),
        encode_record(102, gamma_id, 8, gamma_payload(3), flags=0xFE),
        encode_record(
            103, alpha_id, 6, alpha_payload(20, 10, 0x40, 31, 4, bad_checksum=True)
        ),
        encode_record(104, beta_id, 8, beta_payload(120, 0x00, 21, 2)),
        encode_record(105, 0x7DF, 4, bytes([0xAB] * 8), flags=0x77),
        encode_record(106, gamma_id, 8, gamma_payload(6, bad_checksum=True)),
        encode_record(107, alpha_id, 9, alpha_payload(21, 11, 0x80, 32, 4)),
        encode_record(119, alpha_id, 6, alpha_payload(22, 12, 0x80, 33, 0)),
        encode_record(110, beta_id, 8, beta_payload((1 << 17) - 1, 0x0A, 22, 1)),
        encode_record(111, gamma_id, 8, gamma_payload(9), flags=0x01),
        encode_record(132, alpha_id, 6, alpha_payload(23, 13, 0xC0, 34, 1)),
    ]
    network_path, trace_path = write_variant(tmp_path, "dense_state", network, records)
    actual = run_tool(network_path, trace_path, tmp_path / "dense_state_report.json")
    expected = reference_decode(network, b"".join(records))
    assert actual == expected
    assert [message["name"] for message in actual["messages"]] == [
        "Alpha",
        "Gamma",
        "Beta",
    ]
    alpha = actual["messages"][0]
    assert alpha["frames"] == 5
    assert alpha["valid_frames"] == 3
    assert [warning["reason"] for warning in alpha["warnings"]] == [
        "bad_checksum",
        "dlc_mismatch",
        "stale_gap",
        "counter_jump",
        "stale_gap",
    ]
    assert alpha["signals"][2]["count"] == 2
    gamma = actual["messages"][1]
    assert gamma["frames"] == 3
    assert gamma["valid_frames"] == 2
    assert gamma["signals"] == []
    beta = actual["messages"][2]
    assert beta["valid_frames"] == 3
    assert [warning["reason"] for warning in beta["warnings"]] == [
        "stale_gap",
        "counter_jump",
    ]
    assert beta["signals"][1]["count"] == 2
    assert actual["unknown_frames"] == [
        {"timestamp_ms": 105, "id": 0x7DF, "dlc": 4, "reason": "unknown_id"}
    ]


def test_big_endian_signed_mux_and_gate_interactions(tmp_path: Path) -> None:
    """Verify big-endian signed signals interact correctly with checksum, DLC, mux, gap, and counter gates."""
    message_id = 0x44A
    counter = {"byte": 6, "mask": 0xE0, "shift": 5, "modulo": 7}
    checksum = {"byte": 7, "mode": "sum8"}
    network = {
        "bus": "big-endian-gates",
        "messages": [
            {
                "id": message_id,
                "name": "Pack",
                "expected_dlc": 8,
                "max_gap_ms": 6,
                "counter": counter,
                "checksum": checksum,
                "signals": [
                    {
                        "name": "pack_voltage",
                        "start_bit": 0,
                        "length": 13,
                        "endian": "big",
                        "signed": False,
                        "scale": 0.25,
                        "offset": 0,
                        "unit": "v",
                    },
                    {
                        "name": "thermal_delta",
                        "start_bit": 13,
                        "length": 9,
                        "endian": "big",
                        "signed": True,
                        "scale": 0.5,
                        "offset": -3,
                        "unit": "c",
                    },
                    {
                        "name": "little_current",
                        "start_bit": 24,
                        "length": 10,
                        "endian": "little",
                        "signed": True,
                        "scale": 0.25,
                        "offset": 1,
                        "unit": "a",
                    },
                    {
                        "name": "muxed_diag",
                        "start_bit": 40,
                        "length": 8,
                        "endian": "big",
                        "signed": False,
                        "scale": 1,
                        "offset": -10,
                        "unit": "code",
                        "mux": {"byte": 5, "mask": 3, "value": 2},
                    },
                ],
            }
        ],
    }

    def pack_payload(
        voltage_raw: int,
        thermal_raw: int,
        current_raw: int,
        diag_raw: int,
        mux_bits: int,
        counter_value: int,
        bad_checksum: bool = False,
    ) -> bytes:
        payload = bytearray(8)
        set_big_bits(payload, 0, 13, voltage_raw)
        set_big_bits(payload, 13, 9, thermal_raw)
        set_bits(payload, 24, 10, current_raw)
        set_big_bits(payload, 40, 8, diag_raw)
        payload[5] = (payload[5] & ~0x03) | mux_bits
        payload[counter["byte"]] &= ~counter["mask"] & 0xFF
        payload[counter["byte"]] |= (counter_value << counter["shift"]) & counter[
            "mask"
        ]
        apply_checksum(payload, 8, checksum, 41 if bad_checksum else 0)
        return bytes(payload)

    records = [
        encode_record(10, message_id, 8, pack_payload(0x123, 0x1F0, 0x3F0, 0xA2, 2, 0)),
        encode_record(12, message_id, 8, pack_payload(0x222, 0x010, 0x001, 0xB1, 1, 1)),
        encode_record(20, message_id, 8, pack_payload(0x010, 0x1C0, 0x3E8, 0xC2, 2, 5)),
        encode_record(
            21,
            message_id,
            8,
            pack_payload(0x011, 0x1C1, 0x3E9, 0xD2, 2, 6, bad_checksum=True),
        ),
        encode_record(22, message_id, 7, pack_payload(0x012, 0x1C2, 0x3EA, 0xE2, 2, 6)),
        encode_record(23, 0x7AB, 8, bytes([0x5A] * 8)),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "big_endian_gates", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "big_endian_gates_report.json"
    )
    expected = reference_decode(network, b"".join(records))
    assert actual == expected

    pack = actual["messages"][0]
    assert [warning["reason"] for warning in pack["warnings"]] == [
        "stale_gap",
        "counter_jump",
        "bad_checksum",
        "dlc_mismatch",
    ]
    assert pack["valid_frames"] == 3
    assert pack["signals"][0]["count"] == 3
    assert pack["signals"][0]["min"] == 4
    assert pack["signals"][0]["last"] == 4
    assert pack["signals"][1]["count"] == 3
    assert pack["signals"][1]["min"] == -35
    assert pack["signals"][3]["count"] == 2
    assert pack["signals"][3]["last"] == 184
    assert actual["unknown_frames"] == [
        {"timestamp_ms": 23, "id": 0x7AB, "dlc": 8, "reason": "unknown_id"}
    ]


def test_generated_big_endian_matrix_with_independent_message_state(
    tmp_path: Path,
) -> None:
    """Verify generated captures with mixed endian signals, muxes, counters, checksums, and interleaved IDs."""
    variants: list[tuple[str, dict, list[bytes]]] = []
    for i in range(18):
        be_id = 0x180 + i * 5
        le_id = 0x181 + i * 5
        be_counter = {"byte": 6, "mask": 0x0F, "shift": 0, "modulo": 4 + (i % 3)}
        le_counter = {"byte": 0, "mask": 0x03, "shift": 0, "modulo": 3}
        be_checksum = {"byte": 7, "mode": "sum8"}
        start_a = i % 4
        start_b = 18 + (i % 6)
        network = {
            "bus": f"generated-big-{i}",
            "messages": [
                {
                    "id": be_id,
                    "name": "BigState",
                    "expected_dlc": 8,
                    "max_gap_ms": 5 + (i % 4),
                    "counter": be_counter,
                    "checksum": be_checksum,
                    "signals": [
                        {
                            "name": "be_unsigned",
                            "start_bit": start_a,
                            "length": 11,
                            "endian": "big",
                            "signed": False,
                            "scale": 0.5,
                            "offset": i % 5,
                            "unit": "raw",
                        },
                        {
                            "name": "be_signed",
                            "start_bit": start_b,
                            "length": 8,
                            "endian": "big",
                            "signed": True,
                            "scale": -0.25,
                            "offset": 3,
                            "unit": "delta",
                        },
                        {
                            "name": "be_muxed",
                            "start_bit": 40,
                            "length": 8,
                            "endian": "big",
                            "signed": False,
                            "scale": 2,
                            "offset": -11,
                            "unit": "state",
                            "mux": {"byte": 5, "mask": 0x0C, "value": 0x08},
                        },
                    ],
                },
                {
                    "id": le_id,
                    "name": "LittleState",
                    "expected_dlc": 8,
                    "max_gap_ms": None,
                    "counter": le_counter,
                    "checksum": None,
                    "signals": [
                        {
                            "name": "le_signed",
                            "start_bit": 12,
                            "length": 12,
                            "endian": "little",
                            "signed": True,
                            "scale": 0.125,
                            "offset": -4,
                            "unit": "a",
                        }
                    ],
                },
            ],
        }

        def be_payload(
            unsigned_raw: int,
            signed_raw: int,
            mux_raw: int,
            mux_bits: int,
            counter_value: int,
            bad_checksum: bool = False,
        ) -> bytes:
            payload = bytearray(8)
            set_big_bits(payload, start_a, 11, unsigned_raw)
            set_big_bits(payload, start_b, 8, signed_raw)
            set_big_bits(payload, 40, 8, mux_raw)
            payload[5] = (payload[5] & ~0x0C) | mux_bits
            payload[be_counter["byte"]] &= ~be_counter["mask"] & 0xFF
            payload[be_counter["byte"]] |= (
                counter_value << be_counter["shift"]
            ) & be_counter["mask"]
            apply_checksum(payload, 8, be_checksum, 13 + i if bad_checksum else 0)
            return bytes(payload)

        def le_payload(signed_raw: int, counter_value: int) -> bytes:
            payload = bytearray(payload_from_fields([(12, 12, signed_raw)]))
            payload[le_counter["byte"]] &= ~le_counter["mask"] & 0xFF
            payload[le_counter["byte"]] |= (
                counter_value << le_counter["shift"]
            ) & le_counter["mask"]
            return bytes(payload)

        modulo = be_counter["modulo"]
        records = [
            encode_record(
                100 + i * 20,
                be_id,
                8,
                be_payload(100 + i, 0xF0 - i, 0x48, 0x08, 1 % modulo),
            ),
            encode_record(101 + i * 20, le_id, 8, le_payload(0xFFF - i, 0)),
            encode_record(
                102 + i * 20,
                be_id,
                8,
                be_payload(120 + i, 0x10 + i, 0x45, 0x04, 2 % modulo),
            ),
            encode_record(
                115 + i * 20, be_id, 8, be_payload(130 + i, 0x80 + i, 0x58, 0x08, 0)
            ),
            encode_record(
                116 + i * 20,
                be_id,
                8,
                be_payload(140 + i, 0x81 + i, 0x68, 0x08, 1, bad_checksum=True),
            ),
            encode_record(
                117 + i * 20, be_id, 7, be_payload(150 + i, 0x82 + i, 0x78, 0x08, 1)
            ),
            encode_record(118 + i * 20, 0x700 + i, 8, bytes([i + 3] * 8)),
            encode_record(119 + i * 20, le_id, 8, le_payload(0x050 + i, 2)),
        ]
        variants.append((f"generated_big_{i}", network, records))

    for name, network, records in variants:
        network_path, trace_path = write_variant(tmp_path, name, network, records)
        actual = run_tool(network_path, trace_path, tmp_path / f"{name}_report.json")
        expected = reference_decode(network, b"".join(records))
        assert actual == expected, name
        assert actual["messages"][0]["valid_frames"] == 3
        assert [warning["reason"] for warning in actual["messages"][0]["warnings"]][
            :2
        ] == [
            "stale_gap",
            "counter_jump",
        ]
        assert actual["messages"][0]["signals"][2]["count"] == 2
        assert actual["messages"][1]["signals"][0]["count"] == 2


def test_generated_reset_and_invalid_raw_matrix(tmp_path: Path) -> None:
    """Verify generated reset markers and invalid raw masks across endian and mux variants."""
    variants: list[tuple[str, dict, list[bytes]]] = []
    for i in range(14):
        message_id = 0x5A0 + i
        counter = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 8}
        checksum = {"byte": 6, "mode": "sum8"}
        reset = {"byte": 5, "mask": 0x80, "value": 0x80}
        network = {
            "bus": f"reset-matrix-{i}",
            "messages": [
                {
                    "id": message_id,
                    "name": "ResetMatrix",
                    "expected_dlc": 8,
                    "max_gap_ms": 4 + (i % 3),
                    "counter": counter,
                    "counter_reset": reset,
                    "checksum": checksum,
                    "signals": [
                        {
                            "name": "little_raw",
                            "start_bit": 0,
                            "length": 10,
                            "endian": "little",
                            "signed": False,
                            "scale": 0.5,
                            "offset": i % 4,
                            "unit": "x",
                            "invalid_raw": [0x3FF],
                        },
                        {
                            "name": "big_signed",
                            "start_bit": 16 + (i % 4),
                            "length": 9,
                            "endian": "big",
                            "signed": True,
                            "scale": -0.25,
                            "offset": 2,
                            "unit": "y",
                            "invalid_raw": [0x1FF],
                        },
                        {
                            "name": "muxed_raw",
                            "start_bit": 40,
                            "length": 8,
                            "endian": "big",
                            "signed": False,
                            "scale": 1,
                            "offset": -3,
                            "unit": "z",
                            "mux": {"byte": 4, "mask": 0x03, "value": 0x02},
                            "invalid_raw": [0xEE],
                        },
                    ],
                }
            ],
        }

        def payload(
            little_raw: int,
            big_raw: int,
            mux_raw: int,
            mux_bits: int,
            counter_value: int,
            reset_marker: bool = False,
            bad_checksum: bool = False,
        ) -> bytes:
            data = bytearray(8)
            set_bits(data, 0, 10, little_raw)
            set_big_bits(data, 16 + (i % 4), 9, big_raw)
            set_big_bits(data, 40, 8, mux_raw)
            data[4] = (data[4] & ~0x03) | mux_bits
            if reset_marker:
                data[5] |= 0x80
            data[counter["byte"]] &= ~counter["mask"] & 0xFF
            data[counter["byte"]] |= counter_value & counter["mask"]
            apply_checksum(data, 8, checksum, 5 + i if bad_checksum else 0)
            return bytes(data)

        records = [
            encode_record(
                100 + i * 30, message_id, 8, payload(30 + i, 0x1F0 - i, 0x40, 2, 1)
            ),
            encode_record(
                108 + i * 30,
                message_id,
                8,
                payload(0x3FF, 0x010 + i, 0x41, 2, 7, reset_marker=True),
            ),
            encode_record(
                109 + i * 30, message_id, 8, payload(32 + i, 0x1FF, 0xEE, 2, 0)
            ),
            encode_record(
                118 + i * 30,
                message_id,
                8,
                payload(33 + i, 0x020 + i, 0x42, 1, 4, bad_checksum=True),
            ),
            encode_record(
                119 + i * 30,
                message_id,
                8,
                payload(34 + i, 0x030 + i, 0x43, 2, 3, reset_marker=True),
            ),
            encode_record(
                120 + i * 30, message_id, 8, payload(35 + i, 0x040 + i, 0x44, 2, 4)
            ),
        ]
        variants.append((f"reset_matrix_{i}", network, records))

    for name, network, records in variants:
        network_path, trace_path = write_variant(tmp_path, name, network, records)
        actual = run_tool(network_path, trace_path, tmp_path / f"{name}_report.json")
        expected = reference_decode(network, b"".join(records))
        assert actual == expected, name
        message = actual["messages"][0]
        assert message["valid_frames"] == 5
        assert [warning["reason"] for warning in message["warnings"]] == [
            "stale_gap",
            "bad_checksum",
            "stale_gap",
        ]
        assert message["signals"][0]["count"] == 4
        assert message["signals"][1]["count"] == 4
        assert message["signals"][2]["count"] == 4


def test_seeded_sum_and_xor_checksums_gate_state_updates(tmp_path: Path) -> None:
    """Verify seeded sum8 and xor8 checksums gate counters, resets, muxes, and invalid raw samples."""
    variants: list[tuple[str, dict, list[bytes]]] = []
    for i in range(12):
        sum_id = 0x640 + i * 2
        xor_id = sum_id + 1
        counter = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 8}
        reset = {"byte": 5, "mask": 0x80, "value": 0x80}
        sum_checksum = {"byte": 6, "mode": "sum8", "seed": 17 + i}
        xor_checksum = {"byte": 5, "mode": "xor8", "seed": 0xA0 + i}
        network = {
            "bus": f"seeded-checksum-{i}",
            "messages": [
                {
                    "id": sum_id,
                    "name": "SeededSum",
                    "expected_dlc": 8,
                    "max_gap_ms": 6,
                    "counter": counter,
                    "counter_reset": reset,
                    "checksum": sum_checksum,
                    "signals": [
                        {
                            "name": "speed",
                            "start_bit": 0,
                            "length": 10,
                            "endian": "little",
                            "signed": False,
                            "scale": 0.5,
                            "offset": i,
                            "unit": "kph",
                            "invalid_raw": [0x3FF],
                        },
                        {
                            "name": "trim",
                            "start_bit": 10,
                            "length": 8,
                            "endian": "little",
                            "signed": True,
                            "scale": 1,
                            "offset": -3,
                            "unit": "pct",
                            "invalid_raw": [0x80],
                        },
                        {
                            "name": "muxed",
                            "start_bit": 32,
                            "length": 8,
                            "endian": "little",
                            "signed": False,
                            "scale": 1,
                            "offset": 0,
                            "unit": "raw",
                            "mux": {"byte": 4, "mask": 0x03, "value": 0x02},
                            "invalid_raw": [0xEE],
                        },
                    ],
                },
                {
                    "id": xor_id,
                    "name": "SeededXor",
                    "expected_dlc": 6,
                    "max_gap_ms": 5,
                    "counter": None,
                    "checksum": xor_checksum,
                    "signals": [
                        {
                            "name": "big_signed",
                            "start_bit": 0,
                            "length": 9,
                            "endian": "big",
                            "signed": True,
                            "scale": -1,
                            "offset": 2,
                            "unit": "deg",
                            "invalid_raw": [0x1FF],
                        },
                        {
                            "name": "mux_byte",
                            "start_bit": 24,
                            "length": 8,
                            "endian": "little",
                            "signed": False,
                            "scale": 1,
                            "offset": 0,
                            "unit": "code",
                            "mux": {"byte": 2, "mask": 0xF0, "value": 0xA0},
                            "invalid_raw": [0xAA],
                        },
                    ],
                },
            ],
        }

        def sum_payload(
            speed_raw: int,
            trim_raw: int,
            mux_bits: int,
            muxed_raw: int,
            counter_value: int,
            reset_marker: bool = False,
            bad_checksum: bool = False,
        ) -> bytes:
            data = bytearray(8)
            set_bits(data, 0, 10, speed_raw)
            set_bits(data, 10, 8, trim_raw)
            set_bits(data, 32, 8, muxed_raw)
            data[4] = (data[4] & ~0x03) | mux_bits
            if reset_marker:
                data[5] |= 0x80
            data[counter["byte"]] &= ~counter["mask"] & 0xFF
            data[counter["byte"]] |= counter_value & counter["mask"]
            apply_checksum(data, 8, sum_checksum, 19 + i if bad_checksum else 0)
            return bytes(data)

        def xor_payload(
            big_raw: int,
            mux_nibble: int,
            muxed_raw: int,
            bad_checksum: bool = False,
        ) -> bytes:
            data = bytearray(8)
            set_big_bits(data, 0, 9, big_raw)
            set_bits(data, 24, 8, muxed_raw)
            data[2] = (data[2] & 0x0F) | mux_nibble
            apply_checksum(data, 6, xor_checksum, 7 + i if bad_checksum else 0)
            return bytes(data)

        base = 1000 + i * 100
        records = [
            encode_record(base + 10, sum_id, 8, sum_payload(100 + i, 10, 2, 0x42, 1)),
            encode_record(base + 11, xor_id, 6, xor_payload(0x101 + i, 0xA0, 0x22)),
            encode_record(
                base + 18,
                sum_id,
                8,
                sum_payload(0x3FF, 11, 2, 0x43, 7, reset_marker=True),
            ),
            encode_record(base + 19, sum_id, 8, sum_payload(120 + i, 12, 1, 0x44, 0)),
            encode_record(
                base + 20,
                xor_id,
                6,
                xor_payload(0x102 + i, 0xA0, 0x33, bad_checksum=True),
            ),
            encode_record(base + 25, xor_id, 6, xor_payload(0x1FF, 0xB0, 0x44)),
            encode_record(base + 26, xor_id, 5, xor_payload(0x103 + i, 0xA0, 0x55)),
            encode_record(
                base + 30,
                sum_id,
                8,
                sum_payload(130 + i, 0x80, 2, 0xEE, 3, bad_checksum=True),
            ),
            encode_record(
                base + 31,
                sum_id,
                8,
                sum_payload(140 + i, 13, 2, 0xEE, 1, reset_marker=True),
            ),
            encode_record(base + 32, sum_id, 8, sum_payload(150 + i, 14, 2, 0x45, 2)),
            encode_record(base + 33, xor_id, 6, xor_payload(0x100 + i, 0xA0, 0xAA)),
        ]
        variants.append((f"seeded_checksum_{i}", network, records))

    for name, network, records in variants:
        network_path, trace_path = write_variant(tmp_path, name, network, records)
        actual = run_tool(network_path, trace_path, tmp_path / f"{name}_report.json")
        expected = reference_decode(network, b"".join(records))
        assert actual == expected, name
        sum_msg, xor_msg = actual["messages"]
        assert [warning["reason"] for warning in sum_msg["warnings"]] == [
            "stale_gap",
            "bad_checksum",
            "stale_gap",
        ]
        assert [warning["reason"] for warning in xor_msg["warnings"]] == [
            "bad_checksum",
            "stale_gap",
            "dlc_mismatch",
            "stale_gap",
        ]
        assert sum_msg["valid_frames"] == 5
        assert xor_msg["valid_frames"] == 3
        assert [signal["count"] for signal in sum_msg["signals"]] == [4, 5, 3]
        assert [signal["count"] for signal in xor_msg["signals"]] == [2, 1]


def test_unsupported_checksum_mode_blocks_state_updates(tmp_path: Path) -> None:
    """Verify unsupported checksum modes emit bad_checksum and do not refresh counters, gaps, or signals."""
    message_id = 0x6B0
    network = {
        "bus": "unsupported-checksum",
        "messages": [
            {
                "id": message_id,
                "name": "UnknownChecksum",
                "expected_dlc": 8,
                "max_gap_ms": 1,
                "counter": {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 16},
                "checksum": {"byte": 6, "mode": "crc4", "seed": 5},
                "signals": [
                    {
                        "name": "value",
                        "start_bit": 0,
                        "length": 12,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "raw",
                    }
                ],
            }
        ],
    }
    records = [
        encode_record(
            10,
            message_id,
            8,
            make_drive_payload(
                100, 0, 2, 10, 1, network["messages"][0]["counter"], None
            ),
        ),
        encode_record(
            11,
            message_id,
            7,
            make_drive_payload(
                101, 0, 2, 11, 2, network["messages"][0]["counter"], None
            ),
        ),
        encode_record(
            13,
            message_id,
            8,
            make_drive_payload(
                102, 0, 2, 12, 3, network["messages"][0]["counter"], None
            ),
        ),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "unsupported_checksum", network, records
    )
    actual = run_tool(network_path, trace_path, tmp_path / "unsupported_report.json")
    expected = reference_decode(network, b"".join(records))
    assert actual == expected
    message = actual["messages"][0]
    assert message["valid_frames"] == 0
    assert [warning["reason"] for warning in message["warnings"]] == [
        "bad_checksum",
        "dlc_mismatch",
        "bad_checksum",
    ]
    assert message["signals"][0]["count"] == 0


def test_explicit_cli_can_overwrite_existing_output(tmp_path: Path) -> None:
    """Verify explicit CLI mode writes the requested report path and replaces stale content."""
    network = json.loads(DEFAULT_NETWORK.read_text(encoding="utf-8"))
    network_path, trace_path = write_variant(
        tmp_path, "explicit", network, [DEFAULT_TRACE.read_bytes()[:16]]
    )
    output = tmp_path / "report.json"
    output.write_text('{"stale":true}', encoding="utf-8")
    actual = run_tool(network_path, trace_path, output)
    assert actual == reference_decode(network, trace_path.read_bytes())
    assert "stale" not in output.read_text(encoding="utf-8")


def test_file_order_not_timestamp_order_drives_state_machines(tmp_path: Path) -> None:
    """Verify counters, gaps, warnings, and unknown frames follow file order even when timestamps go backward."""
    message_id = 0x6C1
    counter = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 4}
    checksum = {"byte": 6, "mode": "sum8", "seed": 3}
    network = base_network("file-order-state", message_id, counter, checksum, 20)
    records = [
        encode_record(
            200, message_id, 8, make_drive_payload(80, 0, 2, 12, 0, counter, checksum)
        ),
        encode_record(
            120, message_id, 8, make_drive_payload(81, 1, 2, 13, 1, counter, checksum)
        ),
        encode_record(260, 0x77A, 8, bytes([1, 2, 3, 4, 5, 6, 7, 8])),
        encode_record(
            150, message_id, 8, make_drive_payload(82, 2, 1, 99, 3, counter, checksum)
        ),
        encode_record(
            400, message_id, 8, make_drive_payload(83, 3, 2, 14, 0, counter, checksum)
        ),
    ]
    network_path, trace_path = write_variant(tmp_path, "file_order", network, records)
    actual = run_tool(network_path, trace_path, tmp_path / "file_order_report.json")
    expected = reference_decode(network, b"".join(records))
    assert actual == expected
    message = actual["messages"][0]
    assert [warning["timestamp_ms"] for warning in message["warnings"]] == [
        150,
        150,
        400,
    ]
    assert [warning["reason"] for warning in message["warnings"]] == [
        "stale_gap",
        "counter_jump",
        "stale_gap",
    ]
    assert actual["unknown_frames"] == [
        {"timestamp_ms": 260, "id": 0x77A, "dlc": 8, "reason": "unknown_id"}
    ]
    assert message["signals"][2]["count"] == 3


def test_overlapping_signed_fields_and_zero_physical_values(tmp_path: Path) -> None:
    """Verify overlapping mixed-endian signals are decoded independently and exact zero is canonicalized."""
    message_id = 0x6C2
    checksum = {"byte": 7, "mode": "xor8", "seed": 0x5A}
    network = {
        "bus": "overlap-zero",
        "messages": [
            {
                "id": message_id,
                "name": "Overlap",
                "expected_dlc": 8,
                "max_gap_ms": None,
                "counter": None,
                "checksum": checksum,
                "signals": [
                    {
                        "name": "little_signed_zero",
                        "start_bit": 0,
                        "length": 8,
                        "endian": "little",
                        "signed": True,
                        "scale": 0.5,
                        "offset": 64,
                        "unit": "pct",
                        "invalid_raw": [0x7F],
                    },
                    {
                        "name": "big_overlap",
                        "start_bit": 4,
                        "length": 12,
                        "endian": "big",
                        "signed": False,
                        "scale": 0.25,
                        "offset": -10,
                        "unit": "raw",
                    },
                    {
                        "name": "muxed_negative",
                        "start_bit": 24,
                        "length": 8,
                        "endian": "little",
                        "signed": True,
                        "scale": 2,
                        "offset": 0,
                        "unit": "deg",
                        "mux": {"byte": 4, "mask": 0xF0, "value": 0xA0},
                    },
                ],
            }
        ],
    }

    def payload(
        little_raw: int, big_raw: int, mux_raw: int, mux_bits: int, bad: bool = False
    ) -> bytes:
        data = bytearray(8)
        set_bits(data, 0, 8, little_raw)
        set_big_bits(data, 4, 12, big_raw)
        set_bits(data, 24, 8, mux_raw)
        data[4] = (data[4] & 0x0F) | mux_bits
        apply_checksum(data, 8, checksum, 11 if bad else 0)
        return bytes(data)

    records = [
        encode_record(10, message_id, 8, payload(0x80, 0x040, 0xF8, 0xA0)),
        encode_record(20, message_id, 8, payload(0x7F, 0x020, 0xFE, 0xA0)),
        encode_record(30, message_id, 8, payload(0x00, 0x080, 0x7F, 0x00)),
        encode_record(40, message_id, 8, payload(0x82, 0x010, 0x81, 0xA0, bad=True)),
    ]
    network_path, trace_path = write_variant(tmp_path, "overlap_zero", network, records)
    actual = run_tool(network_path, trace_path, tmp_path / "overlap_zero_report.json")
    expected = reference_decode(network, b"".join(records))
    assert actual == expected
    signals = actual["messages"][0]["signals"]
    assert signals[0]["count"] == 3
    assert signals[0]["min"] == 0
    assert signals[0]["max"] == 120
    assert signals[0]["last"] == 64
    assert signals[1]["count"] == 3
    assert signals[1]["min"] == -2
    assert signals[2]["count"] == 2
    assert signals[2]["min"] == -16
    assert signals[2]["last"] == -4
    assert [warning["reason"] for warning in actual["messages"][0]["warnings"]] == [
        "bad_checksum"
    ]


def test_generated_order_reset_gap_and_mux_matrix(tmp_path: Path) -> None:
    """Verify generated unsorted traces with reset markers, gated frames, mux skips, and per-message state."""
    variants = []
    for i in range(14):
        primary_id = 0x710 + i
        secondary_id = 0x760 + i
        primary_counter = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 5 + (i % 3)}
        secondary_counter = {"byte": 0, "mask": 0x03, "shift": 0, "modulo": 3}
        reset = {"byte": 5, "mask": 0xC0, "value": 0x80}
        checksum = {"byte": 6, "mode": "sum8", "seed": i + 9}
        network = {
            "bus": f"order-reset-{i}",
            "messages": [
                {
                    "id": primary_id,
                    "name": "Primary",
                    "expected_dlc": 8,
                    "max_gap_ms": 25 + i,
                    "counter": primary_counter,
                    "counter_reset": reset,
                    "checksum": checksum,
                    "signals": [
                        {
                            "name": "little",
                            "start_bit": 0,
                            "length": 10,
                            "endian": "little",
                            "signed": False,
                            "scale": 1,
                            "offset": 0,
                            "unit": "raw",
                            "invalid_raw": [0x3FF],
                        },
                        {
                            "name": "big",
                            "start_bit": 16,
                            "length": 10,
                            "endian": "big",
                            "signed": True,
                            "scale": 0.5,
                            "offset": -3,
                            "unit": "b",
                        },
                        {
                            "name": "mux",
                            "start_bit": 32,
                            "length": 8,
                            "endian": "little",
                            "signed": False,
                            "scale": 2,
                            "offset": -4,
                            "unit": "m",
                            "mux": {"byte": 4, "mask": 0x03, "value": 0x02},
                            "invalid_raw": [0xEE],
                        },
                    ],
                },
                {
                    "id": secondary_id,
                    "name": "Secondary",
                    "expected_dlc": 8,
                    "max_gap_ms": 12 + i,
                    "counter": secondary_counter,
                    "checksum": None,
                    "signals": [
                        {
                            "name": "signed",
                            "start_bit": 8,
                            "length": 9,
                            "endian": "little",
                            "signed": True,
                            "scale": 1,
                            "offset": 0,
                            "unit": "s",
                        }
                    ],
                },
            ],
        }

        def primary_payload(
            little: int,
            big: int,
            mux_bits: int,
            mux_raw: int,
            counter_value: int,
            reset_marker: bool = False,
            bad_checksum: bool = False,
        ) -> bytes:
            data = bytearray(8)
            set_bits(data, 0, 10, little)
            set_big_bits(data, 16, 10, big)
            set_bits(data, 32, 8, mux_raw)
            data[4] = (data[4] & ~0x03) | mux_bits
            if reset_marker:
                data[5] = (data[5] & ~0xC0) | 0x80
            data[primary_counter["byte"]] &= ~primary_counter["mask"] & 0xFF
            data[primary_counter["byte"]] |= counter_value & primary_counter["mask"]
            apply_checksum(data, 8, checksum, i + 1 if bad_checksum else 0)
            return bytes(data)

        def secondary_payload(raw: int, counter_value: int) -> bytes:
            data = bytearray(8)
            set_bits(data, 8, 9, raw)
            data[secondary_counter["byte"]] &= ~secondary_counter["mask"] & 0xFF
            data[secondary_counter["byte"]] |= counter_value & secondary_counter["mask"]
            return bytes(data)

        modulo = primary_counter["modulo"]
        records = [
            encode_record(
                300 + i,
                primary_id,
                8,
                primary_payload(10 + i, 0x011, 2, 0x20, modulo - 2),
            ),
            encode_record(305 + i, secondary_id, 8, secondary_payload(0x1FF, 0)),
            encode_record(
                280 + i,
                primary_id,
                8,
                primary_payload(0x3FF, 0x012, 2, 0x21, modulo - 1),
            ),
            encode_record(
                340 + i,
                primary_id,
                8,
                primary_payload(20 + i, 0x1F0, 1, 0xEE, 2, reset_marker=True),
            ),
            encode_record(330 + i, 0x7FF, 8, bytes([i, 1, 2, 3, 4, 5, 6, 7])),
            encode_record(
                355 + i,
                primary_id,
                8,
                primary_payload(30 + i, 0x013, 2, 0xEE, 3, bad_checksum=True),
            ),
            encode_record(
                390 + i, primary_id, 8, primary_payload(40 + i, 0x014, 2, 0x24, 0)
            ),
            encode_record(395 + i, secondary_id, 8, secondary_payload(0x101 + i, 2)),
        ]
        variants.append((f"order_reset_{i}", network, records))

    for name, network, records in variants:
        network_path, trace_path = write_variant(tmp_path, name, network, records)
        actual = run_tool(network_path, trace_path, tmp_path / f"{name}_report.json")
        expected = reference_decode(network, b"".join(records))
        assert actual == expected
        primary = actual["messages"][0]
        secondary = actual["messages"][1]
        assert primary["valid_frames"] == 4
        assert [warning["reason"] for warning in primary["warnings"]] == [
            "stale_gap",
            "bad_checksum",
            "stale_gap",
            "counter_jump",
        ]
        assert [signal["count"] for signal in primary["signals"]] == [3, 4, 3]
        assert secondary["warnings"] == [
            {
                "timestamp_ms": 395 + int(name.rsplit("_", 1)[1]),
                "reason": "stale_gap",
                "detail": "",
            },
            {
                "timestamp_ms": 395 + int(name.rsplit("_", 1)[1]),
                "reason": "counter_jump",
                "detail": "",
            },
        ]


def test_flags_short_dlc_and_sparse_counter_mask_interactions(tmp_path: Path) -> None:
    """Verify reserved flags are ignored and sparse counter masks still use the documented mask/shift."""
    message_id = 0x730
    counter = {"byte": 1, "mask": 0xA0, "shift": 5, "modulo": 6}
    checksum = {"byte": 4, "mode": "xor8", "seed": 0x33}
    network = {
        "bus": "flags-short-dlc",
        "messages": [
            {
                "id": message_id,
                "name": "SparseCounter",
                "expected_dlc": 5,
                "max_gap_ms": 5,
                "counter": counter,
                "checksum": checksum,
                "signals": [
                    {
                        "name": "signed_nibble",
                        "start_bit": 0,
                        "length": 4,
                        "endian": "little",
                        "signed": True,
                        "scale": 1,
                        "offset": 0,
                        "unit": "n",
                    },
                    {
                        "name": "muxed_tail",
                        "start_bit": 16,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 0.5,
                        "offset": -8,
                        "unit": "m",
                        "mux": {"byte": 3, "mask": 0x30, "value": 0x20},
                    },
                ],
            }
        ],
    }

    def payload(
        raw: int, mux_raw: int, mux_bits: int, observed: int, bad: bool = False
    ) -> bytes:
        data = bytearray(8)
        set_bits(data, 0, 4, raw)
        set_bits(data, 16, 8, mux_raw)
        data[3] = (data[3] & ~0x30) | mux_bits
        data[counter["byte"]] &= ~counter["mask"] & 0xFF
        data[counter["byte"]] |= (observed << counter["shift"]) & counter["mask"]
        apply_checksum(data, 5, checksum, 9 if bad else 0)
        return bytes(data)

    records = [
        encode_record(10, message_id, 5, payload(0x7, 20, 0x20, 0), flags=0xF0),
        encode_record(12, message_id, 5, payload(0x8, 22, 0x20, 1), flags=0x01),
        encode_record(20, message_id, 5, payload(0x9, 24, 0x00, 5), flags=0xAA),
        encode_record(
            21, message_id, 5, payload(0xA, 26, 0x20, 4, bad=True), flags=0x55
        ),
        encode_record(30, message_id, 4, payload(0xB, 28, 0x20, 5), flags=0xFF),
        encode_record(40, message_id, 5, payload(0xC, 30, 0x20, 0), flags=0x7E),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "flags_short_dlc", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "flags_short_dlc_report.json"
    )
    expected = reference_decode(network, b"".join(records))
    assert actual == expected
    message = actual["messages"][0]
    assert [warning["reason"] for warning in message["warnings"]] == [
        "stale_gap",
        "counter_jump",
        "bad_checksum",
        "dlc_mismatch",
        "stale_gap",
    ]
    assert [signal["count"] for signal in message["signals"]] == [4, 3]
    assert message["signals"][0]["min"] == -8
    assert message["signals"][1]["last"] == 7


def test_high_bit_boundary_signals_and_muxed_byte_seven(tmp_path: Path) -> None:
    """Verify signals near bit 63, byte-seven muxing, and signed big-endian boundary values."""
    message_id = 0x731
    checksum = {"byte": 5, "mode": "sum8", "seed": 0x21}
    network = {
        "bus": "high-bit-boundary",
        "messages": [
            {
                "id": message_id,
                "name": "Boundary",
                "expected_dlc": 8,
                "max_gap_ms": None,
                "counter": None,
                "checksum": checksum,
                "signals": [
                    {
                        "name": "last_nibble",
                        "start_bit": 60,
                        "length": 4,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "n",
                    },
                    {
                        "name": "big_signed_last_byte",
                        "start_bit": 56,
                        "length": 8,
                        "endian": "big",
                        "signed": True,
                        "scale": 1,
                        "offset": 0,
                        "unit": "b",
                        "invalid_raw": [0x80],
                    },
                    {
                        "name": "muxed_high",
                        "start_bit": 48,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 2,
                        "offset": -10,
                        "unit": "m",
                        "mux": {"byte": 7, "mask": 0x0F, "value": 0x0A},
                    },
                ],
            }
        ],
    }

    def payload(last_byte: int, mux_raw: int, bad: bool = False) -> bytes:
        data = bytearray(8)
        data[7] = last_byte
        data[6] = mux_raw
        apply_checksum(data, 8, checksum, 5 if bad else 0)
        return bytes(data)

    records = [
        encode_record(100, message_id, 8, payload(0x7A, 10)),
        encode_record(110, message_id, 8, payload(0x8A, 12)),
        encode_record(120, message_id, 8, payload(0xF5, 14)),
        encode_record(130, message_id, 8, payload(0x0A, 16, bad=True)),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "high_bit_boundary", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "high_bit_boundary_report.json"
    )
    expected = reference_decode(network, b"".join(records))
    assert actual == expected
    message = actual["messages"][0]
    assert message["signals"][0]["last"] == 15
    assert message["signals"][1]["count"] == 3
    assert message["signals"][1]["min"] == -118
    assert message["signals"][1]["last"] == -11
    assert message["signals"][2]["count"] == 2
    assert message["signals"][2]["max"] == 14
    assert [warning["reason"] for warning in message["warnings"]] == ["bad_checksum"]


def test_generated_short_frame_counter_and_boundary_matrix(tmp_path: Path) -> None:
    """Verify generated short-DLC traces with flags, muxes, stale gaps, bad checksums, and high-bit signals."""
    for i in range(12):
        message_id = 0x740 + i
        counter = {"byte": 2, "mask": 0x1C, "shift": 2, "modulo": 8}
        checksum = {"byte": 3, "mode": "sum8" if i % 2 == 0 else "xor8", "seed": 4 + i}
        network = {
            "bus": f"short-boundary-{i}",
            "messages": [
                {
                    "id": message_id,
                    "name": "ShortBoundary",
                    "expected_dlc": 4,
                    "max_gap_ms": 7 + i,
                    "counter": counter,
                    "checksum": checksum,
                    "signals": [
                        {
                            "name": "low_signed",
                            "start_bit": 0,
                            "length": 5,
                            "endian": "little",
                            "signed": True,
                            "scale": 1,
                            "offset": 0,
                            "unit": "ls",
                        },
                        {
                            "name": "big_mid",
                            "start_bit": 8,
                            "length": 8,
                            "endian": "big",
                            "signed": False,
                            "scale": 0.25,
                            "offset": -4,
                            "unit": "bm",
                        },
                        {
                            "name": "mux_short",
                            "start_bit": 24,
                            "length": 6,
                            "endian": "little",
                            "signed": False,
                            "scale": 1,
                            "offset": 0,
                            "unit": "mx",
                            "mux": {"byte": 1, "mask": 0x03, "value": 0x02},
                            "invalid_raw": [0x3F],
                        },
                    ],
                }
            ],
        }

        def payload(
            low: int,
            big: int,
            mux_raw: int,
            mux_bits: int,
            counter_value: int,
            bad: bool = False,
        ) -> bytes:
            data = bytearray(8)
            set_bits(data, 0, 5, low)
            set_big_bits(data, 8, 8, big)
            set_bits(data, 24, 6, mux_raw)
            data[1] = (data[1] & ~0x03) | mux_bits
            data[counter["byte"]] &= ~counter["mask"] & 0xFF
            data[counter["byte"]] |= (counter_value << counter["shift"]) & counter[
                "mask"
            ]
            apply_checksum(data, 4, checksum, 3 + i if bad else 0)
            return bytes(data)

        records = [
            encode_record(
                10 + i, message_id, 4, payload(0x01, 0x10 + i, 20, 0x02, 0), flags=0x80
            ),
            encode_record(
                12 + i, message_id, 4, payload(0x1F, 0x20 + i, 21, 0x02, 1), flags=0x01
            ),
            encode_record(
                30 + i,
                message_id,
                4,
                payload(0x10, 0x30 + i, 0x3F, 0x02, 4),
                flags=0x02,
            ),
            encode_record(
                31 + i,
                message_id,
                4,
                payload(0x11, 0x40 + i, 22, 0x00, 5, bad=True),
                flags=0x03,
            ),
            encode_record(
                45 + i, message_id, 3, payload(0x12, 0x50 + i, 23, 0x02, 6), flags=0x04
            ),
            encode_record(
                50 + i, message_id, 4, payload(0x13, 0x60 + i, 24, 0x02, 7), flags=0x05
            ),
        ]
        network_path, trace_path = write_variant(
            tmp_path, f"short_boundary_{i}", network, records
        )
        actual = run_tool(
            network_path, trace_path, tmp_path / f"short_boundary_{i}_report.json"
        )
        expected = reference_decode(network, b"".join(records))
        assert actual == expected
        message = actual["messages"][0]
        expected_reasons = [
            "stale_gap",
            "counter_jump",
            "bad_checksum",
            "dlc_mismatch",
            "stale_gap",
            "counter_jump",
        ]
        if i == 11:
            expected_reasons = expected_reasons[1:]
        assert [
            warning["reason"] for warning in message["warnings"]
        ] == expected_reasons
        assert [signal["count"] for signal in message["signals"]] == [
            4,
            4,
            3 if i == 5 else 4,
        ]


def test_invalid_raw_is_unsigned_before_sign_and_warnings_still_compose(
    tmp_path: Path,
) -> None:
    """Verify invalid_raw uses the unsigned pattern before sign conversion and does not stop state warnings."""
    message_id = 0x780
    counter = {"byte": 7, "mask": 0x03, "shift": 0, "modulo": 4}
    checksum = {"byte": 3, "mode": "xor8", "seed": 0x6D}
    network = {
        "bus": "invalid-before-sign",
        "messages": [
            {
                "id": message_id,
                "name": "InvalidBoundary",
                "expected_dlc": 8,
                "max_gap_ms": 9,
                "counter": counter,
                "checksum": checksum,
                "signals": [
                    {
                        "name": "little_signed_neg_scale",
                        "start_bit": 0,
                        "length": 8,
                        "endian": "little",
                        "signed": True,
                        "scale": -0.5,
                        "offset": -1,
                        "unit": "a",
                        "invalid_raw": [0xFF],
                    },
                    {
                        "name": "big_signed_neg_scale",
                        "start_bit": 8,
                        "length": 9,
                        "endian": "big",
                        "signed": True,
                        "scale": -2,
                        "offset": 5,
                        "unit": "b",
                        "invalid_raw": [0x100],
                    },
                    {
                        "name": "zero_canonical",
                        "start_bit": 32,
                        "length": 8,
                        "endian": "little",
                        "signed": True,
                        "scale": 0.25,
                        "offset": -1,
                        "unit": "z",
                    },
                    {
                        "name": "muxed_sparse",
                        "start_bit": 40,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "m",
                        "mux": {"byte": 6, "mask": 0xC0, "value": 0x80},
                        "invalid_raw": [0x12],
                    },
                ],
            }
        ],
    }

    def payload(
        little_raw: int,
        big_raw: int,
        zero_raw: int,
        mux_raw: int,
        mux_bits: int,
        counter_value: int,
        bad: bool = False,
    ) -> bytes:
        data = bytearray(8)
        set_bits(data, 0, 8, little_raw)
        set_big_bits(data, 8, 9, big_raw)
        set_bits(data, 32, 8, zero_raw)
        set_bits(data, 40, 8, mux_raw)
        data[6] = (data[6] & ~0xC0) | mux_bits
        data[counter["byte"]] &= ~counter["mask"] & 0xFF
        data[counter["byte"]] |= (counter_value << counter["shift"]) & counter["mask"]
        apply_checksum(data, 8, checksum, 7 if bad else 0)
        return bytes(data)

    records = [
        encode_record(10, message_id, 8, payload(0xFE, 0x0FE, 4, 0x11, 0x00, 0)),
        encode_record(15, message_id, 8, payload(0xFF, 0x100, 8, 0x12, 0x80, 1)),
        encode_record(30, message_id, 8, payload(0x80, 0x1FF, 4, 0x14, 0x80, 3)),
        encode_record(
            31, message_id, 8, payload(0x01, 0x000, 4, 0x15, 0x80, 0, bad=True)
        ),
        encode_record(50, message_id, 7, payload(0x02, 0x001, 5, 0x16, 0x80, 0)),
        encode_record(70, message_id, 8, payload(0x01, 0x000, 4, 0x17, 0x00, 0)),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "invalid_before_sign", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "invalid_before_sign_report.json"
    )
    expected = reference_decode(network, b"".join(records))
    assert actual == expected
    message = actual["messages"][0]
    assert [warning["reason"] for warning in message["warnings"]] == [
        "stale_gap",
        "counter_jump",
        "bad_checksum",
        "dlc_mismatch",
        "stale_gap",
    ]
    assert [signal["count"] for signal in message["signals"]] == [3, 3, 4, 1]
    assert message["signals"][0]["min"] == -1.5
    assert message["signals"][0]["max"] == 63
    assert message["signals"][1]["min"] == -503
    assert message["signals"][1]["last"] == 5
    assert message["signals"][2]["min"] == 0
    assert message["signals"][2]["last"] == 0
    assert message["signals"][3]["last"] == 20


def test_generated_checksum_uses_dlc_window_not_payload_padding(
    tmp_path: Path,
) -> None:
    """Verify checksum modes use only bytes inside the reported DLC even when padding bytes vary."""
    for i in range(16):
        message_id = 0x790 + i
        dlc = 3 + (i % 4)
        counter = {"byte": 1, "mask": 0xC0, "shift": 6, "modulo": 4}
        checksum = {
            "byte": dlc - 1,
            "mode": "sum8" if i % 2 == 0 else "xor8",
            "seed": 0x20 + i,
        }
        network = {
            "bus": f"dlc-window-{i}",
            "messages": [
                {
                    "id": message_id,
                    "name": "WindowedChecksum",
                    "expected_dlc": dlc,
                    "max_gap_ms": 10,
                    "counter": counter,
                    "checksum": checksum,
                    "signals": [
                        {
                            "name": "low_bits",
                            "start_bit": 0,
                            "length": 6,
                            "endian": "little",
                            "signed": False,
                            "scale": 1,
                            "offset": 0,
                            "unit": "l",
                        },
                        {
                            "name": "counter_shadow",
                            "start_bit": 14,
                            "length": 2,
                            "endian": "little",
                            "signed": False,
                            "scale": 1,
                            "offset": 0,
                            "unit": "c",
                        },
                        {
                            "name": "muxed_inner",
                            "start_bit": 8,
                            "length": 5,
                            "endian": "little",
                            "signed": False,
                            "scale": 2,
                            "offset": -3,
                            "unit": "m",
                            "mux": {"byte": 1, "mask": 0x20, "value": 0x20},
                        },
                    ],
                }
            ],
        }

        def payload(
            raw: int,
            inner: int,
            counter_value: int,
            pad_seed: int,
            bad: bool = False,
        ) -> bytes:
            data = bytearray(8)
            set_bits(data, 0, 6, raw)
            data[1] = inner & 0x3F
            data[1] &= ~counter["mask"] & 0xFF
            data[1] |= (counter_value << counter["shift"]) & counter["mask"]
            for pad_index in range(dlc, 8):
                data[pad_index] = (pad_seed + pad_index * 29 + i) % 256
            apply_checksum(data, dlc, checksum, 5 + i if bad else 0)
            for pad_index in range(dlc, 8):
                data[pad_index] = (pad_seed + pad_index * 37 + i * 11) % 256
            return bytes(data)

        records = [
            encode_record(10 + i, message_id, dlc, payload(3, 0x20, 0, 1), flags=0x10),
            encode_record(15 + i, message_id, dlc, payload(4, 0x00, 1, 2), flags=0x20),
            encode_record(31 + i, message_id, dlc, payload(5, 0x20, 3, 3), flags=0x30),
            encode_record(
                32 + i, message_id, dlc, payload(6, 0x20, 0, 4, bad=True), flags=0x40
            ),
            encode_record(
                50 + i, message_id, dlc - 1, payload(7, 0x20, 0, 5), flags=0x50
            ),
            encode_record(60 + i, message_id, dlc, payload(8, 0x20, 0, 6), flags=0x60),
        ]
        network_path, trace_path = write_variant(
            tmp_path, f"dlc_window_{i}", network, records
        )
        actual = run_tool(
            network_path, trace_path, tmp_path / f"dlc_window_{i}_report.json"
        )
        expected = reference_decode(network, b"".join(records))
        assert actual == expected
        message = actual["messages"][0]
        assert [warning["reason"] for warning in message["warnings"]] == [
            "stale_gap",
            "counter_jump",
            "bad_checksum",
            "dlc_mismatch",
            "stale_gap",
        ]
        assert [signal["count"] for signal in message["signals"]] == [4, 4, 3]


def test_missing_seed_one_bit_signed_and_zero_gap_edges(tmp_path: Path) -> None:
    """Verify missing checksum seeds, one-bit signed fields, zero max-gap, and repeated timestamps."""
    for i in range(12):
        message_id = 0x7C0 + i
        counter = {"byte": 2, "mask": 0x30, "shift": 4, "modulo": 4}
        checksum = {
            "byte": 0 if i % 2 == 0 else 3,
            "mode": "sum8" if i % 2 == 0 else "xor8",
        }
        network = {
            "bus": f"zero-gap-bit-{i}",
            "messages": [
                {
                    "id": message_id,
                    "name": "ZeroGapBit",
                    "expected_dlc": 4,
                    "max_gap_ms": 0,
                    "counter": counter,
                    "checksum": checksum,
                    "signals": [
                        {
                            "name": "little_one_signed",
                            "start_bit": 8,
                            "length": 1,
                            "endian": "little",
                            "signed": True,
                            "scale": 3,
                            "offset": 1,
                            "unit": "lo",
                        },
                        {
                            "name": "big_one_signed",
                            "start_bit": 8,
                            "length": 1,
                            "endian": "big",
                            "signed": True,
                            "scale": -4,
                            "offset": 2,
                            "unit": "bo",
                        },
                        {
                            "name": "muxed_low_nibble",
                            "start_bit": 16,
                            "length": 4,
                            "endian": "little",
                            "signed": False,
                            "scale": 2,
                            "offset": -1,
                            "unit": "mx",
                            "mux": {"byte": 2, "mask": 0x80, "value": 0x80},
                            "invalid_raw": [0x0F],
                        },
                    ],
                }
            ],
        }

        def payload(
            little_bit: int,
            big_bit: int,
            mux_raw: int,
            mux_on: bool,
            counter_value: int,
            bad: bool = False,
        ) -> bytes:
            data = bytearray(8)
            set_bits(data, 8, 1, little_bit)
            set_big_bits(data, 8, 1, big_bit)
            set_bits(data, 16, 4, mux_raw)
            data[2] &= ~counter["mask"] & 0xFF
            data[2] |= (counter_value << counter["shift"]) & counter["mask"]
            if mux_on:
                data[2] |= 0x80
            else:
                data[2] &= 0x7F
            apply_checksum(data, 4, checksum, 9 + i if bad else 0)
            return bytes(data)

        records = [
            encode_record(100, message_id, 4, payload(0, 0, 5, True, 0), flags=0xAA),
            encode_record(100, message_id, 4, payload(1, 1, 0x0F, True, 1), flags=0xBB),
            encode_record(99, message_id, 4, payload(0, 1, 6, False, 2), flags=0xCC),
            encode_record(101, message_id, 4, payload(1, 0, 7, True, 0), flags=0xDD),
            encode_record(
                102, message_id, 4, payload(0, 0, 8, True, 1, bad=True), flags=0xEE
            ),
            encode_record(103, message_id, 3, payload(1, 1, 9, True, 1), flags=0xEF),
            encode_record(104, message_id, 4, payload(0, 1, 9, True, 1), flags=0xF0),
        ]
        network_path, trace_path = write_variant(
            tmp_path, f"zero_gap_bit_{i}", network, records
        )
        actual = run_tool(
            network_path, trace_path, tmp_path / f"zero_gap_bit_{i}_report.json"
        )
        expected = reference_decode(network, b"".join(records))
        assert actual == expected
        message = actual["messages"][0]
        assert [warning["reason"] for warning in message["warnings"]] == [
            "stale_gap",
            "counter_jump",
            "bad_checksum",
            "dlc_mismatch",
            "stale_gap",
        ]
        assert [signal["count"] for signal in message["signals"]] == [5, 5, 3]
        assert message["signals"][0]["min"] == -2
        assert message["signals"][0]["max"] == 1
        assert message["signals"][1]["max"] == 6
        assert message["signals"][2]["last"] == 17


def test_generated_reset_after_gated_noise_and_all_null_muxes(tmp_path: Path) -> None:
    """Verify reset frames after gated failures suppress jumps and all-null muxed signals stay null."""
    for i in range(14):
        message_id = 0x7D0 + i
        counter = {"byte": 6, "mask": 0x70, "shift": 4, "modulo": 5}
        reset = {"byte": 6, "mask": 0x80, "value": 0x80}
        checksum = {
            "byte": 5,
            "mode": "xor8" if i % 2 else "sum8",
            "seed": i + 3,
        }
        network = {
            "bus": f"reset-after-gates-{i}",
            "messages": [
                {
                    "id": message_id,
                    "name": "ResetAfterGates",
                    "expected_dlc": 8,
                    "max_gap_ms": 3 + (i % 3),
                    "counter": counter,
                    "counter_reset": reset,
                    "checksum": checksum,
                    "signals": [
                        {
                            "name": "signed_tail",
                            "start_bit": 0,
                            "length": 7,
                            "endian": "little",
                            "signed": True,
                            "scale": 1,
                            "offset": 0,
                            "unit": "st",
                        },
                        {
                            "name": "never_sampled_mux",
                            "start_bit": 24,
                            "length": 4,
                            "endian": "little",
                            "signed": False,
                            "scale": 1,
                            "offset": 0,
                            "unit": "ns",
                            "mux": {"byte": 4, "mask": 0x03, "value": 0x02},
                            "invalid_raw": [0x0A, 0x0B, 0x0C],
                        },
                    ],
                }
            ],
        }

        def payload(
            tail_raw: int,
            mux_raw: int,
            mux_bits: int,
            counter_value: int,
            reset_marker: bool = False,
            bad: bool = False,
        ) -> bytes:
            data = bytearray(8)
            set_bits(data, 0, 7, tail_raw)
            set_bits(data, 24, 4, mux_raw)
            data[4] = (data[4] & ~0x03) | mux_bits
            data[6] &= ~(counter["mask"] | reset["mask"]) & 0xFF
            data[6] |= (counter_value << counter["shift"]) & counter["mask"]
            if reset_marker:
                data[6] |= reset["value"]
            apply_checksum(data, 8, checksum, 11 + i if bad else 0)
            return bytes(data)

        records = [
            encode_record(10 + i, message_id, 8, payload(0x01, 0x0A, 0x02, 3)),
            encode_record(
                20 + i, message_id, 8, payload(0x02, 0x0B, 0x02, 4, bad=True)
            ),
            encode_record(22 + i, message_id, 7, payload(0x03, 0x0C, 0x02, 4)),
            encode_record(
                30 + i, message_id, 8, payload(0x7F, 0x0A, 0x02, 1, reset_marker=True)
            ),
            encode_record(31 + i, message_id, 8, payload(0x40, 0x0D, 0x00, 2)),
            encode_record(40 + i, message_id, 8, payload(0x3F, 0x0B, 0x02, 0)),
            encode_record(41 + i, 0x7F0 + i, 15, bytes([i & 0xFF] * 8), flags=0x99),
        ]
        network_path, trace_path = write_variant(
            tmp_path, f"reset_after_gates_{i}", network, records
        )
        actual = run_tool(
            network_path, trace_path, tmp_path / f"reset_after_gates_{i}_report.json"
        )
        expected = reference_decode(network, b"".join(records))
        assert actual == expected
        message = actual["messages"][0]
        assert [warning["reason"] for warning in message["warnings"]] == [
            "bad_checksum",
            "dlc_mismatch",
            "stale_gap",
            "stale_gap",
            "counter_jump",
        ]
        assert message["valid_frames"] == 4
        assert message["signals"][0]["count"] == 4
        assert message["signals"][0]["min"] == -64
        assert message["signals"][1] == {
            "name": "never_sampled_mux",
            "unit": "ns",
            "count": 0,
            "min": None,
            "max": None,
            "last": None,
            "last_timestamp_ms": None,
        }
        assert actual["unknown_frames"] == [
            {"timestamp_ms": 41 + i, "id": 0x7F0 + i, "dlc": 15, "reason": "unknown_id"}
        ]


def test_generated_message_order_same_timestamp_and_fractional_stats(
    tmp_path: Path,
) -> None:
    """Verify network message order, same-timestamp file order, and fractional negative-scale stats."""
    for i in range(10):
        alpha_id = 0x320 + i
        beta_id = 0x120 + i
        gamma_id = 0x520 + i
        alpha_counter = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 4}
        alpha_checksum = {"byte": 6, "mode": "sum8", "seed": i}
        beta_checksum = {"byte": 4, "mode": "xor8", "seed": 0x55 + i}
        network = {
            "bus": f"same-timestamp-order-{i}",
            "messages": [
                {
                    "id": gamma_id,
                    "name": "GammaFirst",
                    "expected_dlc": 8,
                    "max_gap_ms": None,
                    "counter": None,
                    "checksum": None,
                    "signals": [],
                },
                {
                    "id": alpha_id,
                    "name": "AlphaSecond",
                    "expected_dlc": 8,
                    "max_gap_ms": 0,
                    "counter": alpha_counter,
                    "checksum": alpha_checksum,
                    "signals": [
                        {
                            "name": "frac_negative",
                            "start_bit": 0,
                            "length": 11,
                            "endian": "little",
                            "signed": True,
                            "scale": -0.125,
                            "offset": 1.5,
                            "unit": "fn",
                        },
                        {
                            "name": "big_fraction",
                            "start_bit": 16,
                            "length": 12,
                            "endian": "big",
                            "signed": False,
                            "scale": 0.1,
                            "offset": -20,
                            "unit": "bf",
                        },
                    ],
                },
                {
                    "id": beta_id,
                    "name": "BetaThird",
                    "expected_dlc": 5,
                    "max_gap_ms": 1,
                    "counter": None,
                    "checksum": beta_checksum,
                    "signals": [
                        {
                            "name": "muxed_beta",
                            "start_bit": 8,
                            "length": 7,
                            "endian": "little",
                            "signed": True,
                            "scale": 0.25,
                            "offset": -2,
                            "unit": "mb",
                            "mux": {"byte": 3, "mask": 0x03, "value": 0x01},
                        }
                    ],
                },
            ],
        }

        def alpha_payload(
            frac_raw: int,
            big_raw: int,
            counter_value: int,
            bad: bool = False,
        ) -> bytes:
            data = bytearray(8)
            set_bits(data, 0, 11, frac_raw)
            set_big_bits(data, 16, 12, big_raw)
            data[alpha_counter["byte"]] &= ~alpha_counter["mask"] & 0xFF
            data[alpha_counter["byte"]] |= counter_value & alpha_counter["mask"]
            apply_checksum(data, 8, alpha_checksum, 3 + i if bad else 0)
            return bytes(data)

        def beta_payload(raw: int, mux_bits: int, bad: bool = False) -> bytes:
            data = bytearray(8)
            set_bits(data, 8, 7, raw)
            data[3] = (data[3] & ~0x03) | mux_bits
            apply_checksum(data, 5, beta_checksum, 5 + i if bad else 0)
            return bytes(data)

        records = [
            encode_record(100, alpha_id, 8, alpha_payload(0x7FF, 0x010, 0), flags=0x01),
            encode_record(100, beta_id, 5, beta_payload(0x7F, 0x01), flags=0x02),
            encode_record(
                100, gamma_id, 8, bytes([i, 1, 2, 3, 4, 5, 6, 7]), flags=0x03
            ),
            encode_record(100, alpha_id, 8, alpha_payload(0x001, 0x020, 1), flags=0x04),
            encode_record(101, alpha_id, 8, alpha_payload(0x400, 0x030, 3), flags=0x05),
            encode_record(
                102, beta_id, 5, beta_payload(0x01, 0x01, bad=True), flags=0x06
            ),
            encode_record(103, beta_id, 5, beta_payload(0x02, 0x00), flags=0x07),
            encode_record(104, alpha_id, 9, alpha_payload(0x002, 0x040, 0), flags=0x08),
            encode_record(
                100, 0x700 + i, 9, bytes([9, 8, 7, 6, 5, 4, 3, 2]), flags=0x09
            ),
        ]
        network_path, trace_path = write_variant(
            tmp_path, f"same_ts_order_{i}", network, records
        )
        actual = run_tool(
            network_path, trace_path, tmp_path / f"same_ts_order_{i}_report.json"
        )
        expected = reference_decode(network, b"".join(records))
        assert actual == expected
        assert [message["name"] for message in actual["messages"]] == [
            "GammaFirst",
            "AlphaSecond",
            "BetaThird",
        ]
        alpha = actual["messages"][1]
        beta = actual["messages"][2]
        assert [warning["reason"] for warning in alpha["warnings"]] == [
            "stale_gap",
            "counter_jump",
            "dlc_mismatch",
        ]
        assert [warning["reason"] for warning in beta["warnings"]] == [
            "bad_checksum",
            "stale_gap",
        ]
        assert alpha["signals"][0]["min"] == 1.375
        assert alpha["signals"][0]["max"] == 129.5
        assert alpha["signals"][1]["min"] == -18.4
        assert beta["signals"][0]["count"] == 1
        assert actual["unknown_frames"] == [
            {"timestamp_ms": 100, "id": 0x700 + i, "dlc": 9, "reason": "unknown_id"}
        ]


def test_generated_wide_cross_byte_signed_fields_with_gates(
    tmp_path: Path,
) -> None:
    """Verify wide signed fields crossing bytes compose with checksum, DLC, mux, and stale-gap gates."""
    for i in range(12):
        message_id = 0x680 + i
        checksum = {
            "byte": 7,
            "mode": "sum8" if i % 2 == 0 else "xor8",
            "seed": 0x12 + i,
        }
        network = {
            "bus": f"wide-cross-byte-{i}",
            "messages": [
                {
                    "id": message_id,
                    "name": "WideCrossByte",
                    "expected_dlc": 8,
                    "max_gap_ms": 4,
                    "counter": None,
                    "checksum": checksum,
                    "signals": [
                        {
                            "name": "little_31",
                            "start_bit": 1,
                            "length": 31,
                            "endian": "little",
                            "signed": True,
                            "scale": 0.0625,
                            "offset": -2.5,
                            "unit": "l31",
                            "invalid_raw": [0x7FFFFFFF],
                        },
                        {
                            "name": "big_20",
                            "start_bit": 16 + (i % 3),
                            "length": 20,
                            "endian": "big",
                            "signed": True,
                            "scale": -0.03125,
                            "offset": 10.25,
                            "unit": "b20",
                        },
                        {
                            "name": "tail_mux",
                            "start_bit": 40,
                            "length": 8,
                            "endian": "little",
                            "signed": False,
                            "scale": 0.5,
                            "offset": -100,
                            "unit": "tm",
                            "mux": {"byte": 0, "mask": 0x01, "value": 0x01},
                        },
                    ],
                }
            ],
        }

        def payload(
            little_raw: int,
            big_raw: int,
            tail_raw: int,
            mux_on: bool,
            bad: bool = False,
        ) -> bytes:
            data = bytearray(8)
            set_bits(data, 1, 31, little_raw)
            set_big_bits(data, 16 + (i % 3), 20, big_raw)
            set_bits(data, 40, 8, tail_raw)
            if mux_on:
                data[0] |= 0x01
            else:
                data[0] &= 0xFE
            apply_checksum(data, 8, checksum, 17 + i if bad else 0)
            return bytes(data)

        records = [
            encode_record(
                10 + i, message_id, 8, payload(0x00000001, 0x00010, 20, True)
            ),
            encode_record(
                12 + i, message_id, 8, payload(0x7FFFFFFF, 0x80000, 21, True)
            ),
            encode_record(
                20 + i, message_id, 8, payload(0x00000002, 0x00020, 22, True, bad=True)
            ),
            encode_record(
                21 + i, message_id, 7, payload(0x00000003, 0x00030, 23, True)
            ),
            encode_record(
                30 + i, message_id, 8, payload(0x40000000, 0xFFFFF, 24, False)
            ),
        ]
        network_path, trace_path = write_variant(
            tmp_path, f"wide_cross_byte_{i}", network, records
        )
        actual = run_tool(
            network_path, trace_path, tmp_path / f"wide_cross_byte_{i}_report.json"
        )
        expected = reference_decode(network, b"".join(records))
        assert actual == expected
        message = actual["messages"][0]
        assert [warning["reason"] for warning in message["warnings"]] == [
            "bad_checksum",
            "dlc_mismatch",
            "stale_gap",
        ]
        assert [signal["count"] for signal in message["signals"]] == [3, 3, 2]
        expected_little_min = [-2050.5, -264194.5, -395266.5][i % 3]
        expected_little_max = [524285.5625, 395261.4375, 460797.4375][i % 3]
        assert message["signals"][0]["min"] == expected_little_min
        assert message["signals"][0]["max"] == expected_little_max
        assert message["signals"][1]["max"] == 16394.25
        assert message["signals"][2]["last"] == -89.5


def test_checksum_byte_outside_dlc_and_tail_signal_decode(tmp_path: Path) -> None:
    """Verify checksum bytes outside the DLC window are compared and payload tail signals still decode."""
    message_id = 0x6D1
    counter = {"byte": 4, "mask": 0x03, "shift": 0, "modulo": 4}
    checksum = {"byte": 7, "mode": "sum8", "seed": 5}
    network = {
        "bus": "short-dlc-tail-checksum",
        "messages": [
            {
                "id": message_id,
                "name": "ShortTail",
                "expected_dlc": 5,
                "max_gap_ms": 10,
                "counter": counter,
                "counter_reset": None,
                "checksum": checksum,
                "signals": [
                    {
                        "name": "front_raw",
                        "start_bit": 0,
                        "length": 12,
                        "endian": "little",
                        "signed": False,
                        "scale": 0.25,
                        "offset": 0,
                        "unit": "v",
                    },
                    {
                        "name": "checksum_tail",
                        "start_bit": 56,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "raw",
                    },
                    {
                        "name": "muxed_tail",
                        "start_bit": 48,
                        "length": 8,
                        "endian": "little",
                        "signed": True,
                        "scale": 0.5,
                        "offset": -3,
                        "unit": "m",
                        "mux": {"byte": 6, "mask": 0x80, "value": 0x80},
                    },
                ],
            }
        ],
    }

    def payload(
        raw: int, tail_raw: int, counter_value: int, bad: bool = False
    ) -> bytes:
        data = bytearray(payload_from_fields([(0, 12, raw), (48, 8, tail_raw)]))
        data[counter["byte"]] &= ~counter["mask"] & 0xFF
        data[counter["byte"]] |= counter_value & counter["mask"]
        apply_checksum(data, 5, checksum, 9 if bad else 0)
        return bytes(data)

    records = [
        encode_record(10, message_id, 5, payload(40, 0x81, 0)),
        encode_record(12, message_id, 5, payload(44, 0x82, 1)),
        encode_record(25, message_id, 5, payload(48, 0x83, 3)),
        encode_record(27, message_id, 5, payload(52, 0x84, 0, bad=True)),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "short_dlc_tail_checksum", network, records
    )
    actual = run_tool(network_path, trace_path, tmp_path / "short_tail_report.json")
    expected = reference_decode(network, b"".join(records))
    assert actual == expected

    message = actual["messages"][0]
    assert [warning["reason"] for warning in message["warnings"]] == [
        "stale_gap",
        "counter_jump",
        "bad_checksum",
    ]
    assert message["valid_frames"] == 3
    assert [signal["count"] for signal in message["signals"]] == [3, 3, 3]
    assert message["signals"][1]["last"] == checksum_value(
        payload(48, 0x83, 3), 5, checksum
    )


def test_unknown_high_dlc_frames_do_not_refresh_known_message_state(
    tmp_path: Path,
) -> None:
    """Verify unknown frames with odd DLC values stay in unknown_frames and do not affect known state."""
    message_id = 0x641
    counter = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 8}
    checksum = {"byte": 6, "mode": "xor8", "seed": 0x44}
    network = base_network(
        "unknown-high-dlc-state",
        message_id,
        counter,
        checksum,
        max_gap_ms=5,
    )
    records = [
        encode_record(
            100, message_id, 8, make_drive_payload(90, 0, 2, 10, 0, counter, checksum)
        ),
        encode_record(1000, 0x777, 15, bytes([1, 2, 3, 4, 5, 6, 7, 8]), flags=0xA5),
        encode_record(
            103, message_id, 8, make_drive_payload(91, 1, 2, 11, 1, counter, checksum)
        ),
        encode_record(
            120, message_id, 9, make_drive_payload(92, 2, 2, 12, 2, counter, checksum)
        ),
        encode_record(
            125, message_id, 8, make_drive_payload(93, 3, 2, 13, 2, counter, checksum)
        ),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "unknown_high_dlc_state", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "unknown_high_dlc_report.json"
    )
    expected = reference_decode(network, b"".join(records))
    assert actual == expected

    assert actual["unknown_frames"] == [
        {"timestamp_ms": 1000, "id": 0x777, "dlc": 15, "reason": "unknown_id"}
    ]
    assert [warning["reason"] for warning in actual["messages"][0]["warnings"]] == [
        "dlc_mismatch",
        "stale_gap",
    ]
    assert actual["messages"][0]["valid_frames"] == 3
    assert actual["messages"][0]["signals"][0]["count"] == 3


def test_counter_reset_marker_overlaps_counter_bits_and_still_decodes(
    tmp_path: Path,
) -> None:
    """Verify overlapping reset markers suppress jumps while stale gaps and signals still apply."""
    message_id = 0x642
    counter = {"byte": 2, "mask": 0x07, "shift": 0, "modulo": 8}
    reset = {"byte": 2, "mask": 0x0F, "value": 0x0A}
    network = {
        "bus": "overlap-reset-counter",
        "messages": [
            {
                "id": message_id,
                "name": "ResetCounter",
                "expected_dlc": 4,
                "max_gap_ms": 5,
                "counter": counter,
                "counter_reset": reset,
                "checksum": None,
                "signals": [
                    {
                        "name": "counter_shadow",
                        "start_bit": 16,
                        "length": 4,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "raw",
                    }
                ],
            }
        ],
    }

    def payload(byte_two: int) -> bytes:
        data = bytearray(8)
        data[2] = byte_two
        return bytes(data)

    records = [
        encode_record(10, message_id, 4, payload(0x00)),
        encode_record(20, message_id, 4, payload(0x0A)),
        encode_record(21, message_id, 4, payload(0x0B)),
        encode_record(22, message_id, 4, payload(0x01)),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "overlap_reset_counter", network, records
    )
    actual = run_tool(network_path, trace_path, tmp_path / "overlap_reset_report.json")
    expected = reference_decode(network, b"".join(records))
    assert actual == expected

    message = actual["messages"][0]
    assert [warning["reason"] for warning in message["warnings"]] == [
        "stale_gap",
        "counter_jump",
    ]
    assert message["signals"][0]["count"] == 4
    assert message["signals"][0]["last"] == 1


def test_big_endian_signed_32bit_extremes_and_unsigned_invalid_raw(
    tmp_path: Path,
) -> None:
    """Verify 32-bit big-endian signed extremes and unsigned invalid_raw filtering."""
    message_id = 0x643
    network = {
        "bus": "big-endian-32-extremes",
        "messages": [
            {
                "id": message_id,
                "name": "WideBE",
                "expected_dlc": 8,
                "max_gap_ms": None,
                "counter": None,
                "counter_reset": None,
                "checksum": None,
                "signals": [
                    {
                        "name": "be32_signed",
                        "start_bit": 0,
                        "length": 32,
                        "endian": "big",
                        "signed": True,
                        "scale": 1,
                        "offset": 0,
                        "unit": "raw",
                        "invalid_raw": [0x7FFFFFFF],
                    },
                    {
                        "name": "le32_signed",
                        "start_bit": 32,
                        "length": 32,
                        "endian": "little",
                        "signed": True,
                        "scale": 0.25,
                        "offset": -2,
                        "unit": "x",
                    },
                ],
            }
        ],
    }

    def payload(big_raw: int, little_raw: int) -> bytes:
        data = bytearray(8)
        set_big_bits(data, 0, 32, big_raw)
        set_bits(data, 32, 32, little_raw)
        return bytes(data)

    records = [
        encode_record(1, message_id, 8, payload(0x80000000, 0x80000000)),
        encode_record(2, message_id, 8, payload(0xFFFFFFFF, 0x00000004)),
        encode_record(3, message_id, 8, payload(0x7FFFFFFF, 0xFFFFFFFF)),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "big_endian_32_extremes", network, records
    )
    actual = run_tool(network_path, trace_path, tmp_path / "wide_be32_report.json")
    expected = reference_decode(network, b"".join(records))
    assert actual == expected

    signals = actual["messages"][0]["signals"]
    assert signals[0]["count"] == 2
    assert signals[0]["min"] == -2147483648
    assert signals[0]["max"] == -1
    assert signals[1]["count"] == 3
    assert signals[1]["min"] == -536870914
    assert signals[1]["last"] == -2.25


def test_generated_short_dlc_tail_checksum_matrix(tmp_path: Path) -> None:
    """Verify generated short-DLC captures with out-of-window checksums and tail muxes."""
    for i in range(8):
        message_id = 0x680 + i
        checksum = {
            "byte": 7 if i % 2 == 0 else 6,
            "mode": "sum8" if i % 3 else "xor8",
            "seed": 0x20 + i,
        }
        counter = {"byte": 3, "mask": 0x30, "shift": 4, "modulo": 4 + (i % 3)}
        network = {
            "bus": f"short-tail-matrix-{i}",
            "messages": [
                {
                    "id": message_id,
                    "name": "TailMatrix",
                    "expected_dlc": 4,
                    "max_gap_ms": 4 + i,
                    "counter": counter,
                    "counter_reset": None,
                    "checksum": checksum,
                    "signals": [
                        {
                            "name": "in_window",
                            "start_bit": 0,
                            "length": 10,
                            "endian": "little",
                            "signed": False,
                            "scale": 0.5,
                            "offset": 0,
                            "unit": "u",
                        },
                        {
                            "name": "tail_muxed",
                            "start_bit": 40,
                            "length": 8,
                            "endian": "little",
                            "signed": True,
                            "scale": 1,
                            "offset": 0,
                            "unit": "t",
                            "mux": {
                                "byte": checksum["byte"],
                                "mask": 0x80,
                                "value": 0x80,
                            },
                        },
                    ],
                }
            ],
        }

        def payload(
            raw: int, tail: int, counter_value: int, bad: bool = False
        ) -> bytes:
            data = bytearray(payload_from_fields([(0, 10, raw), (40, 8, tail)]))
            data[counter["byte"]] &= ~counter["mask"] & 0xFF
            data[counter["byte"]] |= (counter_value << counter["shift"]) & counter[
                "mask"
            ]
            apply_checksum(data, 4, checksum, 3 + i if bad else 0)
            return bytes(data)

        records = [
            encode_record(10 + i, message_id, 4, payload(10 + i, 0x80, 0)),
            encode_record(11 + i, message_id, 4, payload(11 + i, 0x81, 1)),
            encode_record(22 + i, message_id, 4, payload(12 + i, 0x82, 3)),
            encode_record(23 + i, message_id, 4, payload(13 + i, 0x83, 0, bad=True)),
        ]
        network_path, trace_path = write_variant(
            tmp_path, f"short_tail_matrix_{i}", network, records
        )
        actual = run_tool(
            network_path, trace_path, tmp_path / f"short_tail_matrix_{i}_report.json"
        )
        expected = reference_decode(network, b"".join(records))
        assert actual == expected
        message = actual["messages"][0]
        reasons = [warning["reason"] for warning in message["warnings"]]
        assert "counter_jump" in reasons
        assert "bad_checksum" in reasons
        if i < 7:
            assert "stale_gap" in reasons
        else:
            assert "stale_gap" not in reasons
        assert message["signals"][0]["count"] == 3


def test_explicit_cli_creates_output_parent_directories(tmp_path: Path) -> None:
    """Verify explicit CLI mode creates missing parent directories for the requested output file."""
    message_id = 0x710
    counter = {"byte": 3, "mask": 0x0F, "shift": 0, "modulo": 8}
    checksum = {"byte": 5, "mode": "sum8", "seed": 3}
    network = base_network(
        "nested-output", message_id, counter, checksum, max_gap_ms=10
    )
    records = [
        encode_record(
            10,
            message_id,
            8,
            make_drive_payload(100, 4, 2, 22, 3, counter, checksum),
        ),
        encode_record(
            20,
            message_id,
            8,
            make_drive_payload(101, 5, 2, 23, 4, counter, checksum),
        ),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "nested_output", network, records
    )
    output = tmp_path / "a" / "nested" / "path" / "report.json"
    assert not output.parent.exists()
    actual = run_tool(network_path, trace_path, output)
    expected = reference_decode(network, b"".join(records))
    assert actual == expected
    assert output.exists()


def test_interleaved_multi_message_state_pressure(tmp_path: Path) -> None:
    """Verify interleaved known frames require per-message state isolation under multiple gating rules."""
    msg_a_id = 0x721
    msg_b_id = 0x722
    msg_a_counter = {"byte": 2, "mask": 0x0F, "shift": 0, "modulo": 16}
    msg_a_reset = {"byte": 5, "mask": 0x80, "value": 0x80}
    msg_a_checksum = {"byte": 4, "mode": "sum8", "seed": 11}
    msg_b_counter = {"byte": 1, "mask": 0x03, "shift": 0, "modulo": 4}
    msg_b_checksum = {"byte": 7, "mode": "xor8", "seed": 0x44}

    network = {
        "bus": "interleaved-pressure",
        "messages": [
            {
                "id": msg_a_id,
                "name": "Drive",
                "expected_dlc": 8,
                "max_gap_ms": 2,
                "counter": msg_a_counter,
                "counter_reset": msg_a_reset,
                "checksum": msg_a_checksum,
                "signals": [
                    {
                        "name": "speed",
                        "start_bit": 0,
                        "length": 16,
                        "endian": "little",
                        "signed": False,
                        "scale": 0.25,
                        "offset": 0,
                        "unit": "kph",
                    },
                    {
                        "name": "tail_mode",
                        "start_bit": 40,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "mode",
                        "mux": {"byte": 5, "mask": 0x80, "value": 0x80},
                    },
                ],
            },
            {
                "id": msg_b_id,
                "name": "Temp",
                "expected_dlc": 5,
                "max_gap_ms": 3,
                "counter": msg_b_counter,
                "counter_reset": None,
                "checksum": msg_b_checksum,
                "signals": [
                    {
                        "name": "raw_temp",
                        "start_bit": 0,
                        "length": 12,
                        "endian": "big",
                        "signed": True,
                        "scale": 0.5,
                        "offset": -12,
                        "unit": "C",
                        "invalid_raw": [0x7FF],
                    }
                ],
            },
        ],
    }

    def msg_a_payload(
        speed_raw: int,
        tail_raw: int,
        counter_value: int,
        mux_enabled: bool,
        reset_marker: bool,
        bad_checksum: bool = False,
    ) -> bytes:
        data = bytearray(payload_from_fields([(0, 16, speed_raw), (40, 8, tail_raw)]))
        data[2] &= ~msg_a_counter["mask"] & 0xFF
        data[2] |= counter_value & msg_a_counter["mask"]
        data[5] &= 0x7F
        if mux_enabled:
            data[5] |= 0x80
        if reset_marker:
            data[5] |= 0x80
        apply_checksum(data, 8, msg_a_checksum, 17 if bad_checksum else 0)
        return bytes(data)

    def msg_b_payload(
        temp_raw: int, counter_value: int, bad_checksum: bool = False
    ) -> bytes:
        data = bytearray(8)
        set_big_bits(data, 0, 12, temp_raw)
        data[1] &= ~msg_b_counter["mask"] & 0xFF
        data[1] |= counter_value & msg_b_counter["mask"]
        apply_checksum(data, 5, msg_b_checksum, 19 if bad_checksum else 0)
        return bytes(data)

    records = [
        encode_record(100, msg_a_id, 8, msg_a_payload(120, 0x10, 1, True, False)),
        encode_record(101, msg_b_id, 5, msg_b_payload(0x010, 0)),
        encode_record(102, 0x7FF, 8, bytes([1, 2, 3, 4, 5, 6, 7, 8])),
        encode_record(
            105,
            msg_a_id,
            8,
            msg_a_payload(130, 0x11, 2, False, False, bad_checksum=True),
        ),
        encode_record(106, msg_a_id, 8, msg_a_payload(140, 0x12, 3, False, False)),
        encode_record(110, msg_b_id, 5, msg_b_payload(0x020, 2)),
        encode_record(
            111,
            msg_a_id,
            8,
            msg_a_payload(150, 0x13, 0, False, True),
        ),
        encode_record(112, msg_b_id, 5, msg_b_payload(0x7FF, 3)),
    ]

    network_path, trace_path = write_variant(
        tmp_path, "interleaved_state_pressure", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "interleaved_state_pressure_report.json"
    )
    expected = reference_decode(network, b"".join(records))
    assert actual == expected

    drive = actual["messages"][0]
    temp = actual["messages"][1]
    assert [message["name"] for message in actual["messages"]] == ["Drive", "Temp"]
    assert [warning["reason"] for warning in drive["warnings"]] == [
        "bad_checksum",
        "stale_gap",
        "counter_jump",
        "stale_gap",
    ]
    assert drive["frames"] == 4
    assert drive["valid_frames"] == 3
    assert drive["signals"][1]["count"] == 2
    assert temp["frames"] == 3
    assert temp["valid_frames"] == 3
    assert temp["signals"][0]["count"] == 2
    assert temp["warnings"] == [
        {"timestamp_ms": 110, "reason": "stale_gap", "detail": ""},
        {"timestamp_ms": 110, "reason": "counter_jump", "detail": ""},
    ]


def test_listen_only_updates_counter_and_gap_but_skips_signals(
    tmp_path: Path,
) -> None:
    """Verify listen-only frames still advance message state while suppressing signal samples."""
    message_id = 0x733
    counter = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 5}
    checksum = {"byte": 6, "mode": "sum8", "seed": 9}
    network = base_network(
        "listen-only-state", message_id, counter, checksum, max_gap_ms=5
    )
    network["messages"][0]["listen_only_flags"] = True
    records = [
        encode_record(
            100,
            message_id,
            8,
            make_drive_payload(100, 1, 2, 40, 0, counter, checksum),
        ),
        encode_record(
            112,
            message_id,
            8,
            make_drive_payload(200, 2, 2, 41, 1, counter, checksum),
            flags=0x01,
        ),
        encode_record(
            113,
            message_id,
            8,
            make_drive_payload(300, 3, 2, 42, 2, counter, checksum),
        ),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "listen_only_state", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "listen_only_state_report.json"
    )
    assert actual == reference_decode(network, b"".join(records))
    message = actual["messages"][0]
    assert message["valid_frames"] == 3
    assert [warning["reason"] for warning in message["warnings"]] == [
        "stale_gap",
        "listen_only",
    ]
    assert message["signals"][0]["count"] == 2
    assert message["signals"][0]["last"] == 37.5
    assert message["signals"][0]["last_timestamp_ms"] == 113
    assert message["signals"][2]["count"] == 2


def test_listen_only_reset_and_checksum_gate_interactions(tmp_path: Path) -> None:
    """Verify listen-only is after checksum gates and does not block counter reset state."""
    message_id = 0x734
    counter = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 8}
    reset = {"byte": 5, "mask": 0x80, "value": 0x80}
    checksum = {"byte": 6, "mode": "xor8", "seed": 0x5A}
    network = base_network(
        "listen-only-reset", message_id, counter, checksum, max_gap_ms=4
    )
    network["messages"][0]["counter_reset"] = reset
    network["messages"][0]["listen_only_flags"] = True

    def payload(
        speed_raw: int,
        muxed_raw: int,
        counter_value: int,
        reset_marker: bool = False,
        bad_checksum: bool = False,
    ) -> bytes:
        data = bytearray(
            make_drive_payload(
                speed_raw,
                0,
                2,
                muxed_raw,
                counter_value,
                counter,
                None,
            )
        )
        if reset_marker:
            data[5] |= 0x80
        apply_checksum(data, 8, checksum, 31 if bad_checksum else 0)
        return bytes(data)

    records = [
        encode_record(10, message_id, 8, payload(80, 20, 4)),
        encode_record(
            16, message_id, 8, payload(90, 21, 2, bad_checksum=True), flags=0x01
        ),
        encode_record(
            22,
            message_id,
            8,
            payload(100, 22, 7, reset_marker=True),
            flags=0x01,
        ),
        encode_record(23, message_id, 8, payload(110, 23, 0)),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "listen_only_reset", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "listen_only_reset_report.json"
    )
    assert actual == reference_decode(network, b"".join(records))
    message = actual["messages"][0]
    assert [warning["reason"] for warning in message["warnings"]] == [
        "bad_checksum",
        "stale_gap",
        "listen_only",
    ]
    assert message["valid_frames"] == 3
    assert message["signals"][0]["count"] == 2
    assert message["signals"][2]["count"] == 2


def test_counter_hold_skips_counter_state_but_decodes_signals(tmp_path: Path) -> None:
    """Verify counter-hold frames decode signals without advancing rolling-counter state."""
    message_id = 0x735
    counter = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 8}
    checksum = {"byte": 6, "mode": "sum8", "seed": 13}
    network = base_network(
        "counter-hold-state", message_id, counter, checksum, max_gap_ms=5
    )
    network["messages"][0]["counter_hold_flags"] = True
    records = [
        encode_record(
            100,
            message_id,
            8,
            make_drive_payload(100, 1, 2, 40, 0, counter, checksum),
        ),
        encode_record(
            112,
            message_id,
            8,
            make_drive_payload(200, 2, 2, 41, 4, counter, checksum),
            flags=0x02,
        ),
        encode_record(
            113,
            message_id,
            8,
            make_drive_payload(300, 3, 2, 42, 1, counter, checksum),
        ),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "counter_hold_state", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "counter_hold_state_report.json"
    )
    assert actual == reference_decode(network, b"".join(records))
    message = actual["messages"][0]
    assert message["valid_frames"] == 3
    assert [warning["reason"] for warning in message["warnings"]] == [
        "stale_gap",
        "counter_hold",
    ]
    assert message["signals"][0]["count"] == 3
    assert message["signals"][2]["count"] == 3


def test_counter_hold_listen_only_and_reset_marker_precedence(tmp_path: Path) -> None:
    """Verify counter-hold outranks reset state and composes with listen-only."""
    message_id = 0x736
    counter = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 8}
    reset = {"byte": 5, "mask": 0x80, "value": 0x80}
    checksum = {"byte": 6, "mode": "xor8", "seed": 0x33}
    network = base_network(
        "counter-hold-listen-reset", message_id, counter, checksum, max_gap_ms=4
    )
    network["messages"][0]["counter_reset"] = reset
    network["messages"][0]["counter_hold_flags"] = True
    network["messages"][0]["listen_only_flags"] = True

    def payload(
        speed_raw: int,
        muxed_raw: int,
        counter_value: int,
        reset_marker: bool = False,
        bad_checksum: bool = False,
    ) -> bytes:
        data = bytearray(
            make_drive_payload(
                speed_raw,
                0,
                2,
                muxed_raw,
                counter_value,
                counter,
                None,
            )
        )
        if reset_marker:
            data[5] |= 0x80
        apply_checksum(data, 8, checksum, 23 if bad_checksum else 0)
        return bytes(data)

    records = [
        encode_record(10, message_id, 8, payload(80, 20, 4)),
        encode_record(
            16, message_id, 8, payload(90, 21, 2, bad_checksum=True), flags=0x03
        ),
        encode_record(
            22,
            message_id,
            8,
            payload(100, 22, 2, reset_marker=True),
            flags=0x03,
        ),
        encode_record(23, message_id, 8, payload(110, 23, 5)),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "counter_hold_listen_reset", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "counter_hold_listen_reset_report.json"
    )
    assert actual == reference_decode(network, b"".join(records))
    message = actual["messages"][0]
    assert [warning["reason"] for warning in message["warnings"]] == [
        "bad_checksum",
        "stale_gap",
        "counter_hold",
        "listen_only",
    ]
    assert message["valid_frames"] == 3
    assert message["signals"][0]["count"] == 2
    assert message["signals"][2]["count"] == 2


def test_stats_reset_clears_aggregates_before_current_samples(tmp_path: Path) -> None:
    """Verify stats-reset frames start a new signal aggregate window."""
    message_id = 0x737
    counter = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 8}
    checksum = {"byte": 6, "mode": "sum8", "seed": 21}
    network = base_network(
        "stats-reset-window", message_id, counter, checksum, max_gap_ms=6
    )
    network["messages"][0]["stats_reset_flags"] = True
    records = [
        encode_record(
            100,
            message_id,
            8,
            make_drive_payload(100, 1, 2, 40, 0, counter, checksum),
        ),
        encode_record(
            102,
            message_id,
            8,
            make_drive_payload(200, 2, 2, 41, 1, counter, checksum),
        ),
        encode_record(
            110,
            message_id,
            8,
            make_drive_payload(40, 3, 2, 42, 2, counter, checksum),
            flags=0x04,
        ),
        encode_record(
            111,
            message_id,
            8,
            make_drive_payload(80, 4, 2, 43, 3, counter, checksum),
        ),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "stats_reset_window", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "stats_reset_window_report.json"
    )
    assert actual == reference_decode(network, b"".join(records))
    message = actual["messages"][0]
    assert [warning["reason"] for warning in message["warnings"]] == [
        "stale_gap",
        "stats_reset",
    ]
    assert message["valid_frames"] == 4
    assert message["signals"][0]["count"] == 2
    assert message["signals"][0]["min"] == 5
    assert message["signals"][0]["max"] == 10
    assert message["signals"][0]["last"] == 10
    assert message["signals"][2]["count"] == 2


def test_stats_reset_with_hold_and_listen_only_keeps_future_counter_baseline(
    tmp_path: Path,
) -> None:
    """Verify stats-reset can clear samples while counter-hold preserves the prior counter baseline."""
    message_id = 0x738
    counter = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 8}
    reset = {"byte": 5, "mask": 0x80, "value": 0x80}
    checksum = {"byte": 6, "mode": "xor8", "seed": 0x6C}
    network = base_network(
        "stats-reset-hold-listen", message_id, counter, checksum, max_gap_ms=4
    )
    network["messages"][0]["counter_reset"] = reset
    network["messages"][0]["counter_hold_flags"] = True
    network["messages"][0]["listen_only_flags"] = True
    network["messages"][0]["stats_reset_flags"] = True

    def payload(
        speed_raw: int,
        muxed_raw: int,
        counter_value: int,
        reset_marker: bool = False,
        bad_checksum: bool = False,
    ) -> bytes:
        data = bytearray(
            make_drive_payload(speed_raw, 0, 2, muxed_raw, counter_value, counter, None)
        )
        if reset_marker:
            data[5] |= 0x80
        apply_checksum(data, 8, checksum, 17 if bad_checksum else 0)
        return bytes(data)

    records = [
        encode_record(10, message_id, 8, payload(80, 20, 4)),
        encode_record(
            16, message_id, 8, payload(90, 21, 2, bad_checksum=True), flags=0x07
        ),
        encode_record(
            22,
            message_id,
            8,
            payload(100, 22, 2, reset_marker=True),
            flags=0x07,
        ),
        encode_record(23, message_id, 8, payload(120, 23, 5)),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "stats_reset_hold_listen", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "stats_reset_hold_listen_report.json"
    )
    assert actual == reference_decode(network, b"".join(records))
    message = actual["messages"][0]
    assert [warning["reason"] for warning in message["warnings"]] == [
        "bad_checksum",
        "stale_gap",
        "counter_hold",
        "stats_reset",
        "listen_only",
    ]
    assert message["valid_frames"] == 3
    assert message["signals"][0]["count"] == 1
    assert message["signals"][0]["last"] == 15
    assert message["signals"][2]["count"] == 1


def test_crc8_checksum_gates_flags_counters_and_signal_state(tmp_path: Path) -> None:
    """Verify crc8 checksums gate all later state updates and flag handling."""
    message_id = 0x739
    counter = {"byte": 5, "mask": 0x0F, "shift": 0, "modulo": 6}
    checksum = {"byte": 7, "mode": "crc8", "seed": 0xA6, "final_xor": 0x5C}
    network = base_network("crc8-gates", message_id, counter, checksum, max_gap_ms=4)
    network["messages"][0]["listen_only_flags"] = True
    network["messages"][0]["counter_hold_flags"] = True
    network["messages"][0]["stats_reset_flags"] = True

    def payload(
        speed_raw: int,
        muxed_raw: int,
        counter_value: int,
        bad_checksum: bool = False,
    ) -> bytes:
        data = bytearray(
            make_drive_payload(speed_raw, 0, 2, muxed_raw, counter_value, counter, None)
        )
        apply_checksum(data, 8, checksum, 29 if bad_checksum else 0)
        return bytes(data)

    records = [
        encode_record(100, message_id, 8, payload(80, 20, 0)),
        encode_record(
            106, message_id, 8, payload(90, 21, 4, bad_checksum=True), flags=0x07
        ),
        encode_record(112, message_id, 8, payload(100, 22, 4), flags=0x07),
        encode_record(113, message_id, 8, payload(120, 23, 1)),
    ]
    network_path, trace_path = write_variant(tmp_path, "crc8_gates", network, records)
    actual = run_tool(network_path, trace_path, tmp_path / "crc8_gates_report.json")
    assert actual == reference_decode(network, b"".join(records))
    message = actual["messages"][0]
    assert [warning["reason"] for warning in message["warnings"]] == [
        "bad_checksum",
        "stale_gap",
        "counter_hold",
        "stats_reset",
        "listen_only",
    ]
    assert message["valid_frames"] == 3
    assert message["signals"][0]["count"] == 1
    assert message["signals"][0]["last"] == 15
    assert message["signals"][2]["count"] == 1


def test_crc8_checksum_byte_outside_dlc_window(tmp_path: Path) -> None:
    """Verify crc8 compares an out-of-window checksum byte while hashing only DLC bytes."""
    message_id = 0x73A
    counter = {"byte": 3, "mask": 0x30, "shift": 4, "modulo": 4}
    checksum = {"byte": 7, "mode": "crc8", "seed": 0x11, "final_xor": 0xE3}
    network = {
        "bus": "crc8-outside-dlc",
        "messages": [
            {
                "id": message_id,
                "name": "ShortCrc",
                "expected_dlc": 4,
                "max_gap_ms": 3,
                "counter": counter,
                "counter_reset": None,
                "checksum": checksum,
                "signals": [
                    {
                        "name": "short_value",
                        "start_bit": 0,
                        "length": 10,
                        "endian": "little",
                        "signed": False,
                        "scale": 0.5,
                        "offset": 0,
                        "unit": "u",
                    },
                    {
                        "name": "tail_value",
                        "start_bit": 40,
                        "length": 8,
                        "endian": "little",
                        "signed": True,
                        "scale": 1,
                        "offset": 0,
                        "unit": "tail",
                    },
                ],
            }
        ],
    }

    def payload(
        raw: int, tail_raw: int, counter_value: int, bad_checksum: bool = False
    ) -> bytes:
        data = bytearray(payload_from_fields([(0, 10, raw), (40, 8, tail_raw)]))
        data[counter["byte"]] &= ~counter["mask"] & 0xFF
        data[counter["byte"]] |= (counter_value << counter["shift"]) & counter["mask"]
        apply_checksum(data, 4, checksum, 7 if bad_checksum else 0)
        return bytes(data)

    records = [
        encode_record(10, message_id, 4, payload(20, 0x81, 0)),
        encode_record(12, message_id, 4, payload(22, 0x82, 1)),
        encode_record(18, message_id, 4, payload(24, 0x83, 2, bad_checksum=True)),
        encode_record(19, message_id, 4, payload(26, 0x84, 2)),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "crc8_outside_dlc", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "crc8_outside_dlc_report.json"
    )
    assert actual == reference_decode(network, b"".join(records))
    message = actual["messages"][0]
    assert [warning["reason"] for warning in message["warnings"]] == [
        "bad_checksum",
        "stale_gap",
    ]
    assert message["valid_frames"] == 3
    assert message["signals"][0]["count"] == 3
    assert message["signals"][1]["count"] == 3


def test_shared_counter_group_tracks_file_order_across_messages(tmp_path: Path) -> None:
    """Verify non-empty counter_group shares rolling counter state across message IDs."""
    msg_a_id = 0x73B
    msg_b_id = 0x73C
    group = "drivetrain-cycle"
    counter_a = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 4}
    counter_b = {"byte": 1, "mask": 0x30, "shift": 4, "modulo": 4}
    checksum_a = {"byte": 6, "mode": "sum8", "seed": 5}
    checksum_b = {"byte": 5, "mode": "xor8", "seed": 0xA5}
    network = {
        "bus": "shared-counter-order",
        "messages": [
            {
                "id": msg_a_id,
                "name": "DriveA",
                "expected_dlc": 8,
                "max_gap_ms": None,
                "counter": counter_a,
                "counter_group": group,
                "counter_reset": None,
                "checksum": checksum_a,
                "signals": [
                    {
                        "name": "speed",
                        "start_bit": 0,
                        "length": 10,
                        "endian": "little",
                        "signed": False,
                        "scale": 0.5,
                        "offset": 0,
                        "unit": "kph",
                    }
                ],
            },
            {
                "id": msg_b_id,
                "name": "DriveB",
                "expected_dlc": 8,
                "max_gap_ms": None,
                "counter": counter_b,
                "counter_group": group,
                "counter_reset": None,
                "checksum": checksum_b,
                "signals": [
                    {
                        "name": "load",
                        "start_bit": 16,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "pct",
                    }
                ],
            },
        ],
    }

    def payload_a(raw: int, counter_value: int, bad_checksum: bool = False) -> bytes:
        data = bytearray(payload_from_fields([(0, 10, raw)]))
        data[counter_a["byte"]] &= ~counter_a["mask"] & 0xFF
        data[counter_a["byte"]] |= counter_value & counter_a["mask"]
        apply_checksum(data, 8, checksum_a, 9 if bad_checksum else 0)
        return bytes(data)

    def payload_b(raw: int, counter_value: int) -> bytes:
        data = bytearray(payload_from_fields([(16, 8, raw)]))
        data[counter_b["byte"]] &= ~counter_b["mask"] & 0xFF
        data[counter_b["byte"]] |= (counter_value << counter_b["shift"]) & counter_b[
            "mask"
        ]
        apply_checksum(data, 8, checksum_b)
        return bytes(data)

    records = [
        encode_record(10, msg_a_id, 8, payload_a(20, 0)),
        encode_record(11, msg_b_id, 8, payload_b(30, 1)),
        encode_record(12, msg_a_id, 8, payload_a(22, 2)),
        encode_record(13, msg_b_id, 8, payload_b(31, 0)),
        encode_record(14, msg_a_id, 8, payload_a(24, 1, bad_checksum=True)),
        encode_record(15, msg_b_id, 8, payload_b(32, 1)),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "shared_counter_order", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "shared_counter_order_report.json"
    )
    assert actual == reference_decode(network, b"".join(records))
    drive_a = actual["messages"][0]
    drive_b = actual["messages"][1]
    assert drive_a["warnings"] == [
        {"timestamp_ms": 14, "reason": "bad_checksum", "detail": ""}
    ]
    assert drive_b["warnings"] == [
        {"timestamp_ms": 13, "reason": "counter_jump", "detail": ""}
    ]
    assert drive_a["signals"][0]["count"] == 2
    assert drive_b["signals"][0]["count"] == 3


def test_shared_counter_group_hold_and_reset_interactions(tmp_path: Path) -> None:
    """Verify counter-hold and reset markers operate on a shared counter group."""
    msg_a_id = 0x73D
    msg_b_id = 0x73E
    group = "gateway-cycle"
    counter_a = {"byte": 7, "mask": 0x0F, "shift": 0, "modulo": 8}
    counter_b = {"byte": 2, "mask": 0x07, "shift": 0, "modulo": 8}
    reset_b = {"byte": 4, "mask": 0x80, "value": 0x80}
    checksum_a = {"byte": 6, "mode": "crc8", "seed": 0x25, "final_xor": 0x91}
    checksum_b = {"byte": 5, "mode": "sum8", "seed": 3}
    network = {
        "bus": "shared-counter-hold-reset",
        "messages": [
            {
                "id": msg_a_id,
                "name": "A",
                "expected_dlc": 8,
                "max_gap_ms": None,
                "counter": counter_a,
                "counter_group": group,
                "counter_reset": None,
                "checksum": checksum_a,
                "counter_hold_flags": True,
                "signals": [
                    {
                        "name": "a_value",
                        "start_bit": 0,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "a",
                    }
                ],
            },
            {
                "id": msg_b_id,
                "name": "B",
                "expected_dlc": 8,
                "max_gap_ms": None,
                "counter": counter_b,
                "counter_group": group,
                "counter_reset": reset_b,
                "checksum": checksum_b,
                "signals": [
                    {
                        "name": "b_value",
                        "start_bit": 16,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "b",
                    }
                ],
            },
        ],
    }

    def payload_a(raw: int, counter_value: int) -> bytes:
        data = bytearray(payload_from_fields([(0, 8, raw)]))
        data[counter_a["byte"]] &= ~counter_a["mask"] & 0xFF
        data[counter_a["byte"]] |= counter_value & counter_a["mask"]
        apply_checksum(data, 8, checksum_a)
        return bytes(data)

    def payload_b(raw: int, counter_value: int, reset_marker: bool = False) -> bytes:
        data = bytearray(payload_from_fields([(16, 8, raw)]))
        data[counter_b["byte"]] &= ~counter_b["mask"] & 0xFF
        data[counter_b["byte"]] |= counter_value & counter_b["mask"]
        if reset_marker:
            data[reset_b["byte"]] |= reset_b["value"]
        apply_checksum(data, 8, checksum_b)
        return bytes(data)

    records = [
        encode_record(20, msg_a_id, 8, payload_a(10, 0)),
        encode_record(21, msg_a_id, 8, payload_a(11, 5), flags=0x02),
        encode_record(22, msg_b_id, 8, payload_b(20, 1)),
        encode_record(23, msg_b_id, 8, payload_b(21, 6, reset_marker=True)),
        encode_record(24, msg_a_id, 8, payload_a(12, 7)),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "shared_counter_hold_reset", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "shared_counter_hold_reset_report.json"
    )
    assert actual == reference_decode(network, b"".join(records))
    msg_a = actual["messages"][0]
    msg_b = actual["messages"][1]
    assert msg_a["warnings"] == [
        {"timestamp_ms": 21, "reason": "counter_hold", "detail": ""}
    ]
    assert msg_b["warnings"] == []
    assert msg_a["signals"][0]["count"] == 3
    assert msg_b["signals"][0]["count"] == 2


def test_signal_delta_limit_respects_stats_reset_mux_and_invalid_raw(
    tmp_path: Path,
) -> None:
    """Verify max_delta warnings compose with reset windows, mux skips, and invalid samples."""
    message_id = 0x750
    network = {
        "bus": "delta-reset-mux",
        "messages": [
            {
                "id": message_id,
                "name": "DeltaMux",
                "expected_dlc": 8,
                "max_gap_ms": None,
                "counter": None,
                "counter_reset": None,
                "checksum": None,
                "stats_reset_flags": True,
                "signals": [
                    {
                        "name": "torque",
                        "start_bit": 0,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "nm",
                        "max_delta": 5,
                    },
                    {
                        "name": "mode_value",
                        "start_bit": 8,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "u",
                        "mux": {"byte": 4, "mask": 0x01, "value": 0x01},
                        "invalid_raw": [99],
                        "max_delta": 3,
                    },
                ],
            }
        ],
    }

    def payload(torque: int, mode_value: int = 0, mux_on: bool = False) -> bytes:
        data = bytearray(payload_from_fields([(0, 8, torque), (8, 8, mode_value)]))
        if mux_on:
            data[4] |= 0x01
        return bytes(data)

    records = [
        encode_record(1, message_id, 8, payload(10)),
        encode_record(2, message_id, 8, payload(14)),
        encode_record(3, message_id, 8, payload(22)),
        encode_record(4, message_id, 8, payload(40), flags=0x04),
        encode_record(5, message_id, 8, payload(47)),
        encode_record(6, message_id, 8, payload(48, 10, mux_on=True)),
        encode_record(7, message_id, 8, payload(49, 18, mux_on=True)),
        encode_record(8, message_id, 8, payload(50, 99, mux_on=True)),
        encode_record(9, message_id, 8, payload(51, 20, mux_on=True)),
    ]
    network_path, trace_path = write_variant(
        tmp_path, "delta_reset_mux", network, records
    )
    actual = run_tool(
        network_path, trace_path, tmp_path / "delta_reset_mux_report.json"
    )
    assert actual == reference_decode(network, b"".join(records))

    message = actual["messages"][0]
    assert [warning["reason"] for warning in message["warnings"]] == [
        "signal_jump",
        "stats_reset",
        "signal_jump",
        "signal_jump",
    ]
    assert [warning["timestamp_ms"] for warning in message["warnings"]] == [3, 4, 5, 7]
    assert message["signals"][0]["count"] == 6
    assert message["signals"][0]["last"] == 51
    assert message["signals"][1]["count"] == 3
    assert message["signals"][1]["last"] == 20


def test_signal_delta_limit_is_gated_by_checksum_and_listen_only(
    tmp_path: Path,
) -> None:
    """Verify max_delta ignores checksum-failed and listen-only samples."""
    message_id = 0x751
    checksum = {"byte": 7, "mode": "sum8", "seed": 2}
    network = {
        "bus": "delta-gates",
        "messages": [
            {
                "id": message_id,
                "name": "DeltaGates",
                "expected_dlc": 8,
                "max_gap_ms": None,
                "counter": None,
                "counter_reset": None,
                "checksum": checksum,
                "listen_only_flags": True,
                "signals": [
                    {
                        "name": "level",
                        "start_bit": 0,
                        "length": 8,
                        "endian": "little",
                        "signed": False,
                        "scale": 1,
                        "offset": 0,
                        "unit": "pct",
                        "max_delta": 4,
                    }
                ],
            }
        ],
    }

    def payload(raw: int, bad_checksum: bool = False) -> bytes:
        data = bytearray(payload_from_fields([(0, 8, raw)]))
        apply_checksum(data, 8, checksum, 11 if bad_checksum else 0)
        return bytes(data)

    records = [
        encode_record(10, message_id, 8, payload(10)),
        encode_record(11, message_id, 8, payload(40, bad_checksum=True)),
        encode_record(12, message_id, 8, payload(50), flags=0x01),
        encode_record(13, message_id, 8, payload(14)),
        encode_record(14, message_id, 8, payload(20)),
        encode_record(15, message_id, 8, payload(24), flags=0x01),
        encode_record(16, message_id, 8, payload(26)),
    ]
    network_path, trace_path = write_variant(tmp_path, "delta_gates", network, records)
    actual = run_tool(network_path, trace_path, tmp_path / "delta_gates_report.json")
    assert actual == reference_decode(network, b"".join(records))

    message = actual["messages"][0]
    assert [warning["reason"] for warning in message["warnings"]] == [
        "bad_checksum",
        "listen_only",
        "signal_jump",
        "listen_only",
        "signal_jump",
    ]
    assert [warning["timestamp_ms"] for warning in message["warnings"]] == [
        11,
        12,
        14,
        15,
        16,
    ]
    assert message["valid_frames"] == 6
    assert message["signals"][0]["count"] == 4
    assert message["signals"][0]["last"] == 26


def test_adversarial_shared_counter_reset_flag_delta_matrix(
    tmp_path: Path,
) -> None:
    """Verify shared resets, flag precedence, checksum gates, stale gaps, and deltas compose."""
    for seed in range(81, 87):
        msg_a_id = 0x780 + seed
        msg_b_id = 0x7A0 + seed
        group = f"shared-adversarial-{seed}"
        counter_a = {"byte": 6, "mask": 0x03, "shift": 0, "modulo": 4}
        counter_b = {"byte": 2, "mask": 0x30, "shift": 4, "modulo": 4}
        reset_a = {"byte": 5, "mask": 0x80, "value": 0x80}
        reset_b = {"byte": 0, "mask": 0x80, "value": 0x80}
        checksum_a = {
            "byte": 7,
            "mode": "crc8",
            "seed": seed,
            "final_xor": seed ^ 0x5A,
        }
        checksum_b = {"byte": 6, "mode": "xor8", "seed": seed ^ 0x33}
        network = {
            "bus": f"adversarial-shared-{seed}",
            "messages": [
                {
                    "id": msg_a_id,
                    "name": "SharedA",
                    "expected_dlc": 8,
                    "max_gap_ms": 6,
                    "counter": counter_a,
                    "counter_group": group,
                    "counter_reset": reset_a,
                    "checksum": checksum_a,
                    "counter_hold_flags": True,
                    "stats_reset_flags": True,
                    "listen_only_flags": True,
                    "signals": [
                        {
                            "name": "a_level",
                            "start_bit": 0,
                            "length": 8,
                            "endian": "little",
                            "signed": False,
                            "scale": 1,
                            "offset": 0,
                            "unit": "pct",
                            "max_delta": 12,
                        },
                        {
                            "name": "a_signed",
                            "start_bit": 8,
                            "length": 12,
                            "endian": "big",
                            "signed": True,
                            "scale": 0.5,
                            "offset": 1,
                            "unit": "amp",
                            "invalid_raw": [0x7FF],
                        },
                    ],
                },
                {
                    "id": msg_b_id,
                    "name": "SharedB",
                    "expected_dlc": 8,
                    "max_gap_ms": 4,
                    "counter": counter_b,
                    "counter_group": group,
                    "counter_reset": reset_b,
                    "checksum": checksum_b,
                    "listen_only_flags": True,
                    "stats_reset_flags": True,
                    "signals": [
                        {
                            "name": "b_level",
                            "start_bit": 24,
                            "length": 8,
                            "endian": "little",
                            "signed": False,
                            "scale": 2,
                            "offset": -10,
                            "unit": "deg",
                            "mux": {"byte": 4, "mask": 0x03, "value": 0x02},
                            "max_delta": 8,
                        }
                    ],
                },
            ],
        }

        def payload_a(
            level: int,
            signed_raw: int,
            counter_value: int,
            *,
            reset_marker: bool = False,
            bad_checksum: bool = False,
        ) -> bytes:
            data = bytearray(8)
            set_bits(data, 0, 8, level)
            set_big_bits(data, 8, 12, signed_raw)
            data[counter_a["byte"]] &= ~counter_a["mask"] & 0xFF
            data[counter_a["byte"]] |= counter_value & counter_a["mask"]
            if reset_marker:
                data[reset_a["byte"]] |= reset_a["value"]
            apply_checksum(data, 8, checksum_a, 19 if bad_checksum else 0)
            return bytes(data)

        def payload_b(
            level: int,
            counter_value: int,
            *,
            mux_on: bool = True,
            reset_marker: bool = False,
            bad_checksum: bool = False,
        ) -> bytes:
            data = bytearray(8)
            set_bits(data, 24, 8, level)
            if mux_on:
                data[4] |= 0x02
            data[counter_b["byte"]] &= ~counter_b["mask"] & 0xFF
            data[counter_b["byte"]] |= (
                counter_value << counter_b["shift"]
            ) & counter_b["mask"]
            if reset_marker:
                data[reset_b["byte"]] |= reset_b["value"]
            apply_checksum(data, 8, checksum_b, 11 if bad_checksum else 0)
            return bytes(data)

        records = [
            encode_record(10, msg_a_id, 8, payload_a(10, 0x010, 0)),
            encode_record(11, msg_b_id, 8, payload_b(12, 1)),
            encode_record(12, msg_a_id, 8, payload_a(14, 0x020, 3), flags=0x02),
            encode_record(13, msg_b_id, 8, payload_b(15, 0, reset_marker=True)),
            encode_record(20, msg_a_id, 8, payload_a(40, 0x030, 1), flags=0x04),
            encode_record(24, msg_b_id, 8, payload_b(22, 2), flags=0x01),
            encode_record(25, msg_a_id, 8, payload_a(60, 0x7FF, 0)),
            encode_record(
                26, msg_b_id, 8, payload_b(40, 1, reset_marker=True, bad_checksum=True)
            ),
            encode_record(27, msg_a_id, 8, payload_a(62, 0x040, 1)),
            encode_record(28, msg_b_id, 8, payload_b(80, 2), flags=0x04),
        ]
        network_path, trace_path = write_variant(
            tmp_path, f"adversarial_shared_{seed}", network, records
        )
        actual = run_tool(
            network_path,
            trace_path,
            tmp_path / f"adversarial_shared_{seed}_report.json",
        )
        assert actual == reference_decode(network, b"".join(records))
        msg_a = actual["messages"][0]
        msg_b = actual["messages"][1]
        assert [warning["reason"] for warning in msg_a["warnings"]] == [
            "counter_hold",
            "stale_gap",
            "stats_reset",
            "counter_jump",
            "signal_jump",
        ]
        assert [warning["timestamp_ms"] for warning in msg_a["warnings"]] == [
            12,
            20,
            20,
            25,
            25,
        ]
        assert [warning["reason"] for warning in msg_b["warnings"]] == [
            "stale_gap",
            "listen_only",
            "bad_checksum",
            "stats_reset",
        ]
        assert [warning["timestamp_ms"] for warning in msg_b["warnings"]] == [
            24,
            24,
            26,
            28,
        ]
        assert msg_a["signals"][0]["count"] == 3
        assert msg_a["signals"][0]["last"] == 62
        assert msg_a["signals"][1]["count"] == 2
        assert msg_b["signals"][0]["count"] == 1
        assert msg_b["signals"][0]["last"] == 150


def test_adversarial_dlc_crc_tail_signal_and_reset_matrix(tmp_path: Path) -> None:
    """Verify crc8 DLC windows, out-of-DLC payload fields, resets, invalid raw, and stats reset."""
    for seed in range(91, 97):
        message_id = 0x640 + seed
        counter = {"byte": 5, "mask": 0x0F, "shift": 0, "modulo": 8}
        reset = {"byte": 6, "mask": 0x80, "value": 0x80}
        checksum = {
            "byte": 7,
            "mode": "crc8",
            "seed": seed ^ 0xA5,
            "final_xor": seed,
        }
        network = {
            "bus": f"adversarial-dlc-crc-{seed}",
            "messages": [
                {
                    "id": message_id,
                    "name": "TailWindow",
                    "expected_dlc": 6,
                    "max_gap_ms": 5,
                    "counter": counter,
                    "counter_reset": reset,
                    "checksum": checksum,
                    "stats_reset_flags": True,
                    "signals": [
                        {
                            "name": "wide_signed",
                            "start_bit": 4,
                            "length": 16,
                            "endian": "big",
                            "signed": True,
                            "scale": 0.25,
                            "offset": -2,
                            "unit": "v",
                            "invalid_raw": [0x8000],
                        },
                        {
                            "name": "tail_bits",
                            "start_bit": 48,
                            "length": 7,
                            "endian": "little",
                            "signed": False,
                            "scale": 1,
                            "offset": 0,
                            "unit": "raw",
                            "max_delta": 15,
                        },
                        {
                            "name": "muxed_short",
                            "start_bit": 32,
                            "length": 8,
                            "endian": "little",
                            "signed": False,
                            "scale": 1,
                            "offset": 0,
                            "unit": "mode",
                            "mux": {"byte": 4, "mask": 0x01, "value": 0x01},
                        },
                    ],
                }
            ],
        }

        def payload(
            signed_raw: int,
            tail_raw: int,
            mux_value: int,
            counter_value: int,
            *,
            reset_marker: bool = False,
            mux_on: bool = True,
            bad_checksum: bool = False,
        ) -> bytes:
            data = bytearray(8)
            set_big_bits(data, 4, 16, signed_raw)
            set_bits(data, 48, 7, tail_raw)
            set_bits(data, 32, 8, mux_value)
            if mux_on:
                data[4] |= 0x01
            else:
                data[4] &= 0xFE
            data[counter["byte"]] &= ~counter["mask"] & 0xFF
            data[counter["byte"]] |= counter_value & counter["mask"]
            if reset_marker:
                data[reset["byte"]] |= reset["value"]
            apply_checksum(data, 6, checksum, 7 if bad_checksum else 0)
            return bytes(data)

        records = [
            encode_record(100, message_id, 6, payload(0x0010, 10, 5, 0)),
            encode_record(101, message_id, 6, payload(0x8000, 20, 6, 1)),
            encode_record(
                108, message_id, 6, payload(0x0020, 40, 7, 5, reset_marker=True)
            ),
            encode_record(109, message_id, 6, payload(0x0030, 42, 8, 6, mux_on=False)),
            encode_record(
                110, message_id, 6, payload(0x0040, 80, 9, 7, bad_checksum=True)
            ),
            encode_record(111, message_id, 6, payload(0x0050, 43, 10, 7), flags=0x04),
        ]
        network_path, trace_path = write_variant(
            tmp_path, f"adversarial_dlc_crc_{seed}", network, records
        )
        actual = run_tool(
            network_path,
            trace_path,
            tmp_path / f"adversarial_dlc_crc_{seed}_report.json",
        )
        assert actual == reference_decode(network, b"".join(records))
        message = actual["messages"][0]
        assert [warning["reason"] for warning in message["warnings"]] == [
            "stale_gap",
            "signal_jump",
            "bad_checksum",
            "stats_reset",
        ]
        assert [warning["timestamp_ms"] for warning in message["warnings"]] == [
            108,
            108,
            110,
            111,
        ]
        assert message["valid_frames"] == 5
        assert message["signals"][0]["count"] == 1
        assert message["signals"][0]["last_timestamp_ms"] == 111
        assert message["signals"][1]["count"] == 1
        assert message["signals"][1]["last"] == 43
        assert message["signals"][2]["count"] == 1
        assert message["signals"][2]["last"] == 11


def test_adversarial_same_timestamp_hold_listen_noise_matrix(
    tmp_path: Path,
) -> None:
    """Verify file order, hold-suppressed resets, listen-only resets, and gated noise."""
    for seed in range(101, 107):
        msg_a_id = 0x500 + seed
        msg_b_id = 0x5A0 + seed
        shared_group = f"same-ts-shared-{seed}"
        counter_a = {"byte": 0, "mask": 0x0F, "shift": 0, "modulo": 5}
        counter_b = {"byte": 2, "mask": 0x07, "shift": 0, "modulo": 5}
        reset_a = {"byte": 0, "mask": 0xF0, "value": 0xA0}
        reset_b = {"byte": 2, "mask": 0x80, "value": 0x80}
        checksum_a = {"byte": 7, "mode": "sum8", "seed": seed & 0xFF}
        checksum_b = {"byte": 7, "mode": "xor8", "seed": (seed ^ 0x44) & 0xFF}
        network = {
            "bus": f"same-timestamp-hold-listen-{seed}",
            "messages": [
                {
                    "id": msg_a_id,
                    "name": "OrderA",
                    "expected_dlc": 8,
                    "max_gap_ms": 2,
                    "counter": counter_a,
                    "counter_group": shared_group,
                    "counter_reset": reset_a,
                    "checksum": checksum_a,
                    "counter_hold_flags": True,
                    "listen_only_flags": True,
                    "signals": [
                        {
                            "name": "a_value",
                            "start_bit": 8,
                            "length": 8,
                            "endian": "little",
                            "signed": False,
                            "scale": 1,
                            "offset": 0,
                            "unit": "u",
                            "max_delta": 5,
                        }
                    ],
                },
                {
                    "id": msg_b_id,
                    "name": "OrderB",
                    "expected_dlc": 8,
                    "max_gap_ms": 2,
                    "counter": counter_b,
                    "counter_group": shared_group,
                    "counter_reset": reset_b,
                    "checksum": checksum_b,
                    "stats_reset_flags": True,
                    "signals": [
                        {
                            "name": "b_value",
                            "start_bit": 24,
                            "length": 8,
                            "endian": "little",
                            "signed": False,
                            "scale": 1,
                            "offset": 0,
                            "unit": "u",
                            "mux": {"byte": 4, "mask": 0x03, "value": 0x01},
                            "max_delta": 10,
                        }
                    ],
                },
            ],
        }

        def payload_a(
            value: int,
            counter_value: int,
            *,
            reset_marker: bool = False,
            bad_checksum: bool = False,
        ) -> bytes:
            data = bytearray(8)
            data[counter_a["byte"]] = counter_value & counter_a["mask"]
            if reset_marker:
                data[reset_a["byte"]] |= reset_a["value"]
            data[1] = value & 0xFF
            apply_checksum(data, 8, checksum_a, 13 if bad_checksum else 0)
            return bytes(data)

        def payload_b(
            value: int,
            counter_value: int,
            *,
            reset_marker: bool = False,
            bad_checksum: bool = False,
        ) -> bytes:
            data = bytearray(8)
            data[counter_b["byte"]] = counter_value & counter_b["mask"]
            if reset_marker:
                data[reset_b["byte"]] |= reset_b["value"]
            data[3] = value & 0xFF
            data[4] = 0x01
            apply_checksum(data, 8, checksum_b, 17 if bad_checksum else 0)
            return bytes(data)

        records = [
            encode_record(100, msg_a_id, 8, payload_a(10, 0)),
            encode_record(100, msg_b_id, 8, payload_b(10, 1)),
            encode_record(100, 0x7E0, 8, bytes([seed & 0xFF] * 8)),
            encode_record(
                100, msg_a_id, 8, payload_a(20, 4, reset_marker=True), flags=0x02
            ),
            encode_record(
                101, msg_a_id, 8, payload_a(21, 2, reset_marker=True), flags=0x01
            ),
            encode_record(102, msg_b_id, 8, payload_b(25, 3), flags=0x04),
            encode_record(106, msg_b_id, 8, payload_b(50, 4, bad_checksum=True)),
            encode_record(107, msg_a_id, 7, payload_a(22, 3)),
            encode_record(110, msg_b_id, 8, payload_b(55, 4)),
            encode_record(111, msg_a_id, 8, payload_a(30, 0)),
        ]
        network_path, trace_path = write_variant(
            tmp_path, f"same_timestamp_hold_listen_{seed}", network, records
        )
        actual = run_tool(
            network_path,
            trace_path,
            tmp_path / f"same_timestamp_hold_listen_{seed}_report.json",
        )
        assert actual == reference_decode(network, b"".join(records))
        msg_a = actual["messages"][0]
        msg_b = actual["messages"][1]
        assert msg_a["frames"] == 5
        assert msg_a["valid_frames"] == 4
        assert [warning["reason"] for warning in msg_a["warnings"]] == [
            "counter_hold",
            "signal_jump",
            "listen_only",
            "dlc_mismatch",
            "stale_gap",
            "signal_jump",
        ]
        assert [warning["timestamp_ms"] for warning in msg_a["warnings"]] == [
            100,
            100,
            101,
            107,
            111,
            111,
        ]
        assert msg_a["signals"][0]["count"] == 3
        assert msg_a["signals"][0]["last"] == 30
        assert msg_b["frames"] == 4
        assert msg_b["valid_frames"] == 3
        assert [warning["reason"] for warning in msg_b["warnings"]] == [
            "stats_reset",
            "bad_checksum",
            "stale_gap",
            "signal_jump",
        ]
        assert [warning["timestamp_ms"] for warning in msg_b["warnings"]] == [
            102,
            106,
            110,
            110,
        ]
        assert msg_b["signals"][0]["count"] == 2
        assert msg_b["signals"][0]["last"] == 55
        assert actual["unknown_frames"] == [
            {
                "timestamp_ms": 100,
                "id": 0x7E0,
                "dlc": 8,
                "reason": "unknown_id",
            }
        ]
