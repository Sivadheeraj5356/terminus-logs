Storage curves are continuous piecewise-linear maps between level and volume.

Forward: for adjacent knots (h0,V0) and (h1,V1) with h0 <= h <= h1,
V(h) = V0 + (h - h0) * (V1 - V0) / (h1 - h0). Knots return exact knot volumes.

Inverse: for V0 <= V <= V1,
h(V) = h0 + (V - V0) * (h1 - h0) / (V1 - V0). Knots return exact knot levels.

Do not extrapolate. Volumes outside the active curve invalidate the attempted step.

A storage-curve revision replaces the active curve at its event time. Stored volume is conserved; level is recomputed from the new curve. Revisions are never applied retroactively.
