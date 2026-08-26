# Problem: synchronising a periodic transit timetable

`L` bus lines all run at a single common headway `H`: each line repeats every `H`
minutes. The only decision for line `l` is its departure offset `x[l]`, an
integer in `0..H-1`; from then on it departs at `x[l]`, `x[l] + H`, `x[l] + 2H`,
and so on. Choose those offsets.

Every line calls at one interchange, a concourse of `P` platforms. Line `l`
reaches the interchange `arr[l]` minutes after it sets out and sets its
passengers down at platform `ap[l]`; later in the same run it pulls out again
from platform `dp[l]`, `dep[l]` minutes after it set out. Within one period,
then, line `l` lands at minute `x[l] + arr[l]` and leaves at minute
`x[l] + dep[l]`.

Each row `t` of the transfer list is a body of passengers off the feeder line
`fline[t]` who want the connecting line `cline[t]`.

## Crossing the concourse

Arriving passengers do not appear at the connector's platform instantly. They
have to cross the concourse on foot, and the time that walk costs them is
deducted from the time they have to make their connection. `WK` is the
interchange's passage map: `WK[p, q]` is the time of the passage that runs
*directly* between platforms `p` and `q`. The concourse was extended piecemeal
over the decades and was never planned as a whole, so a direct passage is not
much of a guide to how far apart two platforms really are.

Nothing about the building confines a passenger to one passage. The platforms
open onto one another, so a passenger going from one platform to another may
walk any chain of passages that joins them, spending the time of each passage in
the chain. Somebody with a bus to catch is not going to dawdle: the walk charged
between two platforms is the least total time of any chain of passages that
joins them.

## A comfortable connection

A connection is worth something only if the connector pulls out a comfortable
interval after its passengers have reached its platform: not less than `MINW`
minutes, and not more than `MAXW`. Measure that interval **around the cycle**.
Both events repeat every `H` minutes, so the connector's clock minute can fall
before, at, or after the moment the passengers get to its platform; either way
the interval is the number of minutes forward from their arrival to that
connector's next departure, always a value in `0..H-1`. A connector whose clock
minute is earlier is not missed, it is simply the one caught on the next turn of
the cycle.

## Boarding

The transfer list is grouped into `F` passenger flows; `flow[t]` says which flow
row `t` belongs to, and `w[t]` is that flow's weight, the number of people in
it. A flow appearing in several rows is one body of passengers who have been
offered a choice of connecting lines. They travel together and they ride one
bus.

Nobody is dispatching these passengers. They are people standing on a platform
with somewhere to be, and they get on the first bus they can catch: of the
connections open to them, they ride one that pulls out as soon as any of them
does. The authority cannot wave a body of passengers onto a later bus because it
would rather keep the earlier one free, and it cannot ask them to stand and wait
while a heavier crowd goes first. If two of their connections pull out at the
same moment they will take either one. So who boards what is not the authority's
to choose: it follows from the offsets, and the offsets are the only thing the
authority actually decides.

A bus is not infinitely large. `seats[l]` is the number of transferring
passengers line `l` can lift out of the interchange on its departure, and
everybody who boards it, from every flow that chose it, has to be carried away
on that one bus. A departure that the passengers overload is not a schedule the
authority can run at all. Since it cannot tell them to stay behind, the only way
to keep a crowd off a bus is to leave them no comfortable connection to it.
A flow with no comfortable connection is left behind, and its weight is not
earned.

## The schedule

Some lines set out from the same physical terminus building; `terminus[l]`
records which one. Two lines sharing a terminus cannot both use the departure
bay at once, so their offsets must be kept at least `GAP` minutes apart. This
spacing is required, not optional: an assignment that places two co-terminus
lines too close together is not a valid schedule, no matter how much passenger
weight it earns. Like the interval above, the required spacing is measured
around the cycle rather than as a straight-line difference of clock minutes: a
line departing near the very end of the period and another departing near the
very start of the next one are close together in real time.

Choose the offsets so that the total weight of the passenger flows actually
carried away is as large as possible, and report the boarding they produce.
