# Input and output

The program takes one command line argument, the path to an input file, and
writes its answers to standard output.

## Input

The first token is an integer, the number of problems. Each problem is, in order:

1. the degree bound `N`, a positive integer: the unknown polynomial has `N`
   coefficients, that is degree below `N`;
2. the condition count `C`, a nonnegative integer;
3. `C` conditions, each three integers `x j v`, meaning the `j`-th derivative of
   the polynomial at the point `x` equals `v`. The zeroth derivative is the value
   itself.

All of `x`, `j` and `v` are integers. Derivative orders need not be contiguous:
a point may carry order `0` and order `2` with no order `1`, may carry a pure
derivative with no value at all, and the same pair `x j` may appear more than
once. The number of conditions may be less than, equal to, or greater than `N`.

## Output

One block per problem, in input order, with nothing else between or around them.
Every rational value below is written as `numerator/denominator` in lowest terms
with a positive denominator; an integer uses denominator one, so a zero is `0/1`.

- If exactly one polynomial with `N` coefficients meets every condition, the block
  is two lines: the first is `N`, and the second is the `N` coefficients from the
  constant term up to the coefficient of `x` to the `N-1`, separated by single
  spaces.
- If no polynomial with `N` coefficients meets every condition, the block is two
  lines: the first is the word `NONE`, and the second is `C` values, one per
  condition in input order. Weighting each condition's row by its value and adding
  gives zero in every one of the `N` coefficient positions, while weighting each
  condition's target `v` the same way and adding gives a nonzero total; this is a
  proof that no polynomial can meet the conditions.
- If more than one polynomial with `N` coefficients meets every condition, the
  block is three lines: the first is the word `MANY`, and the next two lines each
  give `N` coefficients, describing two different polynomials that each meet every
  condition.
