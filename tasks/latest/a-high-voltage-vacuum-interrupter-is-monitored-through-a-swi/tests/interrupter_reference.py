"""Independent numerical reference for the vacuum-interrupter task."""

from __future__ import annotations

import math
from dataclasses import dataclass


TIME_EPS = 1e-9
VALUE_EPS = 1e-10


@dataclass(frozen=True)
class Curve:
    second: float
    first: float
    constant: float

    def value(self, x: float) -> float:
        return (self.second * x + self.first) * x + self.constant

    def primitive(self, x: float) -> float:
        return self.second * x**3 / 3.0 + self.first * x**2 / 2.0 + self.constant * x

    def exposure(self, begin: float, end: float, baseline: float) -> float:
        return self.primitive(end) - self.primitive(begin) - baseline * (end - begin)


def _event_batches(events: list[dict]) -> list[tuple[float, list[dict]]]:
    ordered = sorted(enumerate(events), key=lambda item: (float(item[1]["t"]), item[0]))
    batches: list[tuple[float, list[dict]]] = []
    index = 0
    while index < len(ordered):
        anchor = float(ordered[index][1]["t"])
        batch: list[tuple[int, dict]] = []
        while index < len(ordered) and float(ordered[index][1]["t"]) <= anchor + TIME_EPS:
            batch.append(ordered[index])
            index += 1
        batch.sort(key=lambda item: item[0])
        batches.append((anchor, [event for _, event in batch]))
    return batches


def _level_roots(curve: Curve, level: float) -> list[float]:
    constant = curve.constant - level
    if abs(curve.second) <= VALUE_EPS:
        if abs(curve.first) <= VALUE_EPS:
            return []
        return [-constant / curve.first]
    discriminant = curve.first**2 - 4.0 * curve.second * constant
    if discriminant < -VALUE_EPS:
        return []
    root = math.sqrt(max(0.0, discriminant))
    return [
        (-curve.first - root) / (2.0 * curve.second),
        (-curve.first + root) / (2.0 * curve.second),
    ]


def _partition(curve: Curve, config: dict, duration: float) -> list[float]:
    points = [0.0, duration]
    points.extend(_level_roots(curve, float(config["strike_level"])))
    points.extend(_level_roots(curve, float(config["clear_level"])))
    points = [min(duration, max(0.0, point)) for point in points if -TIME_EPS <= point <= duration + TIME_EPS]
    points.sort()
    unique: list[float] = []
    for point in points:
        if not unique or abs(point - unique[-1]) > TIME_EPS:
            unique.append(point)
    if not unique or unique[0] > TIME_EPS:
        unique.insert(0, 0.0)
    if duration - unique[-1] > TIME_EPS:
        unique.append(duration)
    return unique


def reconstruct(config: dict, events: list[dict]) -> list[dict]:
    """Reconstruct visible state spans from a configuration and event stream."""

    start = float(config["window_start"])
    finish = float(config["window_end"])
    if finish <= start:
        return []

    current = float(config["start_current"])
    pressure = float(config["start_pressure"])
    gap = float(config["start_gap"])
    conditioning = False
    restrike = False
    welded = False
    qualification = 0.0
    erosion = 0.0

    spans: list[dict] = []
    visible: str | None = None
    visible_start = start

    def state_name() -> str:
        if welded:
            return "welded"
        if conditioning:
            return "conditioning"
        if restrike:
            return "restrike"
        return "normal"

    def record(time: float) -> None:
        nonlocal visible, visible_start
        state = state_name()
        if visible is None:
            visible = state
            visible_start = time
        elif state != visible:
            if time - visible_start > TIME_EPS:
                spans.append({"state": visible, "start": visible_start, "end": time})
            visible = state
            visible_start = time

    def curve() -> Curve:
        return Curve(
            float(config["current_weight"]) * float(config["current_slope"]) ** 2
            + float(config["pressure_weight"]) * float(config["pressure_slope"]) ** 2,
            2.0 * float(config["current_weight"]) * current * float(config["current_slope"])
            + 2.0 * float(config["pressure_weight"]) * pressure * float(config["pressure_slope"])
            - float(config["gap_weight"]) * float(config["gap_slope"]),
            float(config["current_weight"]) * current**2
            + float(config["pressure_weight"]) * pressure**2
            - float(config["gap_weight"]) * gap
            - (float(config["conditioning_relief"]) if conditioning else 0.0),
        )

    def settle(time: float) -> None:
        settle_stress(time, curve().constant)

    def settle_stress(time: float, stress: float) -> None:
        nonlocal restrike, qualification
        if welded:
            return
        if restrike and stress <= float(config["clear_level"]) + VALUE_EPS:
            restrike = False
            qualification = 0.0
            record(time)
        if not restrike:
            if stress < float(config["strike_level"]) - VALUE_EPS:
                qualification = 0.0
            elif float(config["qualify_sec"]) <= TIME_EPS:
                restrike = True
                qualification = 0.0
                record(time)

    def consume_restrike(interval_start: float, stress_curve: Curve, begin: float, end: float) -> None:
        nonlocal restrike, qualification, erosion, welded
        if welded or end - begin <= TIME_EPS:
            return
        if stress_curve.value((begin + end) / 2.0) <= float(config["clear_level"]) + VALUE_EPS:
            restrike = False
            qualification = 0.0
            record(interval_start + begin)
            return
        gained = max(0.0, stress_curve.exposure(begin, end, float(config["clear_level"])))
        remaining = float(config["erosion_limit"]) - erosion
        if gained + VALUE_EPS < remaining:
            erosion += gained
            return
        low, high = begin, end
        for _ in range(100):
            middle = (low + high) / 2.0
            if stress_curve.exposure(begin, middle, float(config["clear_level"])) >= remaining:
                high = middle
            else:
                low = middle
        erosion = float(config["erosion_limit"])
        welded = True
        restrike = False
        qualification = 0.0
        record(interval_start + (low + high) / 2.0)

    def advance(interval_start: float, duration: float) -> None:
        nonlocal current, pressure, gap, restrike, qualification
        if duration <= TIME_EPS:
            return
        stress_curve = curve()
        points = _partition(stress_curve, config, duration)
        for begin, end in zip(points, points[1:]):
            settle_stress(interval_start + begin, stress_curve.value(begin))
            if end - begin <= TIME_EPS or welded:
                continue
            middle_stress = stress_curve.value((begin + end) / 2.0)
            if restrike:
                consume_restrike(interval_start, stress_curve, begin, end)
            elif middle_stress >= float(config["strike_level"]) - VALUE_EPS:
                needed = max(0.0, float(config["qualify_sec"]) - qualification)
                available = end - begin
                if needed <= available + TIME_EPS:
                    transition = min(end, max(begin, begin + needed))
                    qualification = 0.0
                    restrike = True
                    record(interval_start + transition)
                    consume_restrike(interval_start, stress_curve, transition, end)
                else:
                    qualification += available
            else:
                qualification = 0.0
        settle_stress(interval_start + points[-1], stress_curve.value(points[-1]))
        current += float(config["current_slope"]) * duration
        pressure += float(config["pressure_slope"]) * duration
        gap += float(config["gap_slope"]) * duration
        settle(interval_start + duration)

    settle(start)
    record(start)
    cursor = start
    for event_time, batch in _event_batches(events):
        if event_time < start - TIME_EPS:
            continue
        if event_time > finish + TIME_EPS:
            break
        event_time = min(finish, max(cursor, event_time))
        advance(cursor, event_time - cursor)
        cursor = event_time
        for event in batch:
            kind = event["kind"]
            if kind == "current_sample":
                current = float(event["value"])
            elif kind == "pressure_sample":
                pressure = float(event["value"])
            elif kind == "gap_sample":
                gap = float(event["value"])
            elif kind == "conditioning_on":
                conditioning = True
            elif kind == "conditioning_off":
                conditioning = False
        settle(cursor)
        record(cursor)

    advance(cursor, finish - cursor)
    if visible is not None and finish - visible_start > TIME_EPS:
        spans.append({"state": visible, "start": visible_start, "end": finish})
    return spans
