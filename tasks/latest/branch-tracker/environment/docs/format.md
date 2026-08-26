# File formats

## Contract file (`data/contracts/<name>.txt`)

A single whitespace-separated line:

```
problem k m s1 s2 ... sm
```

- `problem`: `bratu` or `cubic`.
- `k`: branch selector, as described in `problem.md`.
- `m`: the number of requested arclengths.
- `s1 .. sm`: the requested arclengths, increasing, each `>= 0`.

## Manifest (`data/cases.csv`)

A CSV with header row `name,contract_path`. Each remaining row names one case
and gives the path of its contract file (relative to `/app/environment`).

## Output file (`outputs/<name>.txt`)

For each case, write one file named after the case, with `m` lines, one per
requested arclength in the order given. Line `j` holds the index `j`, then
`lambda`, then `u_1 .. u_N` at arclength `sj`, with `%.17g` for every value
after the index:

```
<j> <lambda> <u_1> <u_2> ... <u_N>
```
