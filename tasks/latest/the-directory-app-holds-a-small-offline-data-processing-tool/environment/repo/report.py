#!/usr/bin/env python3
"""Haul-permit throttle report builder.

Reads a quarry-config text file and a traffic-stream text file, replays the traffic
events against the configured allowances, and writes the decision ledger to
standard output, one record per line.

The full output contract -- the truck-and-quarry conjunction, the
throttle/cap limits, the surge-window lifecycle, the inclusive surge boundary,
the shared quarry reserve pool with borrow/repay debt, and the canonical ledger
ordering -- is documented in docs/spec.md.

Only `build_ledger` needs to change. The argument handling, file reading,
parsing/validation, error reporting, and printing are fixed.
"""

import sys


class InputError(Exception):
    """Malformed input, an unknown truck, or any structural violation of
    the config / event contract in docs/spec.md."""


def parse_config(text):
    """Parse the quarry-config text into (subs, plans, member_of).

    subs[name]      -> {"soft", "hard", "grace"}
    plans[name]     -> {"soft", "hard", "grace", "reserve"}
    member_of[name] -> quarry name
    """
    subs, plans, member_of = {}, {}, {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        f = line.split()
        directive = f[0]
        if directive == "TRUCK":
            if len(f) != 5:
                raise InputError("config line %d: TRUCK expects 5 fields" % lineno)
            name = f[1]
            soft, hard, grace = (
                _int(f[2], lineno, "soft"),
                _int(f[3], lineno, "hard"),
                _int(f[4], lineno, "grace"),
            )
            if soft < 0 or hard < 0 or grace < 0:
                raise InputError("config line %d: negative parameter" % lineno)
            if hard < soft:
                raise InputError("config line %d: hard < soft" % lineno)
            if name in subs:
                raise InputError("config line %d: duplicate truck %s" % (lineno, name))
            subs[name] = {"soft": soft, "hard": hard, "grace": grace}
        elif directive == "QUARRY":
            # QUARRY accepts an optional 6th field: the shared reserve pool capacity
            # (default 0 when omitted).
            if len(f) not in (5, 6):
                raise InputError("config line %d: QUARRY expects 5 or 6 fields" % lineno)
            name = f[1]
            soft, hard, grace = (
                _int(f[2], lineno, "soft"),
                _int(f[3], lineno, "hard"),
                _int(f[4], lineno, "grace"),
            )
            reserve = _int(f[5], lineno, "pool") if len(f) == 6 else 0
            if soft < 0 or hard < 0 or grace < 0 or reserve < 0:
                raise InputError("config line %d: negative parameter" % lineno)
            if hard < soft:
                raise InputError("config line %d: hard < soft" % lineno)
            if name in plans:
                raise InputError("config line %d: duplicate quarry %s" % (lineno, name))
            plans[name] = {"soft": soft, "hard": hard, "grace": grace, "reserve": reserve}
        elif directive == "ASSIGN":
            if len(f) != 3:
                raise InputError("config line %d: ASSIGN expects 3 fields" % lineno)
            if f[1] in member_of:
                raise InputError("config line %d: duplicate member %s" % (lineno, f[1]))
            member_of[f[1]] = f[2]
        else:
            raise InputError("config line %d: unknown directive" % lineno)

    for user in subs:
        if user not in member_of:
            raise InputError("truck %s has no quarry" % user)
        if member_of[user] not in plans:
            raise InputError("truck %s maps to unknown quarry %s" % (user, member_of[user]))
    return subs, plans, member_of


def parse_events(text, subs):
    """Parse the traffic-stream text into a list of (tick, kind, user, hauls)."""
    events = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        f = line.split()
        if len(f) != 4:
            raise InputError("event line %d: expected 4 fields" % lineno)
        tick = _int(f[0], lineno, "tick")
        if tick < 0:
            raise InputError("event line %d: negative tick" % lineno)
        kind, user = f[1], f[2]
        if user not in subs:
            raise InputError("event line %d: unknown truck %s" % (lineno, user))
        hauls = _int(f[3], lineno, "hauls")
        if hauls <= 0:
            raise InputError("event line %d: non-positive hauls count" % lineno)
        if kind not in ("HAUL", "RETURN"):
            raise InputError("event line %d: unknown event %r" % (lineno, kind))
        events.append((tick, kind, user, hauls))
    return events


def _int(s, lineno, what):
    try:
        return int(s)
    except ValueError:
        raise InputError("line %d: bad %s value %r" % (lineno, what, s))


def build_ledger(config_text, events_text):
    """Return the ledger as a list of output lines (no trailing newlines).

    This is only a placeholder: it parses the inputs and echoes every HAUL as
    PERMITTED. It does NOT yet apply the allowance model from docs/spec.md (the
    throttle/cap limits, the surge-window lifecycle, the shared quarry reserve pool
    with borrow/repay debt, or the canonical record ordering). Build the real
    report here.
    """
    subs, plans, member_of = parse_config(config_text)
    events = parse_events(events_text, subs)

    out = []
    for tick, kind, user, hauls in events:
        if kind == "HAUL":
            out.append("%d PERMITTED" % tick)
    return out


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("traffic: report.py <quarry-config> <traffic-stream>\n")
        return 2
    try:
        with open(argv[1], "r") as fh:
            config_text = fh.read()
        with open(argv[2], "r") as fh:
            events_text = fh.read()
    except OSError as exc:
        sys.stderr.write("cannot read input: %s\n" % exc)
        return 1
    try:
        lines = build_ledger(config_text, events_text)
    except InputError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    sys.stdout.write("".join(line + "\n" for line in lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
