"""Deterministic record generator for the Chan referee differential.

Every builder returns a raw record whose reference account is well formed; the
illegal builders return records whose account is a specific fault.  The neutral
indexed schedule fans across every honour, fine, and fault family so the two
engines are compared on the whole surface.
"""

from __future__ import annotations

import random
from collections import Counter

import channref as ref

WHITE = [kind for kind in ref.KINDS if kind not in ref.RED]

ILLEGAL_REASONS = ("malformed", "bad-hand", "bad-layout", "bad-log")
CUOC_MODES = (
    "banthu", "tom", "leo", "bachdinh", "tamdo", "kinhtuchi", "thienkhai",
    "thienu", "diau", "chi", "thong",
)
FINE_MODES = ("treo-tranh", "tra-cua", "lot-song")
MODE_NAMES = (
    "plain",
    "random",
    "random",
    "random-log",
    "xuong",
    *CUOC_MODES,
    *FINE_MODES,
    *tuple("illegal-" + reason for reason in ILLEGAL_REASONS),
)


def mode_for_index(index: int) -> int:
    """Map an index onto the stable mode schedule."""
    return index % len(MODE_NAMES)


def _fresh_capacity() -> Counter:
    return Counter({kind: 4 for kind in ref.KINDS})


def _consume(capacity: Counter, unit: tuple[str, tuple[str, str]]) -> bool:
    _, cards = unit
    if capacity[cards[0]] < 1 or capacity[cards[1]] < 1:
        return False
    if cards[0] == cards[1] and capacity[cards[0]] < 2:
        return False
    capacity[cards[0]] -= 1
    capacity[cards[1]] -= 1
    return True


def _random_unit(rng: random.Random, capacity: Counter, white_only: bool) -> tuple | None:
    pool = WHITE if white_only else ref.KINDS
    if rng.random() < 0.5:
        choices = [kind for kind in pool if capacity[kind] >= 2]
        if choices:
            kind = rng.choice(choices)
            capacity[kind] -= 2
            return ("chan", (kind, kind))
    ranks = list("23456789")
    rng.shuffle(ranks)
    for rank in ranks:
        suits = [suit for suit in "vns" if capacity[rank + suit] >= 1 and (not white_only or rank + suit in WHITE)]
        if len(suits) >= 2:
            picked = rng.sample(suits, 2)
            capacity[rank + picked[0]] -= 1
            capacity[rank + picked[1]] -= 1
            return ("ca", (rank + picked[0], rank + picked[1]))
    choices = [kind for kind in pool if capacity[kind] >= 2]
    if not choices:
        return None
    kind = rng.choice(choices)
    capacity[kind] -= 2
    return ("chan", (kind, kind))


def _fill(rng: random.Random, units: list, capacity: Counter, white_only: bool = False) -> list | None:
    while len(units) < 10:
        unit = _random_unit(rng, capacity, white_only)
        if unit is None:
            return None
        units.append(unit)
    return units if len(units) == 10 else None


def _units_to_cards(units: list) -> list[str]:
    cards: list[str] = []
    for _, pair in units:
        cards.extend(pair)
    return cards


def _pick_winning(rng: random.Random, units: list, want_chan: bool | None) -> int:
    order = list(range(len(units)))
    rng.shuffle(order)
    for index in order:
        kind = units[index][0]
        if want_chan is None or (want_chan and kind == "chan") or (not want_chan and kind == "ca"):
            return index
    return order[0]


def _raw_unit(rng: random.Random, unit: tuple) -> str:
    kind, cards = unit
    ordered = list(cards)
    rng.shuffle(ordered)
    return "%s(%s,%s)" % (kind, ordered[0], ordered[1])


def _decide(rng: random.Random, units: list, want_chan: bool | None) -> tuple[int, str]:
    win_index = _pick_winning(rng, units, want_chan)
    uu = rng.choice(units[win_index][1])
    return win_index, uu


def _assemble(
    rng: random.Random,
    units: list,
    role: str,
    source: str,
    streak: str,
    log: list[tuple[str, str, int]],
    winner: str,
    win_index: int,
    uu: str,
) -> bytes:
    win_unit = units[win_index]
    rest = [unit for index, unit in enumerate(units) if index != win_index]
    rng.shuffle(rest)
    declared = [win_unit] + rest
    layout = ";".join(_raw_unit(rng, unit) for unit in declared)

    twenty = _units_to_cards(units)
    hand = list(twenty)
    hand.remove(uu)
    rng.shuffle(hand)

    header = [
        "CHAN/1",
        "win %s %s %s %s" % (winner, role, source, streak),
        "uu " + uu,
        "hand " + " ".join(hand),
        "layout " + layout,
        "log",
    ]
    body = ["toss %s %s %d" % (seat, card, rnd) for seat, card, rnd in log]
    return ("\n".join(header + body) + "\n").encode("ascii")


def _base_units(rng: random.Random, forced: list, white_only: bool = False) -> list | None:
    capacity = _fresh_capacity()
    units = []
    for unit in forced:
        if not _consume(capacity, unit):
            return None
        units.append(unit)
    return _fill(rng, units, capacity, white_only)


def _try(builder, seed: int) -> bytes:
    for attempt in range(400):
        rng = random.Random(seed + attempt * 1_000_003)
        try:
            record = builder(rng)
        except (ValueError, IndexError):
            record = None
        if record is not None:
            return record
    raise AssertionError("generator exhausted")


def _clean_log(rng: random.Random, units: list, winner: str, source: str, uu: str, count: int) -> list:
    """A log that triggers no fine: distinct safe cards, avoiding chan kinds and uu."""
    chan_kinds = {cards[0] for kind, cards in units if kind == "chan"}
    losers = ref.other_seats(winner)
    log = []
    rnd = 1
    used = {seat: set() for seat in losers}
    for _ in range(count):
        seat = rng.choice(losers)
        candidates = [
            kind for kind in ref.KINDS
            if kind not in chan_kinds and kind != uu and kind not in used[seat]
        ]
        if not candidates:
            break
        card = rng.choice(candidates)
        used[seat].add(card)
        log.append((seat, card, rnd))
        rnd += rng.randint(0, 1)
    return log


def _build_generic(rng: random.Random, forced: list, mode: str, white_only: bool = False) -> bytes | None:
    units = _base_units(rng, forced, white_only)
    if units is None:
        return None
    winner = rng.choice(ref.SEATS)
    role = rng.choice(("dealer", "nondealer"))
    source = rng.choice(("draw", "gate", "stock"))
    streak = rng.choice(("fresh", "thong"))
    want_chan = None
    if mode == "banthu":
        want_chan = True
    if mode == "thienu":
        role, source = "dealer", "deal"
    if mode == "diau":
        role, source = "nondealer", "deal"
    if mode == "chi":
        source = "gate"
    if mode == "thong":
        streak = "thong"
    win_index, uu = _decide(rng, units, want_chan)
    log = _clean_log(rng, units, winner, source, uu, rng.randint(0, 4))
    return _assemble(rng, units, role, source, streak, log, winner, win_index, uu)


def _build_fine(rng: random.Random, mode: str) -> bytes | None:
    units = _base_units(rng, [])
    if units is None:
        return None
    winner = rng.choice(ref.SEATS)
    losers = ref.other_seats(winner)
    chan_kinds = [cards[0] for kind, cards in units if kind == "chan"]
    source = rng.choice(("draw", "gate", "stock"))
    want_chan = None
    log: list[tuple[str, str, int]] = []
    win_index, uu = _decide(rng, units, want_chan)
    if mode == "treo-tranh":
        if not chan_kinds:
            return None
        log.append((rng.choice(losers), rng.choice(chan_kinds), 1))
    elif mode == "tra-cua":
        source = "draw"
        log.append((rng.choice(losers), uu, 1))
    elif mode == "lot-song":
        card = rng.choice([kind for kind in ref.KINDS if kind not in chan_kinds and kind != uu])
        seat = rng.choice(losers)
        log.append((seat, card, 1))
        log.append((seat, card, 2))
    log.extend(_clean_log(rng, units, winner, source, uu, rng.randint(0, 2)))
    log.sort(key=lambda entry: entry[2])
    role = rng.choice(("dealer", "nondealer"))
    streak = rng.choice(("fresh", "thong"))
    if source == "deal":
        source = "draw"
    return _assemble(rng, units, role, source, streak, log, winner, win_index, uu)


def _mutate_illegal(rng: random.Random, reason: str) -> bytes | None:
    record = _build_generic(rng, [], "plain")
    if record is None:
        return None
    lines = record.decode("ascii").splitlines()
    if reason == "malformed":
        lines[0] = "CHAN/2"
    elif reason == "bad-hand":
        hand = lines[3].split(" ")
        first = hand[1]
        for index in range(2, len(hand)):
            hand[index] = first
        lines[3] = " ".join(hand)
    elif reason == "bad-layout":
        units = lines[4][len("layout "):].split(";")
        units = units[:-1]
        lines[4] = "layout " + ";".join(units)
    elif reason == "bad-log":
        lines.append("toss A 5v 0")
    else:
        raise AssertionError(reason)
    return ("\n".join(lines) + "\n").encode("ascii")


def build(seed: int, index: int) -> bytes:
    """Build the neutral indexed record for seed and schedule index."""
    mode = MODE_NAMES[mode_for_index(index)]
    if mode == "plain":
        return _try(lambda rng: _build_generic(rng, [], "plain"), seed)
    if mode == "random":
        return _try(lambda rng: _build_generic(rng, [], "random"), seed)
    if mode == "random-log":
        return _try(lambda rng: _build_random_log(rng), seed)
    if mode == "xuong":
        return _try(_build_xuong, seed)
    if mode in CUOC_MODES:
        return _try(lambda rng: _build_cuoc(rng, mode), seed)
    if mode in FINE_MODES:
        return _try(lambda rng: _build_fine(rng, mode), seed)
    if mode.startswith("illegal-"):
        reason = mode[len("illegal-"):]
        return _try(lambda rng: _mutate_illegal(rng, reason), seed)
    raise AssertionError(mode)


def _build_random_log(rng: random.Random) -> bytes | None:
    units = _base_units(rng, [])
    if units is None:
        return None
    winner = rng.choice(ref.SEATS)
    losers = ref.other_seats(winner)
    win_index, uu = _decide(rng, units, None)
    log = []
    rnd = 1
    for _ in range(rng.randint(0, 10)):
        seat = rng.choice(losers)
        card = rng.choice(ref.KINDS)
        log.append((seat, card, rnd))
        rnd += rng.randint(0, 1)
    role = rng.choice(("dealer", "nondealer"))
    source = rng.choice(("draw", "gate", "stock"))
    streak = rng.choice(("fresh", "thong"))
    return _assemble(rng, units, role, source, streak, log, winner, win_index, uu)


def _build_xuong(rng: random.Random) -> bytes | None:
    """A guaranteed plain win: ten ca units, one red card, no honour, empty log."""
    units = [
        ("ca", ("2v", "2n")), ("ca", ("2v", "2s")), ("ca", ("3v", "3n")),
        ("ca", ("3v", "3s")), ("ca", ("4v", "4n")), ("ca", ("4v", "4s")),
        ("ca", ("5v", "5n")), ("ca", ("5v", "5s")), ("ca", ("6v", "6n")),
        ("ca", ("9v", "9n")),
    ]
    return _assemble(rng, units, "nondealer", "stock", "fresh", [], "A", 0, "2v")


def _build_cuoc(rng: random.Random, mode: str) -> bytes | None:
    forced: list = []
    white_only = False
    if mode == "tom":
        forced = [("ca", ("3v", "3s")), ("chan", ("7n", "7n"))]
    elif mode == "leo":
        forced = [("chan", ("9v", "9v")), ("chan", ("8s", "8s")), ("chan", ("ci", "ci"))]
    elif mode == "bachdinh":
        white_only = True
    elif mode == "tamdo":
        forced = [
            ("chan", ("9v", "9v")), ("chan", ("9s", "9s")),
            ("chan", ("8v", "8v")), ("chan", ("8s", "8s")),
        ]
        white_only = True
    elif mode == "kinhtuchi":
        forced = [("chan", ("ci", "ci")), ("chan", ("ci", "ci"))]
    elif mode == "thienkhai":
        rank = rng.choice("2345")
        forced = [("chan", (rank + "n", rank + "n")), ("chan", (rank + "n", rank + "n"))]
    return _build_generic(rng, forced, mode, white_only)
