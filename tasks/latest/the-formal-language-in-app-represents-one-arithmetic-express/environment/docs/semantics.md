# fpfold semantics

The tool is a constant folder. It reads one expression, rewrites it into an
equivalent but smaller expression, and prints the result. The guiding rule is
exactness: for every assignment of double values to the free variables, the
folded expression must evaluate to exactly the same double as the original,
bit for bit.

## Numeric model

All arithmetic is IEEE-754 double precision with round-to-nearest-even. There
are no traps and no errors from arithmetic. Dividing by zero yields a signed
infinity or a NaN, overflow yields a signed infinity, and the invalid cases such
as `inf - inf` or `inf * 0` yield NaN. The two signed zeros and the non-finite
values all follow IEEE-754, and a NaN result prints as `nan`.

## Constant folding

Evaluation proceeds from the leaves upward. Any subexpression whose operands are
all numeric constants is replaced by the single constant it evaluates to under
the numeric model above, so `2 * 3 + 1` becomes `7.0` and `1 / 0` becomes `inf`.
A unary minus applied to a constant is the negated constant. Folding is applied
until no constant subexpression remains, so a constant produced by one fold can
feed the fold above it.

## Simplification

Beyond evaluating constants, the folder removes an operand that does not affect
the result. An operand of a `+`, `-`, `*`, or `/` may be dropped, leaving just
the other operand, only when doing so yields an expression equal to the original
for every possible double value of the surviving variables. A double negation is
removed. Those are the only rewrites the folder performs. It evaluates a
constant subexpression, it drops an operand that cannot change the result, and
it removes a double negation, and it makes no other change to the expression.

## Output

The printed expression is the fully reduced form under the two rules above, in
the canonical syntax from the grammar. It contains no constant subexpression and
no removable operand, and it agrees with the input on every assignment of its
variables.
