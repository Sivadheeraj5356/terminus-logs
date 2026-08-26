"""Reader for the ordinance corpus: *.ord records and per-zone meta.toml."""

import os
import re

from .civil import MONTHS, WEEKDAYS, days_from_civil

ANCHORS = ("wall", "standard", "universal")

_OFFSET = re.compile(r"^([+-])(\d{1,2}):(\d{2}):(\d{2})$")
_ID = re.compile(r"^ORD-(\d{4})-(\d{2})$")
_EFFECTIVE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{1,3}):(\d{2}):(\d{2})\s+(\w+)$")
_ENACTED = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_DAY_LAST = re.compile(r"^last(\w{3})$")
_DAY_GE = re.compile(r"^(\w{3})>=(\d{1,2})$")
_DAY_LE = re.compile(r"^(\w{3})<=(\d{1,2})$")
_DAY_FIXED = re.compile(r"^d(\d{1,2})$")
_TOD = re.compile(r"^(\d{1,3}):(\d{2}):(\d{2})$")


class CorpusError(Exception):
    pass


class Event:
    __slots__ = ("month", "day", "tod", "anchor", "save", "label")

    def __init__(self, month, day, tod, anchor, save, label):
        self.month = month
        self.day = day
        self.tod = tod
        self.anchor = anchor
        self.save = save
        self.label = label


class Ordinance:
    __slots__ = ("oid", "zone", "enacted", "seq", "eff_civil", "eff_anchor",
                 "std_offset", "basis", "std_label", "begin", "end", "repeals",
                 "kind", "source")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def __repr__(self):
        return "<Ordinance %s %s>" % (self.zone, self.oid)


class ZoneMeta:
    __slots__ = ("zone", "meridian_seconds", "inherits", "inherits_before")

    def __init__(self, zone, meridian_seconds, inherits, inherits_before):
        self.zone = zone
        self.meridian_seconds = meridian_seconds
        self.inherits = inherits
        self.inherits_before = inherits_before


def parse_offset(text):
    m = _OFFSET.match(text)
    if not m:
        raise CorpusError("bad offset %r" % (text,))
    sign, h, mi, s = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
    v = h * 3600 + mi * 60 + s
    return -v if sign == "-" else v


def parse_tod(text):
    m = _TOD.match(text)
    if not m:
        raise CorpusError("bad time of day %r" % (text,))
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))


def parse_dayspec(text):
    m = _DAY_LAST.match(text)
    if m:
        return ("last", WEEKDAYS.index(m.group(1)), 0)
    m = _DAY_GE.match(text)
    if m:
        return ("ge", WEEKDAYS.index(m.group(1)), int(m.group(2)))
    m = _DAY_LE.match(text)
    if m:
        return ("le", WEEKDAYS.index(m.group(1)), int(m.group(2)))
    m = _DAY_FIXED.match(text)
    if m:
        return ("fixed", 0, int(m.group(1)))
    raise CorpusError("bad day specifier %r" % (text,))


def _parse_event(text, default_save, default_label):
    # "Apr Sun>=8 02:00:00 wall save +01:00:00 label WAST"  (save/label optional)
    parts = text.split()
    if len(parts) < 4:
        raise CorpusError("bad observance line %r" % (text,))
    month = MONTHS.index(parts[0]) + 1
    day = parse_dayspec(parts[1])
    tod = parse_tod(parts[2])
    anchor = parts[3]
    if anchor not in ANCHORS:
        raise CorpusError("bad anchor %r" % (anchor,))
    save = default_save
    label = default_label
    i = 4
    while i < len(parts):
        if parts[i] == "save":
            save = parse_offset(parts[i + 1])
            i += 2
        elif parts[i] == "label":
            label = parts[i + 1]
            i += 2
        else:
            raise CorpusError("unknown observance token %r" % (parts[i],))
    return Event(month, day, tod, anchor, save, label)


def parse_ordinance(path):
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    fields = {}
    obs = {}
    in_obs = False
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  "):
            if not in_obs:
                raise CorpusError("%s: indented line outside observance" % path)
            key, _, val = line.strip().partition(":")
            obs[key.strip()] = val.strip()
            continue
        in_obs = False
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key == "observance":
            in_obs = True
            continue
        if key in fields:
            raise CorpusError("%s: duplicate field %r" % (path, key))
        fields[key] = val

    oid = fields["ordinance"]
    m = _ID.match(oid)
    if not m:
        raise CorpusError("%s: bad ordinance id %r" % (path, oid))
    seq = int(m.group(2))

    m = _ENACTED.match(fields["enacted"])
    if not m:
        raise CorpusError("%s: bad enacted %r" % (path, fields["enacted"]))
    enacted = days_from_civil(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = _EFFECTIVE.match(fields["effective"])
    if not m:
        raise CorpusError("%s: bad effective %r" % (path, fields["effective"]))
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh, mi, ss = int(m.group(4)), int(m.group(5)), int(m.group(6))
    anchor = m.group(7)
    if anchor not in ANCHORS:
        raise CorpusError("%s: bad effective anchor %r" % (path, anchor))
    eff_civil = days_from_civil(y, mo, d) * 86400 + hh * 3600 + mi * 60 + ss

    repeals = fields.get("repeals")
    if repeals is not None:
        if "standard-offset" in fields or obs:
            raise CorpusError("%s: a repeal ordinance establishes nothing" % path)
        return Ordinance(
            oid=oid, zone=fields["jurisdiction"], enacted=enacted, seq=seq,
            eff_civil=eff_civil, eff_anchor=anchor, std_offset=None, basis=None,
            std_label=None, begin=None, end=None, repeals=repeals, kind="repeal",
            source=os.path.basename(path),
        )

    so = fields["standard-offset"]
    if so.startswith("basis "):
        std_offset, basis = None, so.split(None, 1)[1]
    else:
        std_offset, basis = parse_offset(so), None

    std_label = fields["standard-label"]

    begin = end = None
    if obs:
        if set(obs) != {"begin", "end"}:
            raise CorpusError("%s: observance needs begin and end" % path)
        begin = _parse_event(obs["begin"], 3600, None)
        if begin.label is None:
            raise CorpusError("%s: observance begin needs a label" % path)
        end = _parse_event(obs["end"], 0, std_label)

    return Ordinance(
        oid=oid, zone=fields["jurisdiction"], enacted=enacted, seq=seq,
        eff_civil=eff_civil, eff_anchor=anchor, std_offset=std_offset, basis=basis,
        std_label=std_label, begin=begin, end=end, repeals=None, kind="establish",
        source=os.path.basename(path),
    )


def parse_meta(path):
    vals = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, val = line.partition("=")
            vals[key.strip()] = val.strip().strip('"')
    inherits_before = vals.get("inherits_before")
    if inherits_before is not None:
        m = _ENACTED.match(inherits_before)
        if not m:
            raise CorpusError("%s: bad inherits_before" % path)
        inherits_before = days_from_civil(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return ZoneMeta(vals["zone"], int(vals["meridian_seconds"]),
                    vals.get("inherits"), inherits_before)


def load_corpus(root):
    """Returns {zone: (ZoneMeta, [Ordinance])} with inheritance applied."""
    zones = {}
    own = {}
    for name in sorted(os.listdir(root)):
        zdir = os.path.join(root, name)
        if not os.path.isdir(zdir):
            continue
        meta = parse_meta(os.path.join(zdir, "meta.toml"))
        ords_ = [parse_ordinance(os.path.join(zdir, f))
                 for f in sorted(os.listdir(zdir)) if f.endswith(".ord")]
        zones[name] = meta
        own[name] = ords_

    out = {}
    for name, meta in zones.items():
        records = list(own[name])
        if meta.inherits:
            if meta.inherits not in own:
                raise CorpusError("%s inherits unknown zone %s" % (name, meta.inherits))
            for o in own[meta.inherits]:
                if o.enacted < meta.inherits_before:
                    records.append(o)
        seen = set()
        for o in records:
            if o.oid in seen:
                raise CorpusError("%s: duplicate ordinance %s" % (name, o.oid))
            seen.add(o.oid)
        records.sort(key=lambda o: (o.enacted, o.seq, o.oid))
        out[name] = (meta, records)
    return out
