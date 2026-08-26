# Gap bound complementary slackness

## optimality_gap_bound

For each certified feasible solution, optimality_gap_bound certifies complementary slackness between primal slacks and dual shadow prices.

Tolerance TOL = 1e-6.

## Lot capacity slack

For each lot:

  slack = available_ml - amount_ml
  if slack > TOL and lot_dual > TOL: gap += slack * lot_dual

## Band slack

For each analyte with lower L, upper U, achieved concentration c:

  lower_slack = c - L
  upper_slack = U - c
  if lower_slack > TOL and analytes_lower[analyte] > TOL: gap += lower_slack * analytes_lower[analyte]
  if upper_slack > TOL and analytes_upper[analyte] > TOL: gap += upper_slack * analytes_upper[analyte]

## Output

optimality_gap_bound is the summed gap rounded to six decimal places. A correct dual certificate for an optimal grid solution should yield a gap bound near zero.
