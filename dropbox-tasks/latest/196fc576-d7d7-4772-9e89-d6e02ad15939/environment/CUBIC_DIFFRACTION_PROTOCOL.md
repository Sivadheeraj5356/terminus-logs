# Cubic diffraction indexing protocol

This file is the complete normative contract for version 1 of the cubic diffraction study.

The command is `/app/bin/cubic-index --study STUDY_PATH --output OUTPUT_PATH`. Both paths must be absolute, distinct, and must not contain `..` path components. The program exits 64 for command-line errors, 65 for unsafe paths, 66 for malformed studies, 74 for output failures, and 0 after publishing a valid `ok` or `infeasible` certificate. Diagnostics are one line on stderr: `usage`, `unsafe_path`, `study:<physical-line>:<code>`, or `output_error`.

Input is UTF-8 text with LF or CRLF endings. Blank lines are ignored. Records are whitespace-separated and must appear in this order:

`VERSION 1`

`HMAX h` where `1 <= h <= 12`.

`SCAN_RANGE lo hi` where `0 <= lo < hi <= 1000000`.

`SCALE min max drift` where `1 <= min <= max <= 1000`, `max-min <= 30`, and `0 <= drift <= 30`.

`SHIFT min max` where `-1000 <= min <= max <= 1000` and `max-min <= 20`.

`LIMITS max_impurities max_missing min_consensus` where each value is between 0 and 8.

`PHASES` followed by one to three distinct phase names chosen from `P`, `I`, and `F`.

Exactly two scan blocks follow. A block begins `SCAN name`, contains one to eight `PEAK id q tolerance weight` records, and ends with `END`. Names and identifiers match `[A-Za-z][A-Za-z0-9_-]{0,31}` and are unique. Peaks in a scan must have strictly increasing `q`. Values satisfy `0 <= q <= 1000000`, `0 <= tolerance <= 1000`, and `1 <= weight <= 1000`. No records may follow the second `END`.

Validation reports the first physical line with one of: `UNKNOWN_RECORD`, `BAD_ARITY`, `BAD_NUMBER`, `BAD_ORDER`, `BAD_VALUE`, `DUPLICATE`, `TOO_MANY_PEAKS`, or `UNEXPECTED_EOF`. Unknown record and arity checks precede number conversion, which precedes value and ordering checks.

For every integer triple `h >= k >= l >= 0`, not all zero, with `h <= HMAX`, define shell `n = h*h + k*k + l*l`. Phase P allows every triple. Phase I allows triples where `h+k+l` is even. Phase F allows triples where `h`, `k`, and `l` are all even or all odd. A phase shell is a distinct allowed `n`; its reported representative is the lexicographically smallest allowed `(h,k,l)` for that `n`.

A plan chooses one listed phase, integer scales `a0,a1` in the declared scale range, and integer shifts `z0,z1` in the declared shift range, with `abs(a1-a0) <= drift`. In each scan every peak is either assigned to one distinct phase shell or marked as an impurity. An assignment to shell `n` is legal when `abs(q - (a*n+z)) <= tolerance`. Shell assignments must increase with peak order. The number of impurities in each scan may not exceed `max_impurities`.

A phase shell is observable in a scan when its predicted position `a*n+z` lies inside the inclusive scan range. If a scan has assigned shells, its missing shells are the observable shells strictly between its smallest and largest assigned shell that are not assigned. The missing count in each scan may not exceed `max_missing`. A consensus shell is assigned in both scans. The consensus count must be at least `min_consensus`.

For a feasible plan compute, in this order: indexed weight (sum of weights of assigned peaks, maximize), consensus count (maximize), total residual (sum of absolute assignment residuals, minimize), total missing count (minimize), orphan count (number of assignments whose shell is not a consensus shell, minimize), and calibration motion `abs(a1-a0)+abs(z1-z0)` (minimize). Plans tied on all six numeric objectives are all optimal. `optimal_count` is their count modulo 1000000007. The canonical optimal plan is the lexicographically smallest tuple: phase rank `P<I<F`, `a0,z0,a1,z1`, then the two assignment vectors in scan order and peak order, using shell 0 for an impurity.

The compact JSON output has exactly this key order. For a feasible study:

`{"status":"ok","phase":"P","calibration":[{"scan":"s0","scale":1,"shift":0},{"scan":"s1","scale":1,"shift":0}],"objective":{"indexed_weight":0,"consensus":0,"residual":0,"missing":0,"orphans":0,"motion":0},"optimal_count":1,"scans":[...],"digest":"..."}`

Each scan object has keys `name`, `assignments`, `impurities`, and `missing_shells`. Each assignment has keys `peak`, `shell`, `hkl`, `predicted`, and `residual`. Assignments follow input peak order but include only indexed peaks. Impurity identifiers follow input order. Missing shells are increasing integers. For an infeasible study, output `{"status":"infeasible","optimal_count":0,"digest":"..."}`. The digest is lowercase SHA-256 of the compact JSON bytes before adding the `digest` field. The file ends with one newline.

Publication is atomic. On any error an existing destination is unchanged and no staging file remains. A successful write replaces a regular destination but must fail with `output_error` for a symlink destination.
