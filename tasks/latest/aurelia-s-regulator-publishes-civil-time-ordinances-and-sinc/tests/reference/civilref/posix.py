"""POSIX TZ footer construction (RFC 8536 section 3.3 / POSIX XBD 8.3)."""

from .parse import CorpusError


def _name(abbrev):
    if len(abbrev) >= 3 and abbrev.isalpha():
        return abbrev
    return "<%s>" % abbrev


def fmt_offset(utoff):
    """POSIX offsets are the value ADDED to local time to get UT: the sign inverts."""
    v = -utoff
    sign = "-" if v < 0 else ""
    a = abs(v)
    h, m, s = a // 3600, (a % 3600) // 60, a % 60
    if s:
        return "%s%d:%02d:%02d" % (sign, h, m, s)
    if m:
        return "%s%d:%02d" % (sign, h, m)
    return "%s%d" % (sign, h)


def fmt_time(secs):
    sign = "-" if secs < 0 else ""
    a = abs(secs)
    h, m, s = a // 3600, (a % 3600) // 60, a % 60
    if s:
        return "%s%d:%02d:%02d" % (sign, h, m, s)
    if m:
        return "%s%d:%02d" % (sign, h, m)
    return "%s%d" % (sign, h)


def _week_rule(month, spec):
    kind, wd, n = spec
    if kind == "last":
        return "M%d.5.%d" % (month, wd)
    if kind == "ge" and n in (1, 8, 15, 22):
        return "M%d.%d.%d" % (month, (n - 1) // 7 + 1, wd)
    raise CorpusError("day specifier %r is not expressible in a POSIX footer" % (spec,))


def _rule(month, spec, wall_before):
    text = _week_rule(month, spec)
    if wall_before != 7200:
        text += "/" + fmt_time(wall_before)
    return text


def _wall_before(ev, stdoff, save_before):
    if ev.anchor == "wall":
        return ev.tod
    if ev.anchor == "standard":
        return ev.tod + save_before
    return ev.tod + stdoff + save_before


def footer_string(o, stdoff):
    from .timeline import numeric_label

    def lbl(text, utoff):
        return numeric_label(utoff) if text == "numeric" else text

    if o.begin is None:
        return _name(lbl(o.std_label, stdoff)) + fmt_offset(stdoff)

    save = o.begin.save
    dst_utoff = stdoff + save
    std_name = _name(lbl(o.std_label, stdoff))
    dst_name = _name(lbl(o.begin.label, dst_utoff))

    text = std_name + fmt_offset(stdoff) + dst_name
    if dst_utoff != stdoff + 3600:
        text += fmt_offset(dst_utoff)

    text += "," + _rule(o.begin.month, o.begin.day, _wall_before(o.begin, stdoff, 0))
    text += "," + _rule(o.end.month, o.end.day, _wall_before(o.end, stdoff, save))
    return text
