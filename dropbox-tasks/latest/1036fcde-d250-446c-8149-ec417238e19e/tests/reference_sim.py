"""Verifier-only reference model; mounted with /tests at grading time."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path("/app")
ENV = ROOT / "environment"
RESUME_PATH = ROOT / "state" / "resume.offset"


def sha32(payload: str) -> str:
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256"],
        input=payload.encode(),
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode().strip().rsplit(maxsplit=1)[-1].replace(":", "")[:32]


def stems(fixtures_dir: Path) -> list[str]:
    return sorted(p.stem for p in fixtures_dir.glob("pack_m*.json"))


def load_pack(stem: str, fixtures_dir: Path) -> dict[str, Any]:
    return json.loads((fixtures_dir / f"{stem}.json").read_text(encoding="utf-8"))


def load_divisor() -> int:
    merged: dict[str, int] = {}
    for name in ("base.toml", "overlay.toml"):
        for line in (ENV / "config" / name).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line.startswith("chunk_divisor"):
                continue
            _, _, rhs = line.partition("=")
            merged["chunk_divisor"] = int(rhs.strip())
    return max(merged.get("chunk_divisor", 1), 1)


def chunk_size(pipe_cap: int) -> int:
    return max(pipe_cap // load_divisor(), 512)


def resume_row() -> dict[str, Any] | None:
    if not RESUME_PATH.exists():
        return None
    return json.loads(RESUME_PATH.read_text(encoding="utf-8"))


def span_mix(writer: str, reader: str, observed: int) -> str:
    return sha32(f"{writer}|{reader}|0|{observed}|{observed}")


def simulate(fixtures_dir: Path) -> dict[str, Any]:
    resume = resume_row()
    trace_rows: list[dict[str, Any]] = []
    journal_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []

    seq = 0
    last_link = "genesis"

    def emit(label: str, phase: str, observed: int, pending: int, writer: str, reader: str) -> None:
        nonlocal seq, last_link
        trace_rows.append(
            {
                "fixture_label": label,
                "phase": phase,
                "observed": observed,
                "pending": pending,
                "writer_epoch": writer,
                "reader_epoch": reader,
                "span_mix": span_mix(writer, reader, observed),
            }
        )
        seq += 1
        link = sha32(f"{last_link}|{seq}|{label}|{phase}|{observed}|{pending}")
        journal_rows.append(
            {
                "seq": seq,
                "fixture_label": label,
                "phase": phase,
                "observed": observed,
                "pending": pending,
                "link": link,
            }
        )
        last_link = link

    for stem in stems(fixtures_dir):
        spec = load_pack(stem, fixtures_dir)
        writer = "0000"
        reader = "0000"
        observed = 0
        pending = 0
        recycle_pending = False
        start_trace_len = len(trace_rows)
        wave_chunks = 0

        for event in spec["events"]:
            kind = event["kind"]
            if kind == "seed":
                writer = str(event.get("writer_epoch", "")).lower()
                reader = str(event.get("reader_epoch", writer)).lower()
                if (
                    resume
                    and resume.get("fixture_label") == stem
                    and str(resume.get("reader_epoch", "")).lower() == reader
                ):
                    observed += int(resume.get("observed_bytes", 0))
                emit(stem, "seed", observed, pending, writer, reader)
            elif kind == "recycle":
                observed += pending
                pending = 0
                emit(stem, "recycle_before", observed, pending, writer, reader)
                reader = str(event.get("reader_epoch", reader)).lower()
                writer = reader
                recycle_pending = True
                emit(stem, "recycle_after", observed, pending, writer, reader)
            elif kind == "wave":
                remaining = int(event["bytes"])
                chunk = chunk_size(int(spec["pipe_cap"]))
                while remaining > 0:
                    size = min(remaining, chunk)
                    if spec["sink_mode"] == "redirect":
                        accepted = size
                        closed = False
                    else:
                        cap = int(spec["pipe_cap"])
                        if recycle_pending:
                            accepted = min(size, max(cap // 2, 1))
                            closed = True
                            recycle_pending = False
                        elif size > cap:
                            accepted = cap
                            closed = True
                        else:
                            accepted = size
                            closed = False
                    if closed:
                        pending = accepted
                    else:
                        observed += accepted
                        pending = 0
                    wave_chunks += 1
                    emit(stem, "wave_chunk", observed, pending, writer, reader)
                    remaining -= size
                observed += pending
                pending = 0
                emit(stem, "wave_end", observed, pending, writer, reader)

        fixture_trace = trace_rows[start_trace_len:]
        tail = [r["link"] for r in journal_rows if r["fixture_label"] == stem][-1]
        checkpoint = sha32(f"{tail}|{stem}|{observed}")
        completion = sha32(f"{tail}|{len(fixture_trace)}|{wave_chunks}|{observed}")

        report_rows.append(
            {
                "fixture_label": stem,
                "writer_epoch": writer,
                "reader_epoch": reader,
                "byte_span": {"start_offset": 0, "end_offset": observed, "observed_bytes": observed},
                "fingerprint": sha32(f"{writer}|{reader}|0|{observed}|{observed}"),
                "checkpoint_seal": checkpoint,
            }
        )
        manifest_rows.append(
            {
                "fixture_label": stem,
                "journal_tail": tail,
                "trace_lines": len(fixture_trace),
                "wave_chunks": wave_chunks,
                "completion_seal": completion,
            }
        )

    m_by_label = {r["fixture_label"]: r for r in manifest_rows}
    for row in report_rows:
        m = m_by_label[row["fixture_label"]]
        audit_rows.append(
            {
                "fixture_label": row["fixture_label"],
                "journal_tail": m["journal_tail"],
                "completion_seal": m["completion_seal"],
                "checkpoint_seal": row["checkpoint_seal"],
                "audit_seal": sha32(
                    f"{m['journal_tail']}|{m['completion_seal']}|{row['checkpoint_seal']}|{m['trace_lines']}"
                ),
            }
        )

    return {
        "report": report_rows,
        "trace": trace_rows,
        "journal": journal_rows,
        "manifest": manifest_rows,
        "audit": audit_rows,
    }
