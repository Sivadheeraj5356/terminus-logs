# Canonical zone file layout

Zone files are TZif version 2 (RFC 8536). Consumers read them with glibc and with
Python's `zoneinfo`; the diagnostic reader in `zdump` must dump them without
complaint. This document pins the choices RFC 8536 leaves open, so that the same
corpus always produces the same bytes.

All integers are big-endian and two's complement.

## Header

Forty-four octets:

| Octets | Value |
| --- | --- |
| 0–3 | the magic `TZif` |
| 4 | the version octet `2` (0x32) |
| 5–19 | fifteen zero octets |
| 20–23 | `isutcnt` |
| 24–27 | `isstdcnt` |
| 28–31 | `leapcnt` |
| 32–35 | `timecnt` |
| 36–39 | `typecnt` |
| 40–43 | `charcnt` |

`isutcnt` and `isstdcnt` both equal `typecnt`. `leapcnt` is zero.

## Structure

A header, a data block of 32-bit transition times, a second header, a data block of
64-bit transition times, then the footer. Both headers carry the same `typecnt` and
`charcnt`; only `timecnt` differs.

## Data block

In order: `timecnt` transition times; `timecnt` one-octet type indices; `typecnt`
local time type records; `charcnt` octets of designations; `isstdcnt` standard/wall
indicators; `isutcnt` UT/local indicators. Leap second records are absent.

A local time type record is a four-octet offset from UT in seconds, a one-octet
daylight saving flag, and a one-octet index into the designations.

## Time types

Type zero is mean solar time: the jurisdiction's `meridian_seconds`, a daylight saving
flag of zero, the designation `LMT`.

Further types are appended in order of first use along the 64-bit transition list. Two
transitions share a type when their offset, daylight saving flag and designation all
agree.

A type's standard/wall indicator is zero when the rule that first produced it carried
the `wall` anchor, and one otherwise. Its UT/local indicator is one when that rule
carried the `universal` anchor, and zero otherwise. Type zero carries zero for both.

## Designations

One NUL-terminated designation per time type, in type order. A type's designation
index addresses its own entry. Designations are not shared, and no entry is the
suffix of another.

## Transition times

The 64-bit block carries every transition of the timeline, ascending.

The 32-bit block carries those transitions whose instant lies within the range of a
signed 32-bit integer. A transition outside that range is omitted from the 32-bit
block; it is not truncated into it. Both blocks carry the full type list.

## Footer

A newline, a POSIX TZ string, a newline.

The string describes the behaviour of the jurisdiction after its last transition,
which is that of the ordinance governing the horizon.

An abbreviation appears bare when it is three or more characters and wholly
alphabetic, and enclosed in `<` and `>` otherwise.

An offset in the string is the value added to local time to obtain UT, so its sign is
opposite to the offset from UT of the type it describes. It is written as hours,
optionally a colon and minutes, optionally a further colon and seconds, dropping the
trailing components that are zero, with a leading `-` when negative.

Where the governing ordinance carries no observance, the string is the standard
abbreviation followed by its offset, and nothing else.

Otherwise the string is: the standard abbreviation, its offset, the daylight saving
abbreviation, then the daylight saving offset — which is omitted exactly when it is
one hour ahead of standard — then a comma, the rule that begins daylight saving, a
comma, and the rule that ends it.

A rule is `M<month>.<week>.<day>`, where `<day>` is the weekday with Sunday zero, and
`<week>` is 5 for the last such weekday of the month, and otherwise the ordinal of the
week the day specifier selects. A day specifier that no week ordinal describes cannot
appear in a footer.

A rule carries a suffix `/<time>` giving the local wall clock at which it takes
effect, in the offset in force immediately before that transition, written as the
offsets above are written. The suffix is omitted exactly when that time is `2:00:00`.
The time may be negative or may reach beyond `24`.
