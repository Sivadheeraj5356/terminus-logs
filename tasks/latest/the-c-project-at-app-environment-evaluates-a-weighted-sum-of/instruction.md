The C project at /app/environment evaluates a weighted sum of Jacobi theta
values. Each case gives N terms; term i has a coefficient c_i, an angle z_i, and
a nome q_i, and the reported quantity is

    S = sum_{i=1}^{N} c_i * theta3(z_i, q_i),

where theta3(z, q) = 1 + 2 * sum_{k>=1} q^(k^2) * cos(2 k z), with 0 <= q < 1.
Input and output formats are in /app/environment/docs.

Two obstacles occur together. First, coefficients reach theta3 as decimal
strings with far more digits than a double holds (up to several hundred
significant digits); within a case the signed terms nearly cancel, so the
largest term can exceed |S| by ~650 orders of magnitude, and the held-back cases
cancel more deeply than the visible ones. Second, q ranges from near zero up to
values extremely close to 1; as q approaches 1 the series above needs
astronomically many terms to converge, so summing it term by term is intractable
and theta3 must instead be obtained accurately for every q. Size the internal
working precision to the worst case, not the public inputs.

Reimplement theta3 in /app/environment/src/theta.c so S is accurate on every
case, leaving /app/environment/include/theta.h unchanged. Running
/app/environment/scripts/run_all.sh must build and write outputs/<name>.txt for
every case in /app/environment/data/cases.csv, printed with %.17g.

Solve from scratch in C: no shelling out, no external multiple-precision or
special-function library, and no built-in type wider than double. Each value is
graded against an independent reference, accepted when finite and within
relative tolerance 1e-9.
