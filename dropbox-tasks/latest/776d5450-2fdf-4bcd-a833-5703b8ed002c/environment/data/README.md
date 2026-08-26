# switch-binning data dictionary

This directory holds one release slate of forty candidate IGBT die designs (`ig-01` through
`ig-40`) at a power-semiconductor line. A design is signed off when a built die passes the full
acceptance: it holds off its rated collector-emitter voltage in the blocking state, sits inside
the on-state saturation window, and rides out a short-circuit pulse without latching. A die that
punches through, runs its conduction drop out of window, or latches under the fault is scrapped.
The share that comes off accepted is fixed per design as a rate `p`, so building `n` independent
dies signs a design off with chance `1 - (1 - p)^n`.

Files:

- `designs.csv` (one row per design): `design_id`, then `gate_grade`, then the two per-die test
  prices `probe_cost` and `lab_cost`. `gate_grade` is a wafer-level parametric-monitor reading of
  how well the design centred in fab, and a higher reading goes with a higher acceptance rate.
- `test_log.csv` (one row per die built to date): `design_id` and a `passed` flag, 1 where the die
  cleared the full acceptance and 0 where it was scrapped. The row count per design is far from
  even, running from heavily sampled designs down to ones with a single row or nothing but scraps.
- `release_rule.json` (the fixed rule set): `reference_gate` (a baseline gate_grade), the
  `rate_min`/`rate_max` bracket any adopted rate stays inside, the `signoff_floor`, and the
  `probe_capacity`.

Cost turns only on where a die is tested, never on whether it comes off accepted, since both routes
run the identical acceptance sequence. In-house dies are billed at `probe_cost` but draw on one
`probe_capacity` allotment shared across the whole slate; once a design has used its portion of that
allotment, its remaining dies bill at the outside test house's uncapped `lab_cost`. A design's bill
is its in-house dies times `probe_cost` plus its outside dies times `lab_cost`, and the forty bills
summed must stay within a fixed spend ceiling whose value is not given here.
