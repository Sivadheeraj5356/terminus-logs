# File formats

## Case file (`data/thetas/<name>.txt`)

Whitespace-separated tokens:

1. The first token is the term count `N` (a positive integer).
2. Each of the next `N` lines holds three tokens `c_i z_i q_i`: the coefficient
   `c_i`, the angle `z_i`, and the nome `q_i`. `c_i`, `z_i`, and `q_i` are exact
   decimal literals passed to `theta3` verbatim as the strings that appear in the
   file. Every `q_i` satisfies `0 <= q_i < 1`.

A tiny 2-term example:

```
2
1.5 0.7 0.3
-2.25 1.4 0.5
```

## Manifest (`data/cases.csv`)

A CSV with a header row `name,case_path`. Each remaining row names one case and
gives its input file path relative to `/app/environment`.

## Output file (`outputs/<name>.txt`)

For each case, write one file named after the case containing a single line with
the value of the sum

```
S = sum_{i=1}^{N} c_i * theta3(z_i, q_i)
```

printed with `%.17g`.
