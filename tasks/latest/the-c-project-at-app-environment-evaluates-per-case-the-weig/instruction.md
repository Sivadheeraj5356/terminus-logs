The C project at /app/environment evaluates, per case, the weighted sum

    S = sum_i c_i * erf(x_i)

where erf is the error function. Each term gives a coefficient c_i and argument x_i
as decimal strings carrying far more digits than a double holds, and every argument
satisfies the absolute value of x_i being at most 6. The terms cancel so heavily that
S is tiny.

The kernel in /app/environment/src/erfsum.c reads and accumulates in double, which is
not accurate enough here.

Implement erfsum_weighted_sum in /app/environment/src/erfsum.c so S is accurate on
every case. Leave the declaration in /app/environment/include/erfsum.h unchanged; the
result is returned through out.

Running /app/environment/scripts/run_all.sh must build the program and, for every case
in /app/environment/data/cases.csv, write /app/environment/outputs/<name>.txt with that
case's S. Formats are in /app/environment/docs/format.md.

Solve it from scratch in C. Do not shell out to another language or process. Use only
ordinary double; long double, __float128, _Float128, __float80, and inline assembly are
all off-limits, as is any external extended-precision, arbitrary-precision, or
special-function library. The standard math library (sqrt, frexp, ldexp) is available;
the shipped source is scanned for such types, calls, includes, and links. The same
binary is rerun on held-back cases that cancel far more deeply; do not special-case
names or hardcode results.

Each value is graded against an independent high-accuracy reference, accepted when
finite and within relative tolerance 1e-9.
