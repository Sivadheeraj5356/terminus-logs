RNPX-12 is a small integer RNA folding model. Scores are maximized. Indices are
zero-based and inclusive.

Input grammar:

- `sequence NAME ACGU...`
- `react CH i tok`
- `guide CH i j tok`
- `probe i j`

Packed thermo records:

- Base-36 digits are `0-9A-Z`.
- `loops.tbl`: first read `salt S`; each `param key tok` decodes as
  `(base36(tok) xor S) - 128`.
- `pairs.tbl`: first read `salt S`; each `pair XY tok` decodes as
  `(base36(tok) xor ((ord(X)*17 + ord(Y)*31 + S) mod 256)) - 64`.
- `motif.pack`: `motif name seed encoded hex`. Decode bases in alphabet
  `ACGU`; for position `p`, decoded index is
  `encoded_index - seed - 3*p (mod 4)`. The bonus is
  `(hex_value xor ((len*29 + seed*7) mod 256)) - 64`.
- `stack.pack`: first read `salt S`; each `stack OUTER INNER tok` decodes as
  `(base36(tok) xor ((sum(ord(c) for c in OUTER+INNER)*5 + S) mod 256)) - 40`.
  Missing stack records contribute zero on top of `stack_base`.
- `coax.pack`: first read `salt S`; each `coax LEFT RIGHT PHASE tok` decodes as
  `(base36(tok) xor ((sum(ord(c) for c in LEFT+RIGHT) + 37*PHASE + S) mod 256)) - 48`.
  Missing coaxial records are not legal coaxial candidates.
- `shape.pack`: first read `salt S`; each `shape LEFT RIGHT PHASE MOD tok`
  decodes as
  `(base36(tok) xor ((sum(ord(c) for c in LEFT+RIGHT) + 41*PHASE + 17*MOD + S) mod 256)) - 36`.
  Missing shape records are not legal registered-run candidates.
- `splice.pack`: first read `salt S`; each
  `splice LEFT RIGHT PHASE MOD tok` depends on already decoded `coax` and
  `shape` records with the same keys. Decode it as
  `(base36(tok) xor ((sum(ord(c) for c in LEFT+RIGHT) + 43*PHASE + 19*MOD + S
  + ((coax_bonus+96) mod 256) + ((shape_bonus+96) mod 256)) mod 256)) - 44`.
  Records whose matching `coax` or `shape` entry is absent are ignored.
  Missing splice records are not legal registered-run candidates.
- `context.pack`: first read `salt S`; initialize `carry=S`. Each
  `context XY MOD tok` decodes as
  `(base36(tok) xor ((ord(X)*11 + ord(Y)*13 + 23*MOD + S + carry) mod 256)) - 50`.
  After each decoded record, update
  `carry=(carry*3 + decoded_value + 257) mod 256`. Missing context records
  contribute zero.
- `probe.pack`: first read `salt S`; each `channel CH pair_tok unpair_tok`
  decodes as
  `paired_weight=(base36(pair_tok) xor ((sum(ord(c) for c in CH)*13 + S) mod 256)) - 32`
  and
  `unpaired_weight=(base36(unpair_tok) xor ((sum(ord(c) for c in CH)*17 + S) mod 256)) - 32`.
- `guide.pack`: first read `salt S`; each `lane CH mode_tok weight_tok`
  decodes as
  `mode=(base36(mode_tok) xor ((sum(ord(c) for c in CH)*11 + S) mod 256)) mod 4`
  and
  `weight=(base36(weight_tok) xor ((sum(ord(c) for c in CH)*17 + 23*mode + S) mod 256)) - 16`.

Chemical probing records:

- Each input `react CH i tok` uses the `probe.pack` salt and decodes as
  `(base36(tok) xor ((i*19 + sum(ord(c) for c in CH)*7 + S) mod 256)) - 96`.
- Channel base selectivity is: `SH` applies to all bases, `DM` applies only to
  `A/C`, and `CM` applies only to `G/U`.
- For every decoded applicable record at base `i`, add
  `unpaired_weight * value` to `U[i]` and subtract `paired_weight * value` from
  `B[i]`. Non-applicable channel/base combinations still must be decoded and
  emitted, but contribute zero to both arrays.

Guide records are sparse interval evidence. Each input `guide CH i j tok` uses
the `guide.pack` salt and decodes as
`(base36(tok) xor ((i*31 + j*17 + sum(ord(c) for CH)*5 + S) mod 256)) - 32`.
Emit every decoded guide record in input order. It contributes
`lane_weight * decoded_value` to an exact interval guide bonus `E[i][j]` only
when `0 <= i < j < n`, the lane exists, and the lane mode applies to
`seq[i]seq[j]`:

- mode 0 applies to canonical Watson-Crick pairs `AU`, `UA`, `GC`, and `CG`.
- mode 1 applies to wobble pairs `GU` and `UG`.
- mode 2 applies to strong GC pairs `GC` and `CG`.
- mode 3 applies when the left base is a purine, `A` or `G`.

Let `pair(i,j)` be the two-base closing string `seq[i]seq[j]`. A terminal
mismatch score for closing pair `XY` and adjacent bases `a,b` is:

`(((idx(a)+1)*3 + (idx(b)+1)*5 + gc_flag(XY)*2 + terminal_seed) mod 7) - 3`

where `idx(A,C,G,U)=0,1,2,3` and `gc_flag` is one when either base in `XY` is
`G` or `C`.

The per-base arrays `B` and `U` are chemical-probing evidence. `B[i]` is added
when base `i` is used as a closing paired base. `U[i]` is added when base `i`
is explicitly skipped as unpaired or lies in a hairpin/internal-loop unpaired
segment.

Dynamic-programming states:

- `P[i][j]`: best structure on `[i,j]` where `i` pairs with `j`.
- `G[i][j]`: best non-empty multiloop branch forest on `[i,j]`.
- `R[i][j]`: best exact registered two-branch run on `[i,j]`.
- `F[i][j]`: best external structure on `[i,j]`.

Impossible states use negative infinity. Printed impossible values are
`-999999`.

Probe reporting convention: DP table entries exist only for
`0 <= i <= j < n`. For a probe outside that range, do not clamp indices.
Report `F_value` as `0` and report `P_value` and `G_value` as `-999999`.
Report `R_value` as `-999999`. The same `F_value` convention applies to empty
or otherwise invalid external intervals, because the zero candidate is always
available.

`P[i][j]` is impossible unless the closing pair is allowed and
`j-i-1 >= min_loop`. Candidate order for ties is hairpin, stack, internal
loops, then multiloop.

Before evaluating any `P[i][j]` candidate, define
`context_mod=((j-i) + 2*i + 3*j) mod 5` and
`close_score=pair_score + B[i]+B[j] + context_bonus[pair(i,j),context_mod] + E[i][j]`.
Missing context and guide bonuses are zero.

- Hairpin:
  `close_score - (hairpin_base + hairpin_slope*(loop_len-min_loop))`
  plus terminal mismatch on the first and last loop bases, every decoded motif
  bonus whose motif occurs at least once in the loop, and `sum(U[t])` for
  `i<t<j`.
- Stack:
  `close_score + stack_base + stack_bonus[outer,inner] + P[i+1][j-1]`.
- Internal loop:
  choose `i<a<b<j`, `1 <= left+right <= max_internal`, where
  `left=a-i-1` and `right=j-b-1`. Score is
  `close_score + P[a][b] - internal_penalty*(left+right)
   - asym_penalty*abs(left-right)`, plus `U` for the skipped left and right
  segments. When both sides have unpaired bases, also add
  `terminal_score(pair(i,j), seq[i+1], seq[j-1])` and
  `terminal_score(pair(a,b), seq[a-1], seq[b+1])`. Iterate `a` increasing,
  then `b` increasing.
- Multiloop:
  `close_score - ml_close + G[i+1][j-1]`.

`R[i][j]` tie order is registered splits in increasing `k`. A registered split
is legal only when `P[i][k]`, `P[k+1][j]`, a matching `coax` record, a
matching `shape` record, and a matching `splice` record all exist. Its score is

`P[i][k] + P[k+1][j] - 2*ml_branch - reg_penalty + coax_bonus + shape_bonus + splice_bonus`

where `phase=((k-i+1)+2*(j-k)) mod 3` and
`MOD=((k-i+1)*7 + (j-k)*3 + i + j) mod 4`.

`G[i][j]` tie order is full branch, left skip, right skip, registered run,
coaxial split, then ordinary split:

- Full branch: `P[i][j] - ml_branch`.
- Left skip: `U[i] + G[i+1][j] - ml_unpaired`.
- Right skip: `U[j] + G[i][j-1] - ml_unpaired`.
- Registered run: `R[i][j]`.
- Coaxial split, for increasing `k`: if `P[i][k]` and `P[k+1][j]` exist and a
  matching `coax` record exists, score
  `P[i][k] + P[k+1][j] - 2*ml_branch + coax_bonus`. The phase is
  `((k-i+1) + 2*(j-k)) mod 3`.
- Ordinary split, for increasing `k`: `G[i][k] + G[k+1][j]`.

`F[i][j]` tie order is zero, pair, left skip, right skip, then splits in
increasing `k`:

`max(0, P[i][j], U[i]+F[i+1][j], U[j]+F[i][j-1], F[i][k]+F[k+1][j]-split_penalty)`.

Trace back from `F[0][n-1]`, emit all chosen pairs sorted by left index, then
emit the final score and dot-bracket string. Emit decoded `splice` records
after decoded `shape` records, decoded `context` records after decoded `splice`
records, decoded `channel` records after decoded `context` records, decoded
`lane` records after decoded `channel` records, then decoded input `react` and
`guide` records in input order, then probe traces.

Output grammar:

All integers are printed in signed decimal notation. Print exactly one newline
after each record and no other output.

- `pairscore XY value`
- `param key value`
- `motif motif bonus`
- `stack OUTER INNER bonus`
- `coax LEFT RIGHT PHASE bonus`
- `shape LEFT RIGHT PHASE MOD bonus`
- `splice LEFT RIGHT PHASE MOD bonus`
- `context XY MOD bonus`
- `channel CH paired_weight unpaired_weight`
- `lane CH mode weight`
- `react CH i value`
- `guide CH i j value`
- `trace i j F_value P_value G_value R_value`
- `pair i j`
- `score value`
- `dotbracket string`

Decoded thermo records are emitted in file order after ignored records are
removed. Input `react`, input `guide`, and `probe` records are emitted in input
order. Trace values use `-999999` for impossible `P`, `G`, and `R` states.
