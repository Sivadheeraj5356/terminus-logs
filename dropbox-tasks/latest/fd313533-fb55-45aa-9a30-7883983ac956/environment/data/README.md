# wick-proving inputs

The season's run turns on forty candle designs, `cd-01` through `cd-40`, and the three files here
lay each of them out. A design fixes a recipe: a wax base, the wick drawn through it, the load of
fragrance and dye, all set so a finished candle burns down to a full even melt pool with no
tunnelling, no sooting, no drowned wick. Pour a candle to the recipe, set it on the burn bench, and
it either comes back clean or it faults. Two candles off one recipe need not agree: the wick seats a
little off centre, the wax sets with its own grain, the scent throws unevenly, and any of that can
turn one burn where the last was fine. So a design owns a per-candle clean-burn rate `p` you cannot
read off directly, and across `n` candles the recipe first burns clean with probability
`1 - (1 - p)^n`.

Columns in `designs.csv`, one row to a design under `design_id`: `blend_grade`, then `cost_line`
and `cost_shop`. Read `blend_grade` as the melt-bench take on the recipe this season, the refinement
and oil binding of the wax-and-additive blend graded as it is worked up; treat it as a lean, not a
guarantee, a higher grade sitting with a higher clean-burn rate. The two figures beside it are what a
candle costs to pour and burn down each way.

`burn_log.csv` holds the burns already on record: a `design_id` and a `burns_clean` flag per candle,
1 for a clean melt pool and 0 for a faulted burn. How much sits behind a design swings wildly. Some
carry scores of logged burns; others rest on a single candle, or on a short row of faults with no
clean burn entered against them yet.

`run_program.json` carries the rule set: `burn_floor`, the mark every design has to reach;
`reference_blend_grade`, the baseline a design's `blend_grade` is measured from; `rate_min` and
`rate_max`, the bracket any clean-burn rate you adopt has to stay inside; `line_capacity`, the ceiling
on the cheap route; and `cost_ceiling`, the cap on the whole spend.

A design proves out on either of two routes, and only price and headroom tell them apart. The
in-house pouring line runs cheaper a candle but shares one pool: `line_capacity` candles are all it
will take across the forty designs together, so once a design spends its share of that pool the rest
of its candles go to an outside chandler that pours any number at `cost_shop` each. That chandler
works the same recipe to the same burn bench, so a design's clean-burn rate holds wherever the candle
is poured, and what the outside buys you is throughput, not a kinder burn. Sum `cost_line` over a
design's in-house candles and `cost_shop` over the rest, total that across all forty, and that figure
is the one `cost_ceiling` keeps down.
