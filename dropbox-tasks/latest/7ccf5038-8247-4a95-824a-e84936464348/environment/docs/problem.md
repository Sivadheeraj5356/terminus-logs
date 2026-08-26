# Weighted Jacobi theta sum

The project at `/app/environment` evaluates, for each case, the single value

```
S = sum_{i=1}^{N} c_i * theta3(z_i, q_i),
```

where

```
theta3(z, q) = 1 + 2 * sum_{k>=1} q^(k^2) * cos(2 k z)
```

is the Jacobi theta function for a real angle `z` and a real nome `q` with
`0 <= q < 1`. Each case lists `N` terms; term `i` carries a coefficient `c_i`,
an angle `z_i`, and a nome `q_i`, all passed to `theta3` as the exact decimal
strings that appear in the input file.

See `format.md` for the exact input and output file formats.
