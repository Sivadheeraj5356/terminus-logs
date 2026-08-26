# Histogram mode consolidation profile — full contract

The tool is invoked as `/app/consolidate <data_file>` and consolidates the
modes of one integer histogram self-consistently, then reports the converged
partition profile. This document is the complete reference. Every rule is
binding, and all arithmetic is exact integer arithmetic — no floating point
appears anywhere in this task.

## 1. Line grammar

UTF-8 text, read line by line. Blank lines and lines whose first non-space
character is `#` are ignored. Fields are separated by one or more spaces or
tabs.

- `b <pos> <count>` — one histogram bin. `<pos>` is a decimal integer
  (optional leading `-`); `<count>` is a decimal integer. Bin positions are
  the sample values; counts are how often each value occurred.
- `radius <h>` — the climb window radius, a decimal integer. At most one such
  line; it applies to the whole file wherever it appears.
- `sharp <q>` — the dissolution sharpness, a decimal integer. At most one such
  line; file-wide wherever it appears.
- `guard <pos> <n>` — an absorption cap of `n` on the mode at position `<pos>`,
  file-wide wherever it appears. See section 4a.
- `link <pos1> <pos2>` — merges the guarded modes at `<pos1>` and `<pos2>` into
  one shared absorption budget group, file-wide wherever it appears. See
  section 4b.

Defaults when absent: `h = 2`, `q = 4`.

Parse failures exit 3 and write nothing: unknown first field, wrong field
count, an integer field that is not a plain decimal integer, or input that is
not valid UTF-8.

## 2. Value schema

Checked line by line over the whole file in physical order; the first
offending line stops everything with
`{"status":"malformed","error":"<code>","line":<n>}` and exit 0 (`<n>` is the
1-based physical line number). Within one line the checks run in the order
listed for its kind:

For a `b` line — `bad_pos` then `bad_count` then `duplicate_pos`:

- `bad_pos` — a position outside -1000000000..1000000000.
- `bad_count` — a count below 1 or above 1000000000.
- `duplicate_pos` — two `b` lines share a position.

For a `radius` line — `bad_radius` then `duplicate_radius`:

- `bad_radius` — `h` below 1 or above 50.
- `duplicate_radius` — a second `radius` line.

For a `sharp` line — `bad_sharp` then `duplicate_sharp`:

- `bad_sharp` — `q` below 1 or above 1000000.
- `duplicate_sharp` — a second `sharp` line.

For a `guard` line — `bad_guard_pos` then `bad_guard_cap` then `duplicate_guard`:

- `bad_guard_pos` — `<pos>` outside -1000000000..1000000000.
- `bad_guard_cap` — `<n>` below 1 or above 1000000000.
- `duplicate_guard` — a second `guard` line names the same `<pos>`.

For a `link` line — `bad_link_pos` then `link_self` then `duplicate_link`:

- `bad_link_pos` — either `<pos1>` or `<pos2>` outside -1000000000..1000000000.
- `link_self` — `<pos1>` equals `<pos2>`.
- `duplicate_link` — the unordered pair `{<pos1>, <pos2>}` already named
  together by an earlier `link` line, in either order.

After the whole file, in order: `no_bins` — the file contains no `b` line at
all (reported with `"line":0`). Only once at least one `b` line exists:
`unknown_guard` — a `guard` line names a position matched by no `b` line
anywhere in the file, using the first such `guard` line in physical order
(reported at that line's own number). Then `unknown_link` — a `link` line
names a position, on either side, matched by no `b` line anywhere, using the
first such `link` line in physical order. Then `link_unguarded` — a `link`
line names a position, on either side, that never has its own `guard` line
anywhere in the file, using the first such `link` line in physical order.

## 3. The climb and the initial partition

Let the bins hold counts c(p) at their positions p, and let M be the total
mass (the sum of every count).

The climb target of a bin at position p is the bin inside the window
[p-h, p+h] with the greatest count, ties resolved to the lowest position. The
bin itself is always inside its own window. A bin whose target is itself is a
mode. A bin whose target differs climbs to the target and looks again from
there, repeating until it reaches a mode. Every climb terminates: each hop
either strictly increases the count or keeps the count equal while strictly
lowering the position.

The initial modes are the bins that are their own target. The basin of a mode
is the set of bins whose climb ends at it; the basin mass is the sum of their
counts. Every bin belongs to exactly one basin, so the basin masses sum to M.
The number of initial modes is reported as `raw_modes` and never changes
afterwards — it is deliberately a raw figure.

## 4. The consolidation iteration

The surviving mode set starts as the initial modes. Each round works on the
current survivors:

1. The bar. With m surviving modes, the round's bar is
   T = floor(M / (q * m)).
2. Dissolution. Every surviving mode whose basin mass is strictly below T
   dissolves. All dissolutions in a round land at once.
3. Stopping. If the round dissolves nothing, the iteration stops. Otherwise
   each dissolved basin is handed WHOLE to the surviving mode nearest the
   dissolved mode's own position — distance is the absolute difference of
   mode positions, ties resolved to the lower surviving position; the
   receiving basin's mass grows by the whole dissolved mass. The round
   counter increases by one and the next round starts.

The basins always cover the whole mass, so at least one basin always reaches
the bar and the surviving set never empties; the iteration terminates because
every applied round removes at least one mode. Only rounds whose dissolutions
were applied count toward `rounds`. `threshold_final` is the bar T computed in
the round in which the iteration stopped.

The receiving mode for a dissolved basin is chosen only from the modes that
remain surviving once every dissolution of the current round has been
decided; a mode that is itself dissolving in the same round is never a valid
destination for another basin, however close its position.

## 4a. Absorption guards

A `guard <pos> <n>` line gives the mode at position `<pos>` a lifetime cap of
`n` dissolved basins it may receive, counted across every round of the run,
not reset per round, and evaluated against the count that mode has already
received from every earlier round combined (not from basins dissolving in
the same round as each other). When the nearest surviving mode is sought for
a dissolved basin, a candidate that is guarded and has already reached its
cap is skipped in favor of the next nearest eligible candidate under the
same distance then position rule; a mode dissolving in the current round is
still never eligible regardless of any guard. If every candidate that is not
dissolving this round is guard exhausted, the guards are set aside for that
one basin only and the ordinary nearest rule decides its destination without
them. Each basin handed to a guarded mode counts as exactly one unit against
its cap, however large that basin's own mass. A guard on a position that is
a declared bin but never becomes a surviving mode has no effect on anything.

## 4b. Linked guard groups

A `link <pos1> <pos2>` line joins the guarded modes at `<pos1>` and `<pos2>`
into one shared group. Link lines chain transitively: three or more guarded
positions can end up sharing a single group through a chain of pairwise links
even when no line names two of them directly. A guarded position never named
by any `link` line remains a solitary group of one. A group's shared lifetime
cap is the smallest of the individual `guard` caps declared for its members,
never their sum and never any one member's own number taken alone, and every
basin any member of the group absorbs in any round counts once against that
one shared total rather than against the receiving member's own count in
isolation. When the nearest eligible survivor is sought for a dissolved
basin, a candidate belonging to a group whose shared total has already
reached the group's shared cap is skipped in favor of the next nearest
eligible candidate, under the same distance-then-position rule as section 4a;
the same same-round exclusion and the same all-candidates-exhausted fallback
from section 4a still apply, now evaluated group-wide rather than per
position.

## 4c. Emergent majority saturation

Layered on top of everything above, and requested by no line in the input, is a
saturation latch that emerges from the consolidation itself. At the start of
every round, judged on the mass each surviving mode carries INTO that round
(that is, the masses standing at the moment the round's bar is computed, which
for the first round are the initial basin masses and for every later round are
the masses left by the previous round's absorptions), a surviving mode whose
basin mass is at least half the total mass — twice its basin mass is at least M
— is saturated. Saturation is a lifetime latch: once a mode is saturated it
stays saturated for that round and every later round of the run.

A saturated mode is barred from receiving a dissolved basin exactly as a guard
exhausted mode is: when the nearest surviving destination is sought, a saturated
candidate is skipped in favor of the next nearest eligible candidate under the
same distance-then-position rule, and a mode dissolving in the current round is
still never eligible regardless of anything. A candidate is eligible only when
it is a surviving mode that is not dissolving this round, not guard or group
exhausted per sections 4a and 4b, and not saturated. If every candidate that is
not dissolving this round is barred — whether by guard exhaustion, by
saturation, or by both — then for that one basin only both the guard bars and
the saturation bar are set aside and the plain nearest surviving mode places it
under the ordinary distance-then-position rule; the co-dissolving exclusion is
never set aside. A basin placed on a guarded mode still counts against that
mode's guard or group total whether it arrived by the ordinary rule or by this
fallback.

Because saturation is judged only on carried-in mass, a mode that reaches or
passes the half-mass line solely because of basins landing on it during the
current round is NOT saturated for that round; it still receives every basin
assigned to it in that round, and it latches saturated only at the start of the
following round. Saturation never changes which modes dissolve or how the bar is
computed; like a guard it only ever redirects where an already-dissolving
basin's mass ends up, though that redirection can change which basins fall under
the bar in later rounds. As a small illustration, imagine three surviving modes
carrying masses forty, three and twelve out of a total of fifty-five; the first
holds more than half and so latches saturated at the first round, and if the
basin of mass three later dissolves with that saturated mode as its nearest
survivor, the basin walks past it to the mode of mass twelve instead.

## 5. Worked example

Bins `b 0 5`, `b 1 20`, `b 2 5`, `b 10 4`, `b 11 9`, `b 12 4`, `b 16 2`,
`b 20 1`, `b 21 2`, defaults `h=2, q=4`. M = 52.

Climbs: positions 0 and 2 target 1, which targets itself — a mode with basin
mass 30. Positions 10 and 12 target 11, a mode with mass 17. Position 16 sees
only itself — a mode with mass 2. Position 20 targets 21, a mode with mass 3.
`raw_modes` is 4.

Round one: m = 4, T = floor(52/16) = 3. Basin 16 (mass 2) is strictly below;
basin 21 (mass 3) is not. Basin 16 dissolves; the nearest survivors to
position 16 are 11 and 21 at distance 5 each, so the tie goes to 11, whose
mass becomes 19. Round two: m = 3, T = floor(52/12) = 4. Basin 21 (mass 3) is
now strictly below. It dissolves into 11 (distance 10 beats 20), whose mass
becomes 22. Round three: m = 2, T = floor(52/8) = 6. Masses 30 and 22 both
reach the bar; nothing dissolves and the iteration stops. `rounds` is 2 and
`threshold_final` is 6. The mode at position 1 carries more than half the mass
throughout and so is saturated the whole way, but it is never the nearest
survivor to a dissolving basin, so section 4c stays inert here and the result is
unchanged by it.

## 5a. Guard note

Section 4a is the complete and binding statement of how a guard interacts
with the ordinary nearest-survivor rule from section 4: a guarded mode keeps
receiving basins normally until its lifetime cap is spent, a later
dissolution that would have reached an exhausted guard instead falls through
to the next nearest eligible survivor under the same distance-then-position
rule, and a basin with no eligible survivor left ungoverned has its guards
set aside so the ordinary rule can still place it. Nothing here changes
which modes survive a round or how the bar is computed; a guard only ever
redirects where an already-dissolving basin's mass ends up.

## 6. Output

On a schema-valid file the tool writes exactly one JSON object as a single
line to `/app/output/result.json`, prints the identical line to standard
output, and exits 0:

```
{"n":<int>,"total_mass":<int>,"raw_modes":<int>,"mode_count":<int>,"rounds":<int>,"threshold_final":<int>,"mode_positions":[<int>,...],"fractions":["<num>/<den>",...],"heaviest_mode":<int>,"concentration_pct":<int>,"gap_min":<int>,"gap_median":<int>,"gap_max":<int>,"raw_span":<int>}
```

- `n` — bin count. `total_mass` — M.
- `raw_modes` — the initial mode count, before any dissolution.
- `mode_count`, `rounds`, `threshold_final` — per sections 3 and 4.
- `mode_positions` — the surviving mode positions in ascending order.
- `fractions` — one string per surviving mode, in the same ascending order:
  the basin mass over M reduced to lowest terms, written `num/den` (a basin
  holding everything is `1/1`).
- `heaviest_mode` — the surviving mode with the greatest basin mass, ties
  resolved to the lower position.
- `concentration_pct` — the heaviest basin mass times 100, floor-divided
  by M.
- Gaps are the differences between consecutive surviving mode positions in
  ascending order. `gap_min` and `gap_max` are the smallest and largest;
  `gap_median` is the lower median (sort the gaps; with an odd count take the
  middle element, with an even count the lower of the two middle elements).
  With fewer than two surviving modes all three gap figures are 0.
- `raw_span` — the highest bin position minus the lowest bin position over
  ALL bins, dissolved or not — deliberately a raw figure.
- Key order exactly as shown; no spaces after `:` or `,`.

## 7. Exit codes

- 0 — profile written (status ok) or schema violation (malformed object).
- 1 — the data path cannot be read. Nothing written.
- 2 — wrong argument count (exactly one argument). Nothing written.
- 3 — parse failure per section 1. Nothing written.
