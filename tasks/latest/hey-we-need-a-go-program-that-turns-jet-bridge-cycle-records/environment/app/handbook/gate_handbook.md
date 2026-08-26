gate zones and their meanings

four zones operate at this airport. each zone has its own monthly cap on billable cents and its own off hours uplift expressed in basis points. the canonical record is feebook/gate_zones.json.

A_NORTH covers gates A1 through A18, mostly narrow body domestic. its cap is the lowest because the apron management contract limits monthly billable to that zone.

B_MAIN covers the central concourse and is widely used by wide body international turns. its uplift is the smallest because off hours traffic on B_MAIN is normal rather than exceptional.

C_REGIONAL covers regional jet stands C1 through C9. the uplift is the largest in the airport because off hours regional ops require additional ramp staffing.

D_SOUTH covers the south satellite and includes both narrow body and wide body work. it sits between A_NORTH and B_MAIN on every dial.

a gate_zone code that does not appear in gate_zones.json should never occur in clean input. if you see one, treat it as data that cannot be priced and emit no billing for that cycle.
