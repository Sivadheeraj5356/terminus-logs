"""Precedence resolution, anchor fixpoint, recurrence expansion, transition timeline."""

from .civil import civil_from_days, civil_seconds, days_from_civil
from .parse import CorpusError

HORIZON = days_from_civil(2037, 12, 31) * 86400 + 86399
INT32_MIN = -(2 ** 31)
INT32_MAX = 2 ** 31 - 1
_INF = float("inf")


def numeric_label(utoff):
    sign = "-" if utoff < 0 else "+"
    a = abs(utoff)
    h, m, s = a // 3600, (a % 3600) // 60, a % 60
    if s:
        return "%s%02d%02d%02d" % (sign, h, m, s)
    if m:
        return "%s%02d%02d" % (sign, h, m)
    return "%s%02d" % (sign, h)


def _label(text, utoff):
    return numeric_label(utoff) if text == "numeric" else text


class Transition:
    __slots__ = ("ut", "utoff", "isdst", "abbrev", "anchor", "ordinance")

    def __init__(self, ut, utoff, isdst, abbrev, anchor, ordinance):
        self.ut = ut
        self.utoff = utoff
        self.isdst = isdst
        self.abbrev = abbrev
        self.anchor = anchor
        self.ordinance = ordinance

    def key(self):
        return (self.utoff, self.isdst, self.abbrev)


class Segment:
    __slots__ = ("start", "end", "ordinance", "stdoff")

    def __init__(self, start, end, ordinance, stdoff):
        self.start = start
        self.end = end
        self.ordinance = ordinance
        self.stdoff = stdoff


class ZoneTimeline:
    def __init__(self, zone, meridian, transitions, segments, ords, footer, types):
        self.zone = zone
        self.meridian = meridian
        self.transitions = transitions
        self.segments = segments
        self.ordinances = ords
        self.footer = footer
        self.types = types


def _to_ut(civ, anchor, stdoff, save_before):
    if anchor == "universal":
        return civ
    if anchor == "standard":
        return civ - stdoff
    return civ - stdoff - save_before


def _resolve_basis(ords):
    by_id = {o.oid: o for o in ords if o.kind == "establish"}
    resolved = {}

    def walk(oid, seen):
        if oid in resolved:
            return resolved[oid]
        if oid in seen:
            raise CorpusError("basis cycle at %s" % oid)
        o = by_id.get(oid)
        if o is None:
            raise CorpusError("unknown basis reference %s" % oid)
        seen.add(oid)
        val = o.std_offset if o.basis is None else walk(o.basis, seen)
        resolved[oid] = val
        return val

    for oid in by_id:
        walk(oid, set())
    return resolved


def _events_for_year(o, stdoff, y):
    """The begin and end recurrence instants of ordinance o in calendar year y."""
    out = []
    b, e = o.begin, o.end
    cb = civil_seconds(y, b.month, b.day, b.tod)
    out.append((_to_ut(cb, b.anchor, stdoff, 0), b.save, b.label, b.anchor))
    ce = civil_seconds(y, e.month, e.day, e.tod)
    out.append((_to_ut(ce, e.anchor, stdoff, b.save), e.save, e.label, e.anchor))
    return out


def _state_of(o, stdoff, t):
    """(save, label, anchor) in force at instant t under ordinance o, with carry-over."""
    if o.begin is None:
        return (0, o.std_label, o.eff_anchor)
    y = civil_from_days(t // 86400)[0]
    best = None
    for yy in (y - 2, y - 1, y, y + 1):
        for ut, save, label, anchor in _events_for_year(o, stdoff, yy):
            if ut <= t and (best is None or ut > best[0]):
                best = (ut, save, label, anchor)
    if best is None:
        raise CorpusError("no recurrence at or before %d for %s" % (t, o.oid))
    return (best[1], best[2], best[3])


def _segments_from(ords, eff, seq, stdoffs):
    repeal_at = {}
    for o in ords:
        if o.kind != "repeal":
            continue
        if o.repeals not in eff:
            raise CorpusError("%s repeals unknown %s" % (o.oid, o.repeals))
        prev = repeal_at.get(o.repeals)
        repeal_at[o.repeals] = eff[o.oid] if prev is None else min(prev, eff[o.oid])

    windows = []
    for o in ords:
        if o.kind != "establish":
            continue
        start = eff[o.oid]
        end = repeal_at.get(o.oid, _INF)
        if end > start:
            windows.append((start, end, seq[o.oid], o.oid))
    if not windows:
        raise CorpusError("no effective ordinances")

    bounds = sorted({w[0] for w in windows} | {w[1] for w in windows if w[1] != _INF})
    pieces = []
    for i, b in enumerate(bounds):
        nxt = bounds[i + 1] if i + 1 < len(bounds) else _INF
        if nxt == b:
            continue
        covering = [w for w in windows if w[0] <= b < w[1]]
        if not covering:
            continue
        gov = max(covering, key=lambda w: w[2])[3]
        pieces.append((b, nxt, gov))

    merged = []
    for start, end, gov in pieces:
        if merged and merged[-1][2] == gov and merged[-1][1] == start:
            merged[-1] = (merged[-1][0], end, gov)
        else:
            merged.append((start, end, gov))
    return [Segment(s, None if e == _INF else e, g, stdoffs[g]) for s, e, g in merged]


def _effective_instant(o, seg, by_id, stdoffs, meridian, t_guess):
    """The UT instant an ordinance takes effect: its anchor is resolved against the
    offset and save established by the ordinance governing the instant just before."""
    if seg is None:
        sb_std, sb_save = meridian, 0
    else:
        g = by_id[seg.ordinance]
        sb_std = stdoffs[g.oid]
        sb_save = _state_of(g, sb_std, t_guess - 1)[0]
    return _to_ut(o.eff_civil, o.eff_anchor, sb_std, sb_save)


def _governing_at(segments, t):
    lo, hi = 0, len(segments) - 1
    if t < segments[0].start:
        return None
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if segments[mid].start <= t:
            lo = mid
        else:
            hi = mid - 1
    return segments[lo]


def build_zone(meta, ords):
    stdoffs = _resolve_basis(ords)
    seq = {o.oid: i for i, o in enumerate(ords)}
    by_id = {o.oid: o for o in ords}

    eff = {}
    for o in ords:
        eff[o.oid] = _to_ut(o.eff_civil, o.eff_anchor, stdoffs.get(o.oid, 0), 0)

    segments = None
    for _ in range(16):
        segments = _segments_from(ords, eff, seq, stdoffs)
        nxt = {}
        for o in ords:
            seg = _governing_at(segments, eff[o.oid] - 1)
            nxt[o.oid] = _effective_instant(o, seg, by_id, stdoffs,
                                            meta.meridian_seconds, eff[o.oid])
        if nxt == eff:
            break
        eff = nxt
    else:
        raise CorpusError("anchor fixpoint did not converge for %s" % meta.zone)
    segments = _segments_from(ords, eff, seq, stdoffs)

    transitions = []
    prev = (meta.meridian_seconds, 0, "LMT")
    for seg in segments:
        if seg.start > HORIZON:
            break
        g = by_id[seg.ordinance]
        stdoff = stdoffs[g.oid]

        save, label, _ = _state_of(g, stdoff, seg.start)
        utoff = stdoff + save
        st = (utoff, 1 if save != 0 else 0, _label(label, utoff))
        if st != prev:
            transitions.append(Transition(seg.start, st[0], st[1], st[2],
                                          g.eff_anchor, g.oid))
            prev = st

        if g.begin is not None:
            hi = HORIZON if seg.end is None else min(HORIZON, seg.end - 1)
            y0 = civil_from_days(seg.start // 86400)[0] - 1
            y1 = civil_from_days(hi // 86400)[0] + 1
            evs = []
            for y in range(y0, y1 + 1):
                evs.extend(_events_for_year(g, stdoff, y))
            for ut, save, label, anchor in sorted(evs):
                if ut <= seg.start or ut > hi:
                    continue
                utoff = stdoff + save
                st = (utoff, 1 if save != 0 else 0, _label(label, utoff))
                if st != prev:
                    transitions.append(Transition(ut, st[0], st[1], st[2], anchor, g.oid))
                    prev = st

    for a, b in zip(transitions, transitions[1:]):
        if b.ut <= a.ut:
            raise CorpusError("%s: non-monotonic transitions" % meta.zone)

    types = [(meta.meridian_seconds, 0, "LMT", 0, 0)]
    index = {(meta.meridian_seconds, 0, "LMT"): 0}
    for tr in transitions:
        if tr.key() not in index:
            isstd = 0 if tr.anchor == "wall" else 1
            isut = 1 if tr.anchor == "universal" else 0
            index[tr.key()] = len(types)
            types.append((tr.utoff, tr.isdst, tr.abbrev, isstd, isut))

    footer = build_footer(by_id, stdoffs, segments)
    tl = ZoneTimeline(meta.zone, meta.meridian_seconds, transitions, segments,
                      [(o, stdoffs.get(o.oid), seq[o.oid], eff[o.oid]) for o in ords],
                      footer, types)
    tl.type_index = index
    return tl


def build_footer(by_id, stdoffs, segments):
    from .posix import footer_string
    final = None
    for seg in segments:
        if seg.start <= HORIZON:
            final = seg
    if final is None or final.end is not None:
        raise CorpusError("no perpetual governing ordinance at the horizon")
    return footer_string(by_id[final.ordinance], stdoffs[final.ordinance])
