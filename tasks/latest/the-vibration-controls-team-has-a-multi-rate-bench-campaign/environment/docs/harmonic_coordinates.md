# Harmonic coordinates and exact numbers

## Reduced fractions

Every physical scalar is an object with exactly the string fields `n` and `d`. The
represented number is `n / d`. The denominator is strictly positive, the numerator and
denominator have no common factor, and zero is always `{"n":"0","d":"1"}`. Integers in
this chapter are mathematical integers; fields explicitly described as counters remain
JSON integers rather than fraction objects.

Arithmetic is exact. Decimal approximations, tolerance comparisons, and floating-point
rounding are outside the campaign contract.

## Coordinate convention

A line of angular rate `omega` has source motion

`x(t) = c cos(omega t) + s sin(omega t)`.

Its stored coordinates are the pair `(c, s)`. If a calibrated path at that rate is
`H(j omega) = h_r + j h_i`, the output coordinates before sampling are exactly

`out_cos = h_r c + h_i s`

`out_sin = h_r s - h_i c`.

This sign convention is normative. It corresponds to the complex coefficient
`c - j s`; no phase-angle conversion is used.

## Trigger phase

Capture field `trigger_quarters` is an integer time shift measured in quarter turns at
unit angular rate. For a tone with integer `omega`, let
`q = (omega * trigger_quarters) mod 4`, using a non-negative remainder. Before the path
response, replace `(c, s)` as follows:

| q | rotated `(c, s)` |
|---|---|
| 0 | `(c, s)` |
| 1 | `(s, -c)` |
| 2 | `(-c, -s)` |
| 3 | `(-s, c)` |

The trigger rotation precedes the sensitivity-path transformation.
