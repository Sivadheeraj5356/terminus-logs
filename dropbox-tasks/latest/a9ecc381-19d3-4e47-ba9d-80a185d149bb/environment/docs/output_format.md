# Output format

Solved with `minizinc --solver chuffed /app/model.mzn /app/instance.dzn`. Print
two lines:

```
x=[x_1, ..., x_L]
board=[b_1, ..., b_T]
```

`x` has `L` entries, the departure offset of each line (each in `0..H-1`).
`board` has `T` entries, one per row of the transfer list: `1` if that flow's
passengers ride that connection, `0` otherwise. `board` reports what the
passengers do once the offsets are set; it is not a second, free choice. Use

```
output ["x=", show(x), "\nboard=", show(board), "\n"];
```

Chuffed needs finite domains, so give every `var int` you declare an explicit
bound.

The grader reads only those two lines. It rebuilds the walk, the interval and
the earned weight from the raw instance itself, and requires the maximum. It
also independently checks that the plan is a legal one: that every pair of
co-terminus lines keeps the required spacing around the cycle, that the boarding
reported is the one those offsets really do leave the passengers making, and
that no bus is loaded past its seats. A plan that breaks any of those is
rejected however much weight it claims. Several plans may reach the maximum; any
of them is accepted. Re-solved on hidden instances, so hardcoding fails.
