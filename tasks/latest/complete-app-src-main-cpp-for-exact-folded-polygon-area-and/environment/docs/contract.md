Produce the executable described below by completing the supplied source file.

Read n, then n integer vertices of a convex polygon in counterclockwise order, then integers a b c for fold line a*x + b*y = c with a and b not both zero. Let S be the polygon portion satisfying a*x + b*y <= c. Let F be the mirror image across the fold line of the portion satisfying a*x + b*y >= c. Points exactly on the fold line have zero area and do not change the result.

Print one line with six fields: visible_area double_covered_area visible_x_moment visible_y_moment double_x_moment double_y_moment. Visible quantities describe S union F, double quantities describe S intersection F, and moments are integrals of x and y over those regions. Print reduced rationals as p/q with positive denominator, or integers when denominator is one. A denominator-one value must be printed as its integer numerator; forms such as 69/1 are invalid. Use exact arithmetic only.

The fold line may miss the polygon, cross edges at rational points, or pass through vertices or along a supporting boundary. S and F are closed regions for set operations; shared boundaries have zero area and do not create spurious moment contributions. Union and intersection may contain coincident vertices or edges, and a zero-area double-covered region must still report numeric zero fields rather than changing the six-field schema. Coordinates after reflection can be rational and signed. Use sufficiently wide exact arithmetic, do not round or use epsilon geometry, and emit exactly six reduced values with no additional text.

## Stateful batch mode and audit cascade

The legacy single-instance input and output above remain valid. A second, graded mode is enabled when the first non-whitespace token is the literal `BATCH_178A9137`. In that mode the next token is an integer `T` with `2 <= T <= 16`, followed by exactly `T` complete legacy instances concatenated in their original input format. Process them in order without resetting the batch audit state. Emit the canonical legacy answer for each instance on its own line: the same base-10 integer or reduced-rational fields required above, separated by one ASCII space and with no leading or trailing spaces.

After those `T` answer lines, emit one final line `AUDIT_178A9137 H`, where `H` is the unsigned decimal value of this 64-bit FNV-1a recurrence. Start with `h = 15886462886245262841`. For every answer line in order, feed the ASCII bytes of that canonical line and then one line-feed byte (`0x0A`). For each byte `b`, set `h = ((h XOR b) * 1099511628211) modulo 2^64`. The state is continuous across all instances; it is not reset between lines. The final audit line itself is not hashed. Emit exactly `T + 1` nonblank lines in batch mode. This batch contract is part of the required observable behavior, not an example or implementation hint.

## Second-moment mode

A third graded mode is enabled when the first non-whitespace token is the literal `SECOND_178A9137`. It is followed by exactly one complete legacy instance. Print the six legacy fields, then six raw quadratic moment integrals: visible_x2_moment, visible_xy_moment, visible_y2_moment, double_x2_moment, double_xy_moment, and double_y2_moment. These moments are over the same exact union and intersection regions as legacy mode and use the same reduced-rational formatting.

## Batch second-moment mode

A fourth graded mode is enabled when the first non-whitespace token is the literal `BATCH_SECOND_178A9137`. In that mode the next token is an integer `T` with `2 <= T <= 16`, followed by exactly `T` complete legacy instances concatenated in their original input format. Process them in order without resetting the second-moment audit state. Emit the canonical `SECOND_178A9137` answer for each instance on its own line: the six legacy fields followed by the six raw quadratic moment fields, separated by one ASCII space and with no leading or trailing spaces.

After those `T` answer lines, emit one final line `SECOND_AUDIT_178A9137 H`, where `H` is the unsigned decimal value of this 64-bit FNV-1a recurrence. Start with `h = 7809847782465536327`. For every second-moment answer line in order, feed the ASCII bytes of that canonical line and then one line-feed byte (`0x0A`). For each byte `b`, set `h = ((h XOR b) * 1099511628211) modulo 2^64`. The state is continuous across all instances; it is not reset between lines. The final audit line itself is not hashed. Emit exactly `T + 1` nonblank lines in batch second-moment mode.

## Polygon trace mode

`POLY_TRACE_178A9137` is followed by exactly one complete legacy instance. First emit the same line as `SECOND_178A9137`. Then emit exact vertex rows for the kept polygon, reflected folded polygon, and double-covered overlap polygon in that order. Rows are `STAY index x y edge_cross`, `FOLD index x y edge_cross`, or `DOUBLE index x y edge_cross`, where `edge_cross` is the exact cross product of the vertex with the next vertex in the same polygon. During each half-plane clipping pass, process every directed subject edge p to q with this exact sequence rule: inside-to-inside appends q; inside-to-outside appends only the intersection; outside-to-inside appends the intersection followed by q; outside-to-outside appends nothing. Boundary points are inside. For each traced polygon, remove consecutive duplicate vertices, orient the polygon counterclockwise when it has positive area, and preserve the resulting sequence as index order. The first emitted vertex is that sequence's first vertex; do not rotate to a lexicographic or geometric canonical start. Coordinates and edge_cross use the same reduced-rational formatting rules.

After all polygon rows, emit `POLY_AUDIT_178A9137 H`. Start `H = 13679457532755275413` and apply the 64-bit FNV-1a recurrence to the canonical second-moment line and each canonical polygon row, each followed by one line-feed byte. The final audit line itself is not hashed.

