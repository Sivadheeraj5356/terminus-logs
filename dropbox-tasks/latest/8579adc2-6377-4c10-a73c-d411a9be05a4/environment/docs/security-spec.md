Header budget accounting contract

This document is the authoritative contract for the session and stream
header-memory accounting in framecore. It states what must be true of the
observable counters at every point; it does not describe how any particular
function is implemented.

Ownership. Every stream belongs to exactly one session for its whole
lifetime. The session holds two running totals: the accounted byte volume of
every header block that is currently outstanding (charged but not yet
delivered to the application layer) across all of its streams, and the
accounted number of individual headers making up those outstanding blocks.
Each total has its own configured maximum, set when the session is
constructed. A candidate charge is admissible only when adding it would leave
both totals at or under their maximum; a charge that fits the byte maximum
but would exceed the count maximum is not admissible, and neither is the
reverse. A charge sized or counted so that the resulting total lands exactly
on a maximum is admissible; only a total that would exceed a maximum is
refused.

Charging a header. A header with a non-empty name is charged against both
session totals: the byte charge is the header's name length plus its value
length plus a fixed 32-byte per-header overhead, and the count charge is one.
A header with an empty value but a non-empty name is an entirely ordinary
header for accounting purposes and must be charged and retained exactly like
any other, and the call that added it reports the ordinary success outcome.
A header with an empty name carries no wire meaning under this contract: it
must not be charged against either total and must not be retained in the
stream's pending header list, and the call that added it must report a
distinct, non-success outcome so a caller can tell the header was dropped
rather than counted; on the scripted harness this outcome prints as
status=ignored rather than status=ok.

Header phases. A stream accumulates a header block across a sequence of
add-header operations, all belonging to the stream's current phase. The
category of a phase is one of the ordinary main headers, informational
headers, or trailers; a stream may legitimately pass through more than one
phase over its lifetime, each phase starting fresh. Whenever a stream begins
a new phase, whether it is the first phase or a later one, any charge still
outstanding from a prior phase on that same stream must be fully released
back to the two session totals before the new phase's local state is
considered empty.

Phase order. A stream's phases are not interchangeable: informational
phases, if any, always come before the one main headers phase, and trailers,
if present, always come last and end the sequence. Concretely, from
informational a stream may only move to another informational phase or to
the main headers phase; from the main headers phase a stream may only move
to trailers; and from trailers no further phase may begin. The very first
phase a stream ever begins, whichever category it names, is always
admitted, since nothing has been established yet to violate. A request to
begin a phase out of this order must be refused and must leave the stream
exactly as it was, including its current category and any header block
already accumulated in it; the request that named the disallowed phase
reports a distinct, non-success outcome and nothing else about the stream's
observable state changes.

Delivery. When a stream's currently accumulated header block is delivered to
the application layer, the release of that block's charge back to the two
session totals and the reset of the stream's local accounting to empty must
happen together, as one indivisible step, not as two steps an interleaved
caller could observe apart.

Teardown. If a stream is destroyed while it still holds a not-yet-delivered
header block, whatever charge remains outstanding for that block must be
released back to the two session totals as part of destruction. If nothing
is outstanding at the time of destruction, exactly nothing is released; the
same outstanding charge must never be released back to the session totals
more than once across delivery, phase transition, and destruction combined.

The scripted harness. The framecore binary accepts a script subcommand that
reads a small text file, one operation per line, and drives exactly one
session and its streams against this contract, printing the resulting state
after every operation. The recognized lines are: session <max_bytes>
<max_headers>, which constructs the session; stream <id>, which creates a
stream; start_headers <id> <category>, where category is headers,
informational, or trailers; add_header <id> <name> <value>, where the token
- stands for an empty string; flush <id>; and destroy <id>. Every line's
result is printed as tagged, space-separated key=value fields, and a final
line summarizing the session's totals is printed once the script ends. A
line that is malformed, refers to an unknown stream, or names an unrecognized
command causes the program to exit with a non-zero status and a message on
standard error describing the problem, rather than continuing or crashing;
every other outcome, including an admission that a charge failed the byte or
count maximum or that a requested phase was refused for being out of order,
is a normal result and the script continues. Both the add_header and
start_headers lines include the outcome of that call among their printed
fields.
