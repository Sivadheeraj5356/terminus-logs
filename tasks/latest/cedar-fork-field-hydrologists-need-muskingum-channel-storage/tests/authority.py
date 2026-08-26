"""Independent Muskingum routing authority used during grading."""
from __future__ import annotations

import struct
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from pathlib import Path

getcontext().prec = 60

MAGIC = b"CFR1"


def D(x) -> Decimal:
    return Decimal(str(x))


def round3(x) -> Decimal:
    return D(x).quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN)


def subdivisions(K, dt) -> int:
    n = int((D(K) / D(dt)).to_integral_value(rounding=ROUND_HALF_EVEN))
    return n if n >= 1 else 1


def coeffs(K, X, dt) -> tuple[Decimal, Decimal, Decimal]:
    k, x, half = D(K), D(X), D(dt) * D("0.5")
    denom = k * (Decimal("1") - x) + half
    c0 = (half - k * x) / denom
    c1 = (half + k * x) / denom
    c2 = (k * (Decimal("1") - x) - half) / denom
    return c0, c1, c2


def route_once(inflow: list[Decimal], K, X, dt) -> list[Decimal]:
    c0, c1, c2 = coeffs(K, X, dt)
    n = len(inflow)
    out = [Decimal("0")] * n
    out[0] = round3(inflow[0])
    for t in range(1, n):
        raw = c0 * inflow[t] + c1 * inflow[t - 1] + c2 * out[t - 1]
        out[t] = round3(raw)
    return out


def route_reach(inflow: list[Decimal], K, X, dt) -> list[Decimal]:
    n = subdivisions(K, dt)
    ksub = D(K) / D(n)
    series = inflow
    for _ in range(n):
        series = route_once(series, ksub, D(X), dt)
    return series


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise ValueError("truncated survey")
        chunk = self.data[self.pos : self.pos + n]
        self.pos += n
        return chunk

    def u8(self) -> int:
        return self.take(1)[0]

    def u16(self) -> int:
        return struct.unpack("<H", self.take(2))[0]

    def f64(self) -> float:
        return struct.unpack("<d", self.take(8))[0]

    def name(self) -> str:
        return self.take(self.u8()).decode("ascii")


def load_survey(path: str | Path) -> dict:
    r = _Reader(Path(path).read_bytes())
    if r.take(4) != MAGIC:
        raise ValueError("bad magic")
    dt = r.f64()
    peak_min = r.f64()
    reaches = []
    for _ in range(r.u16()):
        rid = r.name()
        river_km = r.f64()
        K = r.f64()
        X = r.f64()
        ups = [r.name() for _ in range(r.u8())]
        reaches.append({"reach_id": rid, "river_km": river_km, "K": K, "X": X, "upstream": ups})
    events = []
    for _ in range(r.u16()):
        ev_name = r.name()
        steps = r.u16()
        headwater = [r.f64() for _ in range(steps)]
        laterals: dict[str, list[float]] = {}
        for _ in range(r.u8()):
            lid = r.name()
            laterals[lid] = [r.f64() for _ in range(steps)]
        events.append({"name": ev_name, "headwater": headwater, "laterals": laterals})
    return {"dt_hours": dt, "peak_min_cms": peak_min, "reaches": reaches, "events": events}


def lateral_series(laterals: dict, rid: str, n: int) -> list[Decimal]:
    raw = laterals.get(rid)
    if not raw:
        return [Decimal("0")] * n
    out = [Decimal("0")] * n
    for t in range(n):
        prev = Decimal("0") if t == 0 else D(raw[t - 1])
        out[t] = round3((D(raw[t]) + prev) / Decimal("2"))
    return out


def process_order(reaches: list[dict]) -> list[dict]:
    by_id = {r["reach_id"]: r for r in reaches}
    done: set[str] = set()
    order: list[dict] = []
    while True:
        ready = [
            r
            for r in reaches
            if r["reach_id"] not in done
            and all(u in done or u not in by_id for u in (r.get("upstream") or []))
        ]
        if not ready:
            break
        for r in sorted(ready, key=lambda x: x["reach_id"]):
            order.append(r)
            done.add(r["reach_id"])
    return order


def analyze(survey: dict, event: dict) -> list[dict]:
    dt = survey["dt_hours"]
    peak_min = D(survey["peak_min_cms"])
    headwater = [D(v) for v in event["headwater"]]
    laterals = event.get("laterals", {})
    n = len(headwater)

    admitted: dict[str, list[Decimal]] = {}
    for r in process_order(survey["reaches"]):
        rid = r["reach_id"]
        ups = r.get("upstream") or []
        if not ups:
            base = list(headwater)
        else:
            base = [Decimal("0")] * n
            for t in range(1, n):
                for u in ups:
                    up = admitted.get(u)
                    if up is not None:
                        base[t] += up[t - 1]
        lat = lateral_series(laterals, rid, n)
        i_eff = [base[t] + lat[t] for t in range(n)]
        series = route_reach(i_eff, r["K"], r["X"], dt)
        if max(series) >= peak_min:
            admitted[rid] = series

    hydrographs = []
    for r in sorted(survey["reaches"], key=lambda x: x["reach_id"]):
        rid = r["reach_id"]
        series = admitted.get(rid)
        if series is None:
            continue
        peak = max(series)
        ttp = round3(series.index(peak) * D(dt))
        hydrographs.append(
            {
                "reach_id": rid,
                "peak_cms": float(peak),
                "time_to_peak_h": float(ttp),
                "outflow_cms": [float(v) for v in series],
            }
        )
    return hydrographs


def analyze_survey(path: str | Path) -> dict[str, list[dict]]:
    survey = load_survey(path)
    return {ev["name"]: analyze(survey, ev) for ev in survey["events"]}


def analyze_first_event(path: str | Path) -> list[dict]:
    survey = load_survey(path)
    return analyze(survey, survey["events"][0])
