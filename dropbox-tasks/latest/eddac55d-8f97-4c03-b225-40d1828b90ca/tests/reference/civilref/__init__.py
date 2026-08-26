"""Reference model for the tzforge ordinance corpus.

Recomputes the whole timeline, the canonical TZif bytes and both database
projections from the committed corpus, so the verifier never carries a literal
expected transition, offset or byte.
"""

import json

from .parse import load_corpus
from .timeline import HORIZON, build_zone
from .tzif import serialize, sha256

__all__ = ["HORIZON", "build_zone", "load_corpus", "serialize", "sha256",
           "build_all", "manifest_bytes", "local_at", "resolve_local"]


def build_all(root):
    return {zone: build_zone(meta, ords)
            for zone, (meta, ords) in sorted(load_corpus(root).items())}


def manifest_bytes(zones):
    entries = []
    for zone in sorted(zones):
        tl = zones[zone]
        raw = serialize(tl)
        entries.append({
            "zone": zone,
            "sha256": sha256(raw),
            "transition_count": len(tl.transitions),
            "first_transition": tl.transitions[0].ut,
            "last_transition": tl.transitions[-1].ut,
        })
    doc = {"version": 1, "zones": entries}
    return (json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _footer_state(tl, t):
    """Offset/isdst/abbrev after the last stored transition, from the perpetual rule."""
    from .civil import civil_from_days
    from .timeline import _events_for_year, _label
    seg = tl.segments[-1]
    match = [(o, so) for o, so, _, _ in tl.ordinances if o.oid == seg.ordinance]
    o, so = match[0]
    if o.begin is None:
        return (so, 0, _label(o.std_label, so))
    y = civil_from_days(t // 86400)[0]
    best = None
    for yy in (y - 1, y, y + 1):
        for ut, save, label, _ in _events_for_year(o, so, yy):
            if ut <= t and (best is None or ut > best[0]):
                best = (ut, save, label)
    save, label = best[1], best[2]
    return (so + save, 1 if save else 0, _label(label, so + save))


def local_at(tl, t):
    """(utoff, isdst, abbrev) in force at UT instant t."""
    if t < tl.transitions[0].ut:
        return (tl.meridian, 0, "LMT")
    if t > tl.transitions[-1].ut:
        return _footer_state(tl, t)
    lo, hi = 0, len(tl.transitions) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if tl.transitions[mid].ut <= t:
            lo = mid
        else:
            hi = mid - 1
    tr = tl.transitions[lo]
    return (tr.utoff, tr.isdst, tr.abbrev)


def _offsets_before(tl):
    """(transition, utoff in force immediately before it) for every transition."""
    prev = tl.meridian
    for tr in tl.transitions:
        yield tr, prev
        prev = tr.utoff


def resolve_local(tl, local_secs, policy, fold):
    """Map a naive local instant to UT. Returns (epoch, kind) with kind in
    {"unique", "fold", "gap"}; epoch is None for a rejected gap."""
    offsets = {tl.meridian, _footer_state(tl, local_secs)[0]}
    offsets.update(tr.utoff for tr in tl.transitions)
    cands = sorted({local_secs - u for u in offsets
                    if local_at(tl, local_secs - u)[0] == u})
    if len(cands) == 1:
        return (cands[0], "unique")
    if len(cands) > 1:
        return (cands[-1] if fold else cands[0], "fold")
    if policy == "reject":
        return (None, "gap")
    for tr, before in _offsets_before(tl):
        if tr.utoff > before and tr.ut + before <= local_secs < tr.ut + tr.utoff:
            return (local_secs - before, "gap")
    raise AssertionError("no gap found for %d in %s" % (local_secs, tl.zone))
