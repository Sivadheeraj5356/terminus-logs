# Branch tracker

## The systems

Both problems discretise a two-point boundary-value problem on the interior
nodes `t_i = i*h`, `i = 1..N`, with `N = 15`, `h = 1/(N+1)`, and boundary
values `u_0 = u_{N+1} = 0`.

For a parameter `lambda`, the residual at node `i` is

```
R_i(u, lambda) = (u_{i-1} - 2*u_i + u_{i+1}) / h^2 + lambda * g(u_i)
```

and a point `(u, lambda)` in `R^{N+1}` is a solution when `R_i = 0` for every
`i = 1..N`. The two problems differ only in `g`:

| `problem` | `g(v)`    |
|-----------|-----------|
| `bratu`   | `exp(v)`  |
| `cubic`   | `v - v^3` |

## The traced segment

Arclength `s` is measured along the traced segment from its start point,
using the Euclidean norm on the full vector `(u_1, ..., u_N, lambda)`.

**`bratu`.** `u = 0` is a solution only at `lambda = 0`. The traced segment
starts at `(u = 0, lambda = 0)` and follows the solution curve through that
point in the direction of increasing `lambda`. The contract's `k` is `0` and
carries no meaning here.

**`cubic`.** `u = 0` is a solution for every `lambda`; call this the trivial
branch. There are finitely many `lambda > 0` at which other solution branches
of the system meet the trivial branch. Numbering those values in increasing
order as `lambda_1 < lambda_2 < ...`, the contract's `k >= 1` selects
`lambda_k`. The traced segment starts at `(u = 0, lambda_k)` and follows the
branch that meets the trivial branch there — not the trivial branch itself —
leaving that start point in the direction whose `u_1` component is positive.

In both cases `s = 0` denotes the start point itself, and the requested
arclengths are given in increasing order.

See `format.md` for the input and output file formats.
