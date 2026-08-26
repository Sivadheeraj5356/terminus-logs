# Harmonic source-recovery campaign

The campaign represents a pointing-axis disturbance survey. Several physical injection
points can excite the same measured probe, and an analog tone can fold onto a different
sampled bin in each acquisition. A source line is therefore identified by the pair
`(tone_id, source_id)`, not by a sampled bin alone.

`/app/plant_lab/campaign.json` names the allowed sources and probes and gives
`max_active_sources`, a JSON integer from zero through the size of the tone/source
Cartesian product, inclusive. `/app/plant_lab/sources.json` supplies operator-facing
descriptions; descriptions do not affect recovery. One file per candidate line appears
under `/app/plant_lab/tones/`, one calibrated path per source/probe pair under
`/app/plant_lab/paths/`, and one acquisition under `/app/plant_lab/captures/`.

Each capture records two phasors at every retained bin:

- `expected` is the projected response of the commanded motion, including finite-window
  leakage from the intended ramp or other commanded component.
- `measured` is the actual projected response.

Only `measured - expected` is attributable to the candidate disturbance sources. Both
coordinates are exact fractions. A source set is acceptable only when it reproduces
every retained coordinate exactly, including coordinates whose residual is zero.

All identifiers are case-sensitive ASCII strings matching
`[A-Za-z0-9][A-Za-z0-9._-]*`. The `sources` and `probes` lists are nonempty.
Every tone `omega` and capture `sample_rate` is a positive JSON integer no greater
than 1,000,000. Directory iteration order has no meaning. Duplicate identifiers,
missing calibrated paths, missing probe rows, duplicate bins, or a bin sequence other
than every integer from zero through `floor(sample_rate / 2)` make the campaign invalid.
