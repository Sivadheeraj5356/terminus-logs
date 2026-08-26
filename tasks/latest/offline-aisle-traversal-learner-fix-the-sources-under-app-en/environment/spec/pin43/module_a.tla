---- MODULE pin43_a ----
\* Minimized annex predicates for zone-to-cell bonds.
EXTENDS Naturals

CONSTANTS Cells, Zones, Bonds

ActiveZone(z, obs) == \E o \in obs : o.zone = z
BondOk(b, visits, obs) ==
  \/ ~ActiveZone(b.from_zone, obs)
  \/ visits[b.to_ix] > 0

AllBondsOk(visits, obs) == \A b \in Bonds : BondOk(b, visits, obs)
====
