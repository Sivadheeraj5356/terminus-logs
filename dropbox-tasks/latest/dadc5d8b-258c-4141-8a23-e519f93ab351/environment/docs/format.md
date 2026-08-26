# File formats

## Case file (`data/cases/<name>.txt`)

Whitespace-separated values:

1. The first value is the term count `N` (a positive integer).
2. Each of the next `N` lines holds two fields, the coefficient `c_i` and the
   argument `x_i` of term `i`, separated by whitespace.

Both `c_i` and `x_i` are plain decimal literals: an optional leading sign, then
digits with at most one decimal point (no exponent notation). They may carry many
more significant digits than a `double` can hold. Every argument satisfies
`|x_i| <= 6`.

A tiny 2-term example:

```
2
1.5 0.75
-0.5 6.25
```

## Manifest (`data/cases.csv`)

A CSV with a header row `name,input_path`. Each remaining row names one case and
gives its input file path relative to `/app/environment`.

## Output file (`outputs/<name>.txt`)

For each case, write one file named after the case containing a single line with
the value of the sum

```
S = sum_{i=1}^{N} c_i * erf(x_i)
```

printed with `%.17g`.
