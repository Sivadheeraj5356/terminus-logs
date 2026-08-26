"""Independent reference oracle for the SVOD residual pool ledger task."""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


DEFAULT_SECRET = "residual-escrow-key"
GENESIS = "0" * 64

DAILY_HEADER = [
    "workId",
    "territory",
    "dayLocal",
    "medium",
    "playCount",
    "grossMicroCents",
    "recoupedMicroCents",
    "netMicroCents",
]
WEEKLY_HEADER = [
    "workId",
    "territory",
    "weekStartLocal",
    "playCount",
    "grossMicroCents",
    "recoupedMicroCents",
    "netMicroCents",
]

ALLOWED_MEDIA = {"SVOD", "AVOD", "THEATRICAL"}
UTC_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$")


@dataclass(frozen=True)
class Survivor:
    work_id: str
    territory: str
    day_local: str
    medium: str
    play_count: int
    gross_micro_cents: int


@dataclass(frozen=True)
class Participant:
    participant_id: str
    weight: int
    catalog_index: int


def compute_outputs(app_root: Path | str, secret: str = DEFAULT_SECRET) -> tuple[str, str, str]:
    root = Path(app_root)
    works = _load_works(root / "data" / "works.csv")
    aliases = _load_aliases(root / "data" / "aliases.csv")
    participants = _load_participants(root / "data" / "participants.csv")
    territory = _load_territory(root / "config" / "territory_calendar.json")
    rates = _load_rates(root / "config" / "rate_tiers.toml")
    recoup = _load_recoup(root / "config" / "recoupment_caps.json")
    raw_rows, _ = _load_usage(root, territory)

    survivors = _dedupe(raw_rows, works, aliases, territory, rates)
    daily = _aggregate_daily(survivors)
    weekly = _aggregate_weekly(daily, territory)
    escrow = _build_escrow(daily, participants, recoup, secret)
    return (
        _render_csv(DAILY_HEADER, daily),
        _render_csv(WEEKLY_HEADER, weekly),
        escrow,
    )


def compute_audit(app_root: Path | str) -> str:
    root = Path(app_root)
    territory = _load_territory(root / "config" / "territory_calendar.json")
    _, audit = _load_usage(root, territory)
    return "".join(audit)


def _load_usage(root: Path, territory: dict[str, dict]) -> tuple[list[dict], list[str]]:
    manifest_path = root / "config" / "usage_ingest_order.json"
    usage_dir = root / "data" / "usage"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    listed = manifest.get("files", [])
    manifest_index = {path: idx for idx, path in enumerate(listed)}

    paths: list[Path] = []
    seen: set[str] = set()
    for rel in listed:
        paths.append(root / rel)
        seen.add(rel)
    for path in sorted(usage_dir.glob("*.jsonl"), key=lambda p: p.name):
        rel = str(path.relative_to(root)).replace("\\", "/")
        if rel not in seen:
            manifest_index[rel] = len(manifest_index)
            paths.append(path)

    loaded: list[dict] = []
    audit: list[str] = []
    for path in paths:
        rel = str(path.relative_to(root)).replace("\\", "/")
        line_no = 0
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            line_no += 1
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                audit.append(_audit_line("bad_json", "-", rel, line_no))
                continue
            if not isinstance(obj, dict):
                audit.append(_audit_line("bad_json", "-", rel, line_no))
                continue
            reason = _malformed_reason(obj, territory)
            if reason:
                audit.append(_audit_line(reason, _event_id(obj), rel, line_no))
                continue
            obj["_manifest_index"] = manifest_index.get(rel, 9999)
            obj["_source_line"] = line_no
            loaded.append(obj)
    return loaded, audit


def _audit_line(reason: str, event_id: str, manifest_rel: str, source_line: int) -> str:
    return f"audit,{reason},{event_id},{manifest_rel},{source_line}\n"


def _event_id(obj: dict) -> str:
    value = obj.get("eventId", "")
    if isinstance(value, str) and value:
        return value
    return "-"


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _malformed_reason(obj: dict, territory: dict[str, dict]) -> str | None:
    if not isinstance(obj.get("eventId"), str) or not obj["eventId"]:
        return "bad_id"
    if not isinstance(obj.get("workAlias"), str) or not obj["workAlias"]:
        return "bad_id"
    if obj.get("territory") not in territory:
        return "bad_territory"
    if obj.get("medium") not in ALLOWED_MEDIA:
        return "bad_medium"
    if not isinstance(obj.get("capturedAt"), str):
        return "bad_time"
    try:
        _parse_utc(obj["capturedAt"])
    except ValueError:
        return "bad_time"
    if not _is_int(obj.get("playCount")) or obj["playCount"] < 0:
        return "bad_play_count"
    if not _is_int(obj.get("rerunIndex")) or obj["rerunIndex"] < 0:
        return "bad_rerun"
    if not _is_int(obj.get("revision")) or obj["revision"] < 1:
        return "bad_revision"
    return None


def _load_works(path: Path) -> dict[str, str]:
    return {row["workId"]: row["status"] for row in csv.DictReader(path.read_text(encoding="utf-8").splitlines())}


def _load_aliases(path: Path) -> dict[str, str]:
    return {row["alias"].lower(): row["workId"] for row in csv.DictReader(path.read_text(encoding="utf-8").splitlines())}


def _load_participants(path: Path) -> dict[str, list[Participant]]:
    out: dict[str, list[Participant]] = {}
    for row in csv.DictReader(path.read_text(encoding="utf-8").splitlines()):
        out.setdefault(row["workId"], []).append(
            Participant(row["participantId"], int(row["weight"]), int(row["catalogIndex"]))
        )
    for parts in out.values():
        parts.sort(key=lambda p: p.catalog_index)
    return out


def _load_territory(path: Path) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8"))["territories"]


def _load_rates(path: Path) -> dict:
    medium: dict[str, int] = {}
    brackets: list[dict[str, int]] = []
    current: dict[str, int] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[medium."):
            name = line[len("[medium.") : -1]
            medium[name] = 0
            current = {"_medium": name}
            continue
        if line == "[[rerun.brackets]]":
            if current and "maxRerunIndex" in current:
                brackets.append(
                    {"maxRerunIndex": current["maxRerunIndex"], "multiplier": current["multiplier"]}
                )
            current = {}
            continue
        if "=" in line:
            key, val = [part.strip() for part in line.split("=", 1)]
            if key == "baseRateMicroCents" and "_medium" in current:
                medium[current["_medium"]] = int(val)
            elif key in ("maxRerunIndex", "multiplier"):
                current[key] = int(val)
    if current and "maxRerunIndex" in current:
        brackets.append({"maxRerunIndex": current["maxRerunIndex"], "multiplier": current["multiplier"]})
    brackets.sort(key=lambda b: b["maxRerunIndex"])
    return {"medium": medium, "brackets": brackets}


def _load_recoup(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_utc(value: str) -> datetime:
    match = UTC_RE.match(value)
    if not match:
        raise ValueError(f"bad time: {value}")
    y, mo, d, h, mi, s = map(int, match.groups())
    return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)


def _localize(utc_dt: datetime, iana: str) -> datetime:
    tz = ZoneInfo(iana)
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)

    # Detect spring-forward gap: UTC maps to two different offsets; nonexistent hour.
    utc_naive = utc_dt.replace(tzinfo=None)
    local = utc_naive.replace(tzinfo=timezone.utc).astimezone(tz)

    # If offset changed discontinuously forward, ensure we didn't land before gap.
    fold = getattr(tz, "fold", 0)
    if fold:
        local = local.replace(fold=1)

    # Explicit spring-forward: try converting; if hour missing, advance.
    try:
        candidate = utc_dt.astimezone(tz)
    except Exception:
        candidate = local

    # Validate round-trip for spring gap.
    back = candidate.astimezone(timezone.utc)
    if abs((back - utc_dt).total_seconds()) > 3600:
        probe = utc_dt
        for _ in range(180):
            probe += timedelta(minutes=1)
            candidate = probe.astimezone(tz)
            back = candidate.astimezone(timezone.utc)
            if abs((back - utc_dt).total_seconds()) <= 60:
                break
    return candidate


def _day_local(utc_dt: datetime, iana: str) -> str:
    return _localize(utc_dt, iana).date().isoformat()


def _week_start(day_local: str, iana: str) -> str:
    y, m, d = map(int, day_local.split("-"))
    local = datetime(y, m, d, 12, 0, 0, tzinfo=ZoneInfo(iana))
    monday = local - timedelta(days=local.weekday())
    return monday.date().isoformat()


def _rerun_multiplier(rerun_index: int, brackets: list[dict]) -> int:
    for bracket in brackets:
        if rerun_index <= bracket["maxRerunIndex"]:
            return bracket["multiplier"]
    return brackets[-1]["multiplier"]


def _accrual(play_count: int, base: int, territory_mult: int, rerun_mult: int) -> int:
    num = play_count * base * territory_mult * rerun_mult
    den = 10000 * 10000
    if num >= 0:
        return num // den
    return -((-num) // den)


def _dedupe(
    raw_rows: list[dict],
    works: dict[str, str],
    aliases: dict[str, str],
    territory: dict[str, dict],
    rates: dict,
) -> list[Survivor]:
    parsed: list[dict] = []
    for obj in raw_rows:
        work_id = aliases.get(obj["workAlias"].lower())
        if work_id is None or works.get(work_id) != "active":
            continue
        terr = obj["territory"]
        if terr not in territory:
            continue
        medium = obj["medium"]
        if medium not in ALLOWED_MEDIA:
            continue
        captured = _parse_utc(obj["capturedAt"])
        iana = territory[terr]["iana"]
        parsed.append(
            {
                "work_id": work_id,
                "territory": terr,
                "medium": medium,
                "day_local": _day_local(captured, iana),
                "rerun_index": int(obj["rerunIndex"]),
                "play_count": int(obj["playCount"]),
                "revision": int(obj["revision"]),
                "captured_ts": int(captured.timestamp()),
                "manifest_index": int(obj["_manifest_index"]),
                "source_line": int(obj["_source_line"]),
            }
        )

    grouped: dict[tuple, list[dict]] = {}
    for row in parsed:
        key = (row["work_id"], row["territory"], row["day_local"], row["medium"], row["rerun_index"])
        grouped.setdefault(key, []).append(row)

    survivors: list[Survivor] = []
    for group in grouped.values():
        winner = max(
            group,
            key=lambda r: (r["revision"], r["captured_ts"], r["manifest_index"], r["source_line"]),
        )
        base = rates["medium"][winner["medium"]]
        terr_mult = int(territory[winner["territory"]]["multiplier"])
        rerun_mult = _rerun_multiplier(winner["rerun_index"], rates["brackets"])
        gross = _accrual(winner["play_count"], base, terr_mult, rerun_mult)
        survivors.append(
            Survivor(
                work_id=winner["work_id"],
                territory=winner["territory"],
                day_local=winner["day_local"],
                medium=winner["medium"],
                play_count=winner["play_count"],
                gross_micro_cents=gross,
            )
        )
    return survivors


def _aggregate_daily(survivors: list[Survivor]) -> list[dict[str, str | int]]:
    buckets: dict[tuple, dict[str, int]] = {}
    for row in survivors:
        key = (row.work_id, row.territory, row.day_local, row.medium)
        bucket = buckets.setdefault(key, {"playCount": 0, "grossMicroCents": 0})
        bucket["playCount"] += row.play_count
        bucket["grossMicroCents"] += row.gross_micro_cents

    daily: list[dict[str, str | int]] = []
    for (work_id, territory, day_local, medium), vals in sorted(buckets.items()):
        if vals["playCount"] == 0:
            continue
        gross = vals["grossMicroCents"]
        daily.append(
            {
                "workId": work_id,
                "territory": territory,
                "dayLocal": day_local,
                "medium": medium,
                "playCount": vals["playCount"],
                "grossMicroCents": gross,
                "recoupedMicroCents": 0,
                "netMicroCents": gross,
            }
        )
    return daily


def _aggregate_weekly(daily: list[dict[str, str | int]], territory: dict[str, dict]) -> list[dict[str, str | int]]:
    buckets: dict[tuple, dict[str, int]] = {}
    for row in daily:
        iana = territory[row["territory"]]["iana"]
        week = _week_start(str(row["dayLocal"]), iana)
        key = (row["workId"], row["territory"], week)
        bucket = buckets.setdefault(key, {"playCount": 0, "grossMicroCents": 0, "netMicroCents": 0})
        bucket["playCount"] += int(row["playCount"])
        bucket["grossMicroCents"] += int(row["grossMicroCents"])
        bucket["netMicroCents"] += int(row["netMicroCents"])

    weekly: list[dict[str, str | int]] = []
    for (work_id, terr, week), vals in sorted(buckets.items()):
        weekly.append(
            {
                "workId": work_id,
                "territory": terr,
                "weekStartLocal": week,
                "playCount": vals["playCount"],
                "grossMicroCents": vals["grossMicroCents"],
                "recoupedMicroCents": 0,
                "netMicroCents": vals["netMicroCents"],
            }
        )
    return weekly


def _period_month(day_local: str) -> str:
    return day_local[:7]


def _apply_recoupment(gross: int, caps: dict[str, int]) -> int:
    remaining = gross
    total = 0
    for tier in ("distributor", "producer", "participant"):
        cap = int(caps.get(tier, 0))
        take = min(remaining, cap)
        total += take
        remaining -= take
        if remaining <= 0:
            break
    return gross - total


def _split_pool(net_pool: int, participants: list[Participant]) -> list[tuple[Participant, int]]:
    if net_pool <= 0 or not participants:
        return []
    total_weight = sum(p.weight for p in participants)
    floors: list[tuple[Participant, int]] = []
    for p in participants:
        share = (net_pool * p.weight) // total_weight
        floors.append((p, share))
    assigned = sum(v for _, v in floors)
    remainder = net_pool - assigned
    amounts = {p.participant_id: v for p, v in floors}
    ordered = sorted(participants, key=lambda p: p.catalog_index)
    idx = 0
    while remainder > 0:
        p = ordered[idx % len(ordered)]
        amounts[p.participant_id] += 1
        remainder -= 1
        idx += 1
    return [(p, amounts[p.participant_id]) for p in ordered if amounts[p.participant_id] > 0]


def _build_escrow(
    daily: list[dict[str, str | int]],
    participants: dict[str, list[Participant]],
    recoup: dict,
    secret: str,
) -> str:
    month_groups: dict[tuple[str, str, str], int] = {}
    for row in daily:
        period = _period_month(str(row["dayLocal"]))
        key = (str(row["workId"]), str(row["territory"]), period)
        month_groups[key] = month_groups.get(key, 0) + int(row["grossMicroCents"])

    if not month_groups:
        return ""

    period_month = max(period for _, _, period in month_groups.keys())

    body: list[dict[str, int | str]] = []
    for (work_id, territory, period), gross in sorted(month_groups.items()):
        if period != period_month:
            continue
        caps = recoup.get(work_id, {}).get(territory, {})
        net = _apply_recoupment(gross, caps)
        parts = participants.get(work_id, [])
        for part, amount in _split_pool(net, parts):
            body.append(
                {
                    "workId": work_id,
                    "territory": territory,
                    "periodMonth": period,
                    "participantId": part.participant_id,
                    "amountMicroCents": amount,
                    "catalogIndex": part.catalog_index,
                }
            )

    pool_total = sum(int(line["amountMicroCents"]) for line in body)
    line_count = len(body)
    message = f"{period_month}|{pool_total}|{line_count}|{GENESIS}"
    entry_hash = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    footer = {
        "type": "footer",
        "periodMonth": period_month,
        "poolTotalMicroCents": pool_total,
        "lineCount": line_count,
        "prevHash": GENESIS,
        "entryHash": entry_hash,
    }

    lines = [json.dumps(row, separators=(",", ":")) for row in body]
    lines.append(json.dumps(footer, separators=(",", ":")))
    return "\n".join(lines) + "\n"


def _render_csv(header: list[str], rows: list[dict[str, str | int]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in header})
    return buf.getvalue()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "environment"
    daily, weekly, escrow = compute_outputs(root)
    print("=== DAILY ===")
    print(daily)
    print("=== WEEKLY ===")
    print(weekly)
    print("=== ESCROW ===")
    print(escrow)
