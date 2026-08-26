# fpfold grammar

A program is one arithmetic expression over double-precision values. Whitespace
between tokens is insignificant and there is no statement terminator.

```
expr   = term (("+" | "-") term)*
term   = factor (("*" | "/") factor)*
factor = "-" factor | atom
atom   = number | ident | "(" expr ")"
```

The binary operators `+` and `-` share one precedence level and `*` and `/`
share a higher level. All four are left associative, so `a - b - c` groups as
`(a - b) - c` and `a / b / c` groups as `(a / b) / c`. Unary minus binds tighter
than the binary operators, so `-a * b` is `(-a) * b`.

A number is a decimal literal with an optional fraction and an optional decimal
exponent, for example `0`, `2.0`, `.5`, `1e3`, or `6.022e23`. The two spellings
`inf` and `nan` denote positive infinity and a NaN. An identifier is a lower
case letter or underscore followed by letters, digits, or underscores, and names
a free variable whose value is unknown at fold time. `inf` and `nan` are
reserved and are never identifiers.

The tool prints the folded expression on one line. Numbers print in a canonical
form: `nan`, `inf`, and `-inf` for the non-finite values, `0.0` and `-0.0` for
the two zeros, and otherwise the shortest decimal that round-trips to the same
double. A variable prints as its name. Every binary application prints fully
parenthesized as `(left op right)` with single spaces, and a unary minus prints
as `-` immediately followed by its operand.
