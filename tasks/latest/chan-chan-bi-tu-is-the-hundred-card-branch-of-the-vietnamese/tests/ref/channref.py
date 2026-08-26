"""Independent Python referee for the Chan (bi tu, 100-card) winning account.

The referee reads one recorded Chan winning declaration and writes the byte-exact
"account" the table keeps: it validates the twenty-card round hand, names every
cuoc (winning honour) that applies under the precedence and exclusion rules, sums
the diem, charges the phat (fines) the discard log triggers, and settles the four
seats.  All rendering uses ASCII tokens only.
"""

from __future__ import annotations

import re
from collections import Counter

# --- deck ---------------------------------------------------------------------
# The Chan pack is the To Tom deck stripped of the Nhat rank and the Thang / Cu
# honours: 100 cards, 25 kinds, four copies each.  A kind token is two ASCII
# characters: a rank digit 2..9 with a suit v (van) / n (van/wen) / s (sach), or
# the lone honour "ci" (chi chi).
RANKS = "23456789"
SUITS = "vns"
KINDS = [rank + suit for suit in SUITS for rank in RANKS] + ["ci"]
KIND_INDEX = {kind: index for index, kind in enumerate(KINDS)}
CARD_RE = re.compile(r"(?:[2-9][vns]|ci)\Z")
INT_RE = re.compile(r"(?:0|[1-9][0-9]*)\Z")
UNIT_RE = re.compile(r"(chan|ca)\(([^(),]+),([^(),]+)\)\Z")
SEATS = ("A", "B", "C", "D")

# The five red kinds (quan do): cuu van, cuu sach, bat van, bat sach, chi chi.
RED = {"9v", "9s", "8v", "8s", "ci"}

CUOC_ORDER = [
    "thienu", "diau", "thong", "chi", "banthu",
    "tom", "leo", "bachdinh", "tamdo", "kinhtuchi", "thienkhai",
]
CUOC_DIEM = {
    "thienu": 6, "diau": 6, "thong": 3, "chi": 3, "banthu": 4,
    "tom": 4, "leo": 5, "bachdinh": 8, "tamdo": 8, "kinhtuchi": 8, "thienkhai": 5,
}
TOM_SET = ("3v", "3s", "7n")
LEO_SET = ("9v", "8s", "ci")

BASE_DIEM = 3


def other_seats(winner: str) -> list[str]:
    """Return the three losing seats in fixed A B C D order."""
    return [seat for seat in SEATS if seat != winner]


def kind_key(kind: str) -> int:
    """Return the canonical display position of a kind."""
    return KIND_INDEX[kind]


def sorted_kinds(cards: list[str] | tuple[str, ...]) -> list[str]:
    """Sort card kinds by the canonical display order."""
    return sorted(cards, key=kind_key)


def _rank_of(kind: str) -> str:
    return kind[0]


def _suit_of(kind: str) -> str:
    return kind[1]


def _fault(line: int, reason: str) -> str:
    return "Fault = line:%d reason:%s\nResult = void\n" % (line, reason)


def _clean_lines(raw: bytes) -> tuple[list[str] | None, int]:
    """Split into stripped ASCII lines, or report the first offending line."""
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        return None, raw[: error.start].count(b"\n") + 1
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return None, 1
    for index, line in enumerate(lines, 1):
        if (
            not line
            or line != line.strip(" ")
            or "  " in line
            or "\t" in line
            or "\r" in line
        ):
            return None, index
    return lines, 0


def _parse_unit(text: str) -> tuple[str, tuple[str, str]] | None:
    """Parse one declared unit; validate chan / ca membership."""
    match = UNIT_RE.fullmatch(text)
    if not match:
        return None
    kind, first, second = match.group(1), match.group(2), match.group(3)
    if not CARD_RE.fullmatch(first) or not CARD_RE.fullmatch(second):
        return None
    if kind == "chan":
        if first != second:
            return None
    else:  # ca
        if first == "ci" or second == "ci":
            return None
        if _rank_of(first) != _rank_of(second) or _suit_of(first) == _suit_of(second):
            return None
    return kind, (first, second)


def _unit_text(kind: str, cards: tuple[str, str]) -> str:
    ordered = sorted_kinds(cards)
    return "%s(%s,%s)" % (kind, ordered[0], ordered[1])


def _unit_sort_key(unit: tuple[str, tuple[str, str]]) -> tuple:
    kind, cards = unit
    ordered = sorted_kinds(cards)
    return (0 if kind == "chan" else 1, kind_key(ordered[0]), kind_key(ordered[1]))


def trace(raw: str | bytes) -> str:
    """Replay one Chan declaration and return its exact referee account."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    lines, bad_line = _clean_lines(raw)
    if lines is None:
        return _fault(bad_line, "malformed")

    # ---- fixed six-line header + a log section -------------------------------
    if len(lines) < 6:
        return _fault(len(lines) + 1, "malformed")
    if lines[0] != "CHAN/1":
        return _fault(1, "malformed")

    win_fields = lines[1].split(" ")
    if (
        len(win_fields) != 5
        or win_fields[0] != "win"
        or win_fields[1] not in SEATS
        or win_fields[2] not in ("dealer", "nondealer")
        or win_fields[3] not in ("deal", "draw", "gate", "stock")
        or win_fields[4] not in ("fresh", "thong")
    ):
        return _fault(2, "malformed")
    winner, role, source, streak = win_fields[1], win_fields[2], win_fields[3], win_fields[4]

    uu_fields = lines[2].split(" ")
    if len(uu_fields) != 2 or uu_fields[0] != "uu" or not CARD_RE.fullmatch(uu_fields[1]):
        return _fault(3, "malformed")
    uu = uu_fields[1]

    hand_fields = lines[3].split(" ")
    if (
        len(hand_fields) != 20
        or hand_fields[0] != "hand"
        or any(not CARD_RE.fullmatch(card) for card in hand_fields[1:])
    ):
        return _fault(4, "malformed")
    hand = hand_fields[1:]

    layout_fields = lines[4].split(" ")
    if len(layout_fields) != 2 or layout_fields[0] != "layout" or not layout_fields[1]:
        return _fault(5, "malformed")
    unit_texts = layout_fields[1].split(";")
    units: list[tuple[str, tuple[str, str]]] = []
    for text in unit_texts:
        parsed = _parse_unit(text)
        if parsed is None:
            return _fault(5, "malformed")
        units.append(parsed)

    if lines[5] != "log":
        return _fault(6, "malformed")

    log: list[tuple[str, str, int]] = []
    for offset, line in enumerate(lines[6:], 7):
        fields = line.split(" ")
        if (
            len(fields) != 4
            or fields[0] != "toss"
            or fields[1] not in SEATS
            or not CARD_RE.fullmatch(fields[2])
            or not INT_RE.fullmatch(fields[3])
        ):
            return _fault(offset, "malformed")
        log.append((fields[1], fields[2], int(fields[3])))

    # ---- semantic validation (precedence: hand, layout, log) -----------------
    full = Counter(hand)
    full[uu] += 1
    if any(count > 4 for count in full.values()):
        return _fault(4, "bad-hand")

    if len(units) != 10:
        return _fault(5, "bad-layout")
    laid = Counter()
    for _, cards in units:
        laid[cards[0]] += 1
        laid[cards[1]] += 1
    if laid != full:
        return _fault(5, "bad-layout")
    first_kind, first_cards = units[0]
    if uu not in first_cards:
        return _fault(5, "bad-layout")

    previous_round = 0
    for offset, (_, _, rnd) in enumerate(log, 7):
        if rnd < 1 or rnd < previous_round:
            return _fault(offset, "bad-log")
        previous_round = rnd

    # ---- winning honours (cuoc) ---------------------------------------------
    banthu = first_kind == "chan" and source != "deal"
    thienu = role == "dealer" and source == "deal"
    diau = role == "nondealer" and source == "deal"
    suppress = thienu or diau

    twenty = list(hand) + [uu]
    reds = sum(1 for card in twenty if card in RED)
    have = Counter(twenty)
    chan_kinds = {cards[0] for kind, cards in units if kind == "chan"}
    quad_kinds = [kind for kind, count in have.items() if count == 4 and kind != "ci"]

    cuoc: list[str] = []
    if thienu:
        cuoc.append("thienu")
    if diau:
        cuoc.append("diau")
    if streak == "thong" and not suppress:
        cuoc.append("thong")
    if source == "gate" and not suppress:
        cuoc.append("chi")
    if banthu:
        cuoc.append("banthu")
    if all(have[card] >= 1 for card in TOM_SET):
        cuoc.append("tom")
    if all(have[card] >= 1 for card in LEO_SET):
        cuoc.append("leo")
    if reds == 0:
        cuoc.append("bachdinh")
    if reds == 8:
        cuoc.append("tamdo")
    if have["ci"] == 4:
        cuoc.append("kinhtuchi")
    for _ in quad_kinds:
        cuoc.append("thienkhai")

    if not cuoc:
        cuoc = ["xuong"]
        diem = BASE_DIEM
    else:
        diem = BASE_DIEM + sum(CUOC_DIEM[name] for name in cuoc)

    # ---- fines (phat) from the discard log -----------------------------------
    fines: list[tuple[str, str, int]] = []  # (type, seat, points)
    seat_points: dict[str, int] = {seat: 0 for seat in SEATS}
    for seat in other_seats(winner):
        seat_tosses = [(card, rnd) for tseat, card, rnd in log if tseat == seat]
        for card, _ in seat_tosses:
            if card in chan_kinds:
                fines.append(("treo-tranh", seat, 2))
                seat_points[seat] += 2
        if source == "draw":
            for card, _ in seat_tosses:
                if card == uu:
                    fines.append(("tra-cua", seat, 3))
                    seat_points[seat] += 3
        counts = Counter(card for card, _ in seat_tosses)
        for kind in sorted_kinds([k for k, c in counts.items() if c >= 2]):
            for _ in range(counts[kind] - 1):
                fines.append(("lot-song", seat, 1))
                seat_points[seat] += 1

    total_fine = sum(points for _, _, points in fines)

    # ---- render --------------------------------------------------------------
    winning = _unit_text(first_kind, first_cards)
    rest = sorted(units[1:], key=_unit_sort_key)
    layout_render = ";".join([winning] + [_unit_text(kind, cards) for kind, cards in rest])

    out = [
        "Chan = bi-tu 100-card",
        "Winner = " + winner,
        "Source = %s/%s/%s" % (role, source, streak),
        "Uu = " + uu,
        "Wait = " + ("banthu" if banthu else "thuong"),
        "Layout = " + layout_render,
        "Reds = %d" % reds,
        "Cuoc = " + ",".join(cuoc),
        "Diem = %d" % diem,
    ]
    if fines:
        for kind, seat, points in fines:
            out.append("Phat = %s:%s:%d" % (kind, seat, points))
    else:
        out.append("Phat = none")

    net = {seat: -diem - seat_points[seat] for seat in SEATS}
    net[winner] = 3 * diem + total_fine
    for seat in SEATS:
        out.append("Settle %s = %d" % (seat, net[seat]))
    out.append("Result = uu")
    return "\n".join(out) + "\n"
