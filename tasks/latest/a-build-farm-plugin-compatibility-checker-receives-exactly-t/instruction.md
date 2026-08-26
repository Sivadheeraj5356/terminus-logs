A build-farm plugin compatibility checker receives exactly two command-line
arguments: a candidate dependency version and a requested version selector,
both written as text. For that pair, it must print exactly one line, either
`true` or `false` followed by a newline, reporting whether the candidate version
is admitted by the selector.

The behavior you must reproduce is Gradle's dependency version selection: given
a single candidate version and a version selector, decide whether Gradle would
consider that version to match the selector. Treat Gradle's own matching as the
definition of correct behavior and match it exactly, for every version and
selector pair. This covers Gradle's static-version comparison (how a version
string is split into parts and how those parts are ordered), the special
ordering of qualifier words such as `dev`, `rc`, `snapshot`, `final`, `ga`,
`release` and `sp` (and how unrecognized qualifiers order among themselves),
the comparison of numeric against non-numeric parts, and the tie-breaking
between versions of unequal length.

Qualifier comparison follows Gradle's special meanings, case-insensitively.
The `final`, `ga`, and `release` words are release aliases at the same
position. The `sp` word is still below the base version with no extra qualifier:
for example, `1.0-sp` compares below `1.0`. When a recognized qualifier matches
a bound case-insensitively, later suffix parts do not pull it below that bound;
for example, `RC.beta.3.15` is admitted by `[rc,)`.

The selector may be an exact version, a range written with square and round
brackets and a comma such as `[1.0,2.0)`, `(,1.0]` or `[1.0,)` (with inclusive
and exclusive bounds), a sub-version prefix such as `1.+` or `1.2.+`, the bare
`+`, or one of the dynamic selectors `latest.release` and `latest.integration`.
Reproduce Gradle's rules for each of these forms rather than guessing from the
surface syntax.

For a range with an exclusive upper bound, Gradle also rejects any candidate
whose raw version text starts with the upper-bound text. For example, `3.ga` is
not admitted by `(,3)`, but it is admitted by `(,3]`.

Because the checker evaluates a single candidate at a time and has no component
metadata, `latest.release` and `latest.integration` both admit the candidate
version.

A bracketed selector counts as a range only when each *empty* bound is written
with the matching bracket direction: an empty lower bound must use `(` (as in
`(,1.0]`) and an empty upper bound must use `)` (as in `[1.0,)`). A bracketed
string that breaks this pairing — for example `[,1.0]`, `[,1.0)`, `[1.0,]` or
`(1.0,]` — is *not* a range at all. Gradle does not reject it; it falls back to
treating the entire string as an ordinary exact-version selector, which then
matches only when Gradle's version comparison considers the candidate equal to
that literal selector string. Do not read these forms as one-sided ranges.

The version and selector given to the checker are always well-formed inputs that
Gradle parses without error, so you do not need an error path; concentrate all
of your effort on making the true-or-false decision match Gradle. The program's
observable contract is only the two text inputs and the single boolean output
line.
