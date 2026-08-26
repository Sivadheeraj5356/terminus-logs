# Line-shape engine: request format and value definition

The engine evaluates the Faddeeva function for each request. This file defines
the value, the request format, the argument ranges, the output format, and how
a value is graded. It does not describe how to compute anything.

## Value

For a complex argument `z = x + i*y` the Faddeeva function is

    w(z) = exp(-z^2) * erfc(-i * z)

where `erfc` is the complementary error function, `erfc(u) = 1 - erf(u)`, and
`erf` is the usual error function extended to complex argument. The function is
entire; this definition holds everywhere in the plane. The real part of `w` is
the absorption line shape and the imaginary part is the dispersion.

Requests come from both half-planes. Above the real axis `w` is bounded. Below
it `w` grows like `exp(y^2 - x^2)`, which at the range limits is far past what
any floating-point type can hold, so values are reported in log form as defined
under Output.

## Requests

A request batch is JSON Lines: one JSON object per line, giving the real and
imaginary parts of the argument.

    {"x": <number>, "y": <number>}

Ranges: `-3e7 <= x <= 3e7` and `-3e7 <= y <= 3e7`. The batch path is passed as
the single command-line argument. Lines are independent and may appear in any
order.

## Output

Print one line per request, in the same order as the input. Each line holds two
numbers separated by a single space, and nothing else:

    L PHI

where `L = ln|w(z)|` is the natural logarithm of the modulus and `PHI` is the
principal argument of `w(z)` in radians, in the interval `(-pi, pi]`.

Any spelling of each number that a standard decimal parser reads back is
accepted (plain decimal or exponential). `L` is graded against an absolute bar
(see Grading) while its magnitude reaches about `9e14`, so at the large end it
needs on the order of 24 significant digits to be worth printing; a number that
size carries more information than one double holds, and the grader parses it
at full decimal precision. `PHI` never needs more than double precision to
print.

## Grading

Each printed pair is compared against a reference computed at high precision.
A line is accepted when both parts pass:

    |L - L_ref| <= 5e-9
    dist(PHI, PHI_ref) <= 5e-9

where `dist` is distance on the circle, `min(|d|, 2*pi - |d|)` for
`d = PHI - PHI_ref`, so the branch point at pi is not a trap. Both bars are
absolute. A non-finite part (NaN or infinity) is never accepted.

Be aware of what the absolute bar on `L` means at the top of the range: `5e-9`
sits far below the spacing of double-precision numbers near `9e14`, which is
about `0.1`. Values are checked on batches drawn from the ranges above,
including points that are not in the sample batch. Batches can be large and
each batch is processed under a fixed wall-clock budget.
