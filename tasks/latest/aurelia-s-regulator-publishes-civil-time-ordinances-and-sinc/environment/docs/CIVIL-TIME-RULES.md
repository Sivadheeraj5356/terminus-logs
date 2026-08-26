# Civil time rules

Normative. These rules determine, for any jurisdiction and any instant, the offset
from UT, whether daylight saving is in force, and the abbreviation in use.

## 1. Enactment sequence

Ordinances of a jurisdiction are ordered by `enacted` date; ties are broken by the
sequence number in the identifier, then by the identifier itself. This ordering is the
**enactment sequence**. Repeal ordinances occupy a place in it.

## 2. Force

An establishing ordinance is in force at an instant when its effective instant is at
or before that instant, and no repeal ordinance naming it has an effective instant at
or before that instant.

A repeal ordinance takes effect at its own effective instant. It never governs.

An ordinance whose repeal takes effect at or before its own effective instant is never
in force and contributes nothing.

## 3. Governing ordinance

The ordinance **governing** an instant is the establishing ordinance in force there
with the greatest enactment sequence. Where the governing ordinance changes, a
**governing interval** ends and the next begins.

Nothing governs instants before the first effective instant of the jurisdiction.

## 4. Anchors

An anchored instant is converted to UT using the offset and the save in force
immediately before it — that is, those established by the ordinance governing the
instant one second earlier. Where nothing governs, the jurisdiction's mean solar
offset stands in.

| Anchor | UT instant |
| --- | --- |
| `universal` | the civil value, read as UT |
| `standard` | the civil value less the standard offset in force before it |
| `wall` | the civil value less the offset and the save in force before it |

## 5. Basis chains

`standard-offset: basis <ordinance>` takes the standard offset that the named
ordinance establishes, following the chain until a literal offset is reached. A cycle
is a corpus error.

## 6. Observances

An observance's `begin` and `end` recur every calendar year, indefinitely, in both
directions. Each recurrence is anchored per rule 4: a `begin` against a save of zero,
an `end` against the save its `begin` establishes.

The save and the abbreviation in force at an instant under an ordinance are those of
the most recent recurrence at or before that instant, which may fall in an earlier
calendar year. An ordinance without an observance holds a save of zero and its
`standard-label`.

## 7. Daylight saving and abbreviations

Daylight saving is in force exactly when the save is not zero, whatever its sign.

The keyword `numeric` denotes the abbreviation `±HH`, `±HHMM` or `±HHMMSS` of the
offset from UT then in force, using the shortest of the three that loses nothing.

## 8. Timeline

The timeline of a jurisdiction begins with mean solar time, offset by
`meridian_seconds`, abbreviated `LMT`, in force until the first transition.

A **transition** is emitted at an instant where the triple of offset from UT, daylight
saving flag, and abbreviation differs from the triple in force immediately before it.
Candidate instants are the start of each governing interval and each recurrence of the
governing ordinance's observance.

Transitions are emitted from the first effective instant through
`2037-12-31T23:59:59Z` inclusive. No transition is emitted for a later instant; the
behaviour of the jurisdiction after the last transition is carried entirely by the
POSIX footer of its zone file.

## 9. Disambiguating civil time

A civil time may correspond to no instant, one instant, or two.

Where it corresponds to two, the earlier is taken unless a fold of 1 is requested, in
which case the later is taken.

Where it corresponds to none, it falls in a gap opened by a transition. Under the
`reject` policy no instant is returned. Under the `shift` policy the civil value is
read against the offset in force immediately before the gap.
