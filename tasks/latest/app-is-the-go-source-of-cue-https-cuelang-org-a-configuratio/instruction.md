`/app` is the Go source of [CUE](https://cuelang.org), a configuration and
constraint language: it reads configuration source text, unifies the constraints
that text declares, and either produces an evaluated result or reports a
**conflict** when a value is required to be two incompatible things at once. It
builds offline:

```
cd /app && go build ./...
```

Make the evaluator in `/app` honour the following contract on the configurations
it processes.

A field that a definition fixes by reference, and that an inline struct then
overrides with a different concrete value, is contradictory, and such a
configuration must be reported as a conflict. In

```
#Base: 5
#fn: {x: #Base, y: x * 2}
r: (#fn & {x: 7}).y
```

`#fn.x` is constrained to `#Base` (which is `5`), while the unification
`#fn & {x: 7}` also requires `x` to be `7`. Since `5` and `7` cannot both hold,
evaluating this must fail with a conflict on `x`, exactly as a conflict on an
ordinary field is reported. As the engine stands, it instead evaluates the
configuration to a value for `r` and reports nothing, and it does the same for the
other shapes of this pattern: booleans, strings, or arithmetic derived from the
conflicting field, and references nested through several structs.

Configurations that are genuinely valid must go on evaluating without error. That
includes inline overrides that agree with the constraint, overrides that further
constrain an abstract field, and ordinary struct merges, list references, and deep
or abstract unifications. No other evaluation behaviour may change, and the public
API must stay as it is. The change this contract calls for is a small, targeted
one rather than a broad restructuring of the evaluator. Build with
`go build ./...`.
