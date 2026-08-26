# Polynomial reconstruction

A numerical computation in exact linear algebra: the reconstruction of a
univariate polynomial from a scheme of derivative conditions. Each problem fixes
a degree bound and a list of conditions, each pinning the value of some
derivative of the polynomial at a point, with the derivative orders allowed to
skip and repeat freely. For each problem the computation decides whether exactly
one polynomial below the degree bound meets every condition, none does, or more
than one does, and reports the coefficients or the supporting evidence
accordingly.

`docs/io_contract.md` gives the layout of a problem and of an answer,
`docs/running.md` the build, and `docs/allowed_libraries.md` what is available.
Worked numbers live under `data/` and `examples/`.
