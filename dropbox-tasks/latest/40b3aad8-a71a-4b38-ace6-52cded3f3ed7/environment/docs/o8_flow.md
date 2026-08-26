# Obligation eight witness synthesis (o8_flow)

Scientific-computing witness policy for annex slice 759: each graded walk instance `i` with composed label set `L_i` and rank map `R` derives an o8 score from upstream label ranks minus seed label ranks after fold.

Obligation eight passes when every graded instance in the bundled walk has a non-negative o8 score. A negative score is a fault.

## Label ranks

Label ids map to ranks through `(id mod 7) + 1`. Upstream mesh labels inherited through fold must dominate seed ranks under obligation eight.

## Class codes

| code | basis size |
|------|------------|
| 10   | 2          |
| 11   | 3          |
| 12   | 2          |

Basis rows are unique per `(instance_uid, class_code)` closure element. Duplicate basis keys are redundant.

## Lattice labels

Each emitted row carries a `lattice_label` string `L{profile}{dominant_arm}` where dominant arm is the MI-selected arm index after profile tie resolution.
