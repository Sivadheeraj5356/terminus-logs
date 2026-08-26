Complete /app/src/main.cpp for exact folded-polygon area and moments.

Legacy input is n, n counterclockwise integer vertices, then a b c defining a*x+b*y=c. S is the closed a*x+b*y<=c portion; F is the reflection of the a*x+b*y>=c portion. Output visible_area, double_covered_area, visible_x_moment, visible_y_moment, double_x_moment, and double_y_moment, where visible is S union F and double is S intersection F. Values are reduced rationals with positive denominators. Denominator one must be emitted as an integer; p/1 is invalid. Zero-area double regions still use six numeric fields.

BATCH_178A9137 emits T answers then AUDIT_178A9137 H. SECOND_178A9137 adds visible and double raw x2, xy, and y2 moments. BATCH_SECOND_178A9137 ends with SECOND_AUDIT_178A9137 H. POLY_TRACE_178A9137 emits STAY, FOLD, and DOUBLE vertex rows with edge_cross values, then POLY_AUDIT_178A9137 H.

For every directed clipping edge p to q, inside-to-inside appends q; inside-to-outside appends the intersection; outside-to-inside appends the intersection then q; outside-to-outside appends nothing. Consecutive duplicates are removed, positive-area traces are oriented counterclockwise, and the resulting start vertex is not rotated.

All geometry must be exact for missed, crossing, tangent, and supporting fold lines. Fixed outputs, floating point, epsilon comparisons, verifier artifacts, and network access are invalid.
