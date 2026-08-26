Our measurement pipeline profiles empirical histograms whose true modes come
out oversplit by sampling noise, and the consolidation has to be
self-consistent — this is a fixed-point statistics computation, not a general
data-processing utility. Every bin first climbs to the lowest-position
heaviest bin inside its radius window, looking again from each stop until it
settles, which yields the initial modes and their basins. Then the weak modes
dissolve in rounds: the mass bar is derived from the surviving mode count
itself — the floor of the total mass over the sharpness times the number of
survivors — every basin strictly under the bar dissolves at once, each
dissolved basin is handed whole to the surviving mode nearest its own mode
with ties to the lower position, and the bar is recomputed from the shrunken
mode set, so one dissolution can drag further modes under on the next pass.
An optional guard directive caps how many dissolved basins a given mode may
ever absorb across the whole run, and once that cap is spent the nearest
search has to walk past it to the next eligible mode. Independent of any
directive, a mode that ever holds an outright majority of the total mass is
sealed for the remainder of the consolidation and can take on no further
dissolved basin — a ceiling that emerges from the masses alone and is written
nowhere in the input — so a dissolving basin whose nearest survivor is a sealed
mode belongs instead to the next nearest mode still open, with the plain nearest
rule governing only when every open mode is spent. The iteration ends the first
time a round dissolves nothing. I want a Java
tool, invoked as `/app/consolidate <data_file>`, that runs this consolidation
on one histogram and reports the converged profile.

The converged partition feeds the report: mode positions in ascending order,
each basin's share of the total mass as an exact fraction reduced to lowest
terms, the heaviest mode with ties to the lower position, its floored percent
concentration, and gap statistics over consecutive mode positions using the
lower median, all zero when fewer than two modes remain. Two figures
deliberately ignore the consolidation — the initial mode count and the full
position span cover the histogram as given. Rounds count only when their
dissolutions are applied, the reported bar is the one computed in the round
that stopped the iteration, and every quantity in this task is an exact
integer or an exact reduced fraction; there is no floating point anywhere.

Build the program from scratch on the Java standard library alone — no build
tool, no third-party jar; one source file compiled with `javac` is the whole
program. Write the report as a single JSON line to `/app/output/result.json`
and print the identical line to standard output. The grammar, the value
schema, the climb, the iteration, a worked example, the exact output object,
and the exit codes are pinned in `/app/SPEC.md`; follow it precisely.
Everything runs offline, and your program must be correct for any conforming
histogram, not just samples you may find.
