# Data dictionary

`/app/instance.dzn` defines:

- `L` (int): number of bus lines, `1..L`.
- `H` (int): the common headway; every line repeats every `H` minutes.
- `MINW` (int): the smallest interval that still counts as comfortable.
- `MAXW` (int): the largest interval that counts as comfortable.
- `T` (int): number of rows in the transfer list, `1..T`.
- `F` (int): number of passenger flows, `1..F`.
- `P` (int): number of platforms in the interchange concourse, `1..P`.
- `arr` (`array[1..L] of int`): `arr[l]` is how far into its run line `l` reaches
  the interchange.
- `ap` (`array[1..L] of int`): `ap[l]` is the platform line `l` arrives at.
- `dep` (`array[1..L] of int`): `dep[l]` is how far into its run line `l` leaves
  the interchange again.
- `dp` (`array[1..L] of int`): `dp[l]` is the platform line `l` leaves from.
- `seats` (`array[1..L] of int`): `seats[l]` is the number of transferring
  passengers line `l` can lift out of the interchange on its departure.
- `terminus` (`array[1..L] of int`): `terminus[l]` identifies which physical
  terminus line `l` sets out from. Lines with the same `terminus[l]` value share
  a terminus.
- `GAP` (int): the minimum number of minutes required between any two departures
  from the same terminus.
- `fline` (`array[1..T] of int`): `fline[t]` is the feeder line of row `t`.
- `cline` (`array[1..T] of int`): `cline[t]` is the connecting line of row `t`.
- `flow` (`array[1..T] of int`): `flow[t]` is the passenger flow row `t` serves.
  Rows carrying the same value are alternative connections offered to that one
  flow.
- `w` (`array[1..T] of int`): `w[t]` is the weight of the flow that row `t`
  serves, in people. Every row of a flow repeats that flow's weight.
- `WK` (`array[1..P, 1..P] of int`): `WK[p, q]` is the time of the passage that
  runs directly between platforms `p` and `q`. The diagonal is zero.
