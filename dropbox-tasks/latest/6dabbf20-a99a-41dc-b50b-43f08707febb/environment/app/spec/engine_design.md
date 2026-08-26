# Tape Engine — Internal Design Note (rev. 7)

Status: accepted, implemented in tree. Owner: training-infra.
Audience: anyone touching the autodiff core, the training loop, the checkpoint
subsystem, or the run database. This is the reference for *why* the engine is
built the way it is and *exactly* what numbers it must produce. It is deliberately
explicit: the whole product of this engine is reproducibility, and reproducibility
that is only described loosely is not reproducibility.

This document is long because the invariants are subtle and interact. Read the
whole thing before changing anything in `tape.rs`, `rng.rs`, `optimizer.rs`, or
`checkpoint.rs`; a change that looks locally harmless in one of those files
routinely breaks a property that is only observable several training steps later,
in a different subsystem. The failure-mode catalogue near the end (section 19) is
not padding — every item in it is a real regression we have shipped at least once.

---

## 1. What this engine is, and what "correct" means

The engine trains a small fixed multilayer perceptron by reverse-mode automatic
differentiation over an explicit tape, using a hand-written Adam variant, on a
fixed synthetic dataset, from a fixed seed. It is not interesting as a model. It
exists as the reference implementation of three correctness properties that our
larger training stack depends on and that are notoriously easy to get subtly
wrong:

1. **Rematerialization invisibility.** A training run with activation
   rematerialization (a.k.a. gradient checkpointing) enabled must produce numbers
   that are *identical* — not "close", identical — to the same run with
   rematerialization disabled. Rematerialization trades compute for memory by
   discarding some activations during the forward pass and recomputing them during
   the backward pass. The recomputation must reproduce the discarded values
   exactly, which is only possible if every source of nondeterminism inside the
   recomputed region — here, dropout — is replayed from the same PRNG state it
   consumed originally. If it is not, gradients drift, and because the drift is
   fed back through the optimizer the two runs diverge *a few steps later*, not on
   the step where the mistake happened. This is the single most common class of
   bug in production checkpointing code.

2. **Resume fidelity.** Training can be stopped at a checkpoint and resumed later,
   possibly in a different process, and the resumed run must continue *as if it had
   never stopped*: the per-step loss and gradient norm of the resumed steps must
   equal the corresponding steps of an uninterrupted run. This requires the
   checkpoint to capture the full state needed to continue deterministically —
   weights, optimizer accumulators, PRNG state, and the step counter — not just
   the weights. A weights-only checkpoint resumes into a *different* trajectory
   because Adam's moment estimates and the PRNG position are both lost.

3. **Ragged-batch stream fidelity.** The dataset size is not a multiple of the
   batch size, so every epoch ends with a short "ragged" batch. The number of
   random draws consumed in an epoch depends on the exact sizes of its batches,
   because dropout draws one random number per activation element and the ragged
   batch has fewer elements. Mishandling the ragged batch (dropping it, or padding
   it up to a full batch) consumes the wrong number of draws and desynchronizes the
   PRNG stream for *every subsequent epoch's shuffle*. Like (1), the symptom shows
   up later and elsewhere.

"Correct" is defined operationally by an independent reference implementation that
recomputes the expected per-step loss and gradient norm from the raw dataset bytes
and the formulas in this document, and by cross-run comparisons inside the run
database. There is no tolerance for "the algorithm is morally the same": the Adam
epsilon placement, the layer-norm epsilon, the float summation order, and the
dropout scaling are all pinned, because each of them changes the low-order bits and
the low-order bits are what the comparisons check.

Everything is IEEE-754 binary64 (`f64`). There is no `f32` anywhere. There is no
threading and no parallel reduction anywhere: reductions run sequentially in a
pinned index order (section 14). If you introduce a `rayon` iterator or a
`HashMap`-keyed accumulation "for speed", you will reorder floating-point additions
and break bit-for-bit reproducibility between the cached and rematerialized passes.
Don't.

---

## 2. Conventions and notation

- All matrices are dense, row-major, `f64`. A matrix with `r` rows and `c` columns
  stores element `(i, j)` at flat offset `i * c + j`.
- A batch of `R` examples is a matrix `X` of shape `R × D_in`; row `i` is one
  example. Layer activations keep the batch on the row axis throughout, so a hidden
  activation is `R × H`.
- Weight matrices multiply on the right: a linear layer with input width `K` and
  output width `M` has a weight `W` of shape `K × M` and computes `Z = X·W + b`
  where `b` is broadcast across rows. Biases, layer-norm gains, and layer-norm
  shifts are length-`M` vectors stored as `1 × M` matrices so that every parameter
  tensor can be iterated uniformly (section 15).
- `⊙` is elementwise (Hadamard) product. `Xᵀ` is transpose. `‖·‖` is the Euclidean
  (L2) norm of the flattened argument.
- Indexing is zero-based. "Step `k`" means the `k`-th optimizer update, counting
  from 0. "Epoch `e`" means `e = floor(step / batches_per_epoch)`.
- Random draws are counted in units of 64-bit outputs from the core generator
  (`next_u64`, section 6). Everything else — uniforms, integers, normals — is
  defined in terms of how many `next_u64` calls it consumes, because that count is
  what has to line up across runs.

The architecture is fixed: input width `D_in` and class count `C` come from the
dataset manifest; the three hidden widths are pinned at `H1 = H2 = H3 = 16`. With
the shipped dataset `D_in = 8` and `C = 4`.

---

## 3. Module map

The crate is split so that each concern that has a reproducibility invariant lives
in exactly one place:

- `rng.rs` — the PRNG. One 64-bit word of state, snapshot/restore.
- `tensor.rs` — the `Mat` type and its sequential reductions (matmul, transpose,
  column sums, sum-of-squares).
- `ops.rs` — forward and backward for each op (layer norm, ReLU, the layer-3
  activation, dropout apply, softmax cross-entropy).
- `tape.rs` — the parameter set, the forward pass that records the activation tape,
  the reverse pass (including the rematerialized layer-2 recompute), gradient
  clipping, and the global gradient norm.
- `optimizer.rs` — the Adam variant and its state.
- `dataset.rs` — the manifest/fixture parser and the raw-blob loader.
- `checkpoint.rs` — the snapshot binary format, load-time validation, and the
  state-fingerprint hashes.
- `dbwriter.rs` — emission of the run database via the `sqlite3` tool.
- `report.rs` — the per-step and per-snapshot row records.
- `main.rs` — argument parsing and the training-loop driver that ties the modes
  together.

The forward tape and the reverse pass are the heart; the rest exists to feed them
deterministic inputs and to record their outputs faithfully.

---

## 4. Data flow of one training step

One step consumes one batch and produces one optimizer update and one database row.
In order:

1. If this step begins an epoch, draw a fresh permutation of all sample indices
   (section 11). Otherwise reuse the current epoch's permutation.
2. Slice the permutation to this step's batch. The final batch of an epoch is
   short (ragged); it is used at its true length, never dropped and never padded.
3. Gather the batch rows from the dataset into `X` (shape `R × D_in`) and the batch
   labels into a length-`R` vector.
4. Run the forward pass (section 8), consuming dropout draws in a fixed order and
   recording the tape. If rematerialization is on, the layer-2 block is *computed*
   (its loss contribution is needed) but *not retained* on the tape; only the PRNG
   state immediately before its dropout draw is retained.
5. Compute the loss from the output logits (softmax cross-entropy, mean over the
   batch).
6. Run the reverse pass (section 9). If rematerialization is on, recompute the
   layer-2 block from the retained layer-1 output with the PRNG restored to the
   retained pre-dropout state, then restore the PRNG to where the forward pass left
   it (section 10).
7. Clip the layer-3 gradient group (section 13). Record the *post-clip* global
   gradient norm over all parameters.
8. Apply the Adam update (section 12).
9. Append a row to the `steps` table: the step index, the loss, the post-clip
   gradient norm, and a fingerprint hash of the full post-update state.
10. In checkpoint mode, persist a snapshot of the post-update state and append a row
    to the `checkpoints` table.

The PRNG is a single continuous stream threaded through the entire run: init draws
first, then for each epoch a shuffle followed by the per-batch dropout draws. The
stream is never reseeded mid-run. This is what makes the whole thing a single
deterministic function of the seed.

---

## 5. Dataset and manifest

The dataset lives in `/app/data` and is a fixed, vendored, synthetic blob. It is
never regenerated; the bytes are the ground truth. `dataset_manifest.toml`
describes it:

- `num_samples` — total examples (shipped value 50).
- `input_dim` — feature width `D_in` (shipped value 8).
- `num_classes` — label cardinality `C` (shipped value 4).
- `batch_size` — examples per full batch (shipped value 16).
- `input_file` / `target_file` — the blob names.
- `input_dtype = "f64_le"` — `num_samples × input_dim` little-endian binary64,
  row-major (example 0's 8 features, then example 1's, …).
- `target_dtype = "i64_le"` — `num_samples` little-endian signed 64-bit integers,
  each a class label in `[0, C)`.

`train_inputs.bin` is therefore `50 × 8 × 8 = 3200` bytes and `train_targets.bin`
is `50 × 8 = 400` bytes. The loader must check these lengths and reject anything
else; a truncated blob is a hard error, not something to pad around.

The sample count is deliberately **not** a multiple of the batch size:
`50 = 3 × 16 + 2`. Every epoch is four batches of sizes `16, 16, 16, 2`. The
two-example ragged batch is not an accident to be tidied away; it is load-bearing
(sections 11 and 19).

---

## 6. The pseudo-random number generator

The generator is SplitMix64. The entire state is a single `u64`. That is the whole
point: to rematerialize a dropout mask or to resume a run, we must be able to
snapshot the generator to a fixed-size value and later restore it so that the *next*
draw is identical. A generator whose state is spread across an array, a buffer of
pre-generated values, or a lazily-cached second normal deviate is far harder to
snapshot correctly, and the usual bug is to snapshot part of it. One word, no
hidden cache.

### 6.1 Core step

Given state `s`:

```
s   ← (s + 0x9E3779B97F4A7C15)            mod 2^64
z   ← s
z   ← (z XOR (z >> 30)) * 0xBF58476D1CE4E5B9   mod 2^64
z   ← (z XOR (z >> 27)) * 0x94D049BB133111EB   mod 2^64
z   ← z XOR (z >> 31)
next_u64 ← z
```

All arithmetic is wrapping in `u64`. `next_u64` advances the state by exactly one
increment of the golden-ratio constant, so the stream position is exactly the
number of `next_u64` calls made since seeding.

Test vector — seeding with `s = 1234` and calling `next_u64` six times yields, in
hex:

```
0xbb0cf61b2f181cdb  0x97c7a1364df06524  0x33befae49bc025da
0x4e6241f252d0a033  0xb912e3ff44b145a5  0xb0bfb29e8c72a511
```

If your generator does not reproduce those exact words, nothing downstream will
line up and there is no point debugging anything else first.

### 6.2 Open-interval uniform

A uniform in the open interval `(0, 1)` — never exactly 0 or 1 — is derived from
one `next_u64`:

```
uniform_open ← ((next_u64 >> 11) as f64 + 0.5) * (1.0 / 2^53)
```

Taking the top 53 bits and adding a half-ULP offset keeps the result strictly
inside `(0, 1)`, which matters because it feeds `ln(·)` in the normal generator
(section 6.4) where an input of exactly 0 would be catastrophic. One draw, one
`next_u64`.

Test vector — from `s = 1234`, the first four `uniform_open` values:

```
0.73066652454062408  0.59288985801498617
0.20213287431010990  0.30618679205037097
```

### 6.3 Bounded integer

A uniform integer in `[0, n)` uses Lemire's multiply-shift, which consumes exactly
one `next_u64` and does no rejection loop (rejection would make the draw count
input-dependent, which we cannot have):

```
below(n) ← (next_u64 as u128 * n as u128) >> 64
```

Because it never rejects, `below(n)` always advances the stream by exactly one,
regardless of `n`. This is essential for keeping the shuffle's draw count fixed.

Test vector — from `s = 1234`, `below(50)` eight times:

```
36  29  10  15  36  34  24  11
```

### 6.4 Normal deviate

Standard normals use the Box–Muller transform, cosine branch only, and consume
exactly **two** `next_u64` calls per normal:

```
u1 ← uniform_open        # one draw
u2 ← uniform_open        # one draw
normal ← sqrt(-2 · ln(u1)) · cos(2π · u2)
```

The sine companion deviate is *discarded*, not cached. Caching it would halve the
draw count and — worse — introduce hidden generator state (the cached value and a
"have I got one buffered" flag) that the snapshot format would have to capture.
Discarding it keeps the rule trivial: one normal is two draws, always, and the
generator state after `k` normals is exactly the state after `2k` `next_u64` calls.

Test vector — from `s = 1234`, the first four normals:

```
-0.66106731351334813  -0.61826026342832963
-0.29452649233363881   0.16601907694432896
```

### 6.5 Snapshot and restore

`state()` returns the current `u64`; `set_state(s)` overwrites it. These are used
in two places: the rematerialized backward pass (save the live state, jump back to
the retained pre-dropout state, redraw, jump forward again — section 10) and the
snapshot file (persist the state, restore it on resume — section 15). Both rely on
the property that `set_state(state())` is a no-op and that after `set_state(v)` the
next `next_u64` is exactly what it would have been at the moment `v` was captured.

---

## 7. Weight initialization

Initialization draws from the same stream as everything else, *before* the first
epoch's shuffle. The order is fixed and the counts are fixed, because the shuffle
that follows must land on a specific stream position.

Only the four weight matrices are randomized. In this exact order — `W1`, `W2`,
`W3`, `Wo` — each matrix is filled row-major (element `(0,0)`, `(0,1)`, …, then
row 1, …), each element being one `normal()` (two `next_u64` draws) scaled by the
matrix's standard deviation:

- `W1` (`D_in × H1`): σ = 0.30
- `W2` (`H1 × H2`): σ = 0.30
- `W3` (`H2 × H3`): σ = 0.50
- `Wo` (`H3 × C`): σ = 0.30

The biases `b1, b2, b3, bo` initialize to 0. The layer-norm gains `g1, g2`
initialize to 1 and the shifts `be1, be2` to 0. None of those consume draws.

With the shipped dimensions the matrices hold `8·16 = 128`, `16·16 = 256`,
`16·16 = 256`, and `16·4 = 64` elements, so initialization draws `704` normals =
**1408** `next_u64` calls, after which the stream is positioned for the epoch-0
shuffle. Getting this count wrong (for example by drawing biases, or by using a
normal generator that consumes one draw instead of two) shifts every subsequent
shuffle and dropout mask.

Worked value — seeding with the shipped run seed `0xC0FFEE123`, the first four
entries of row 0 of `W1` and `W3` are:

```
W1[0][0..4] =  0.2233087383   0.2500335658  -0.2555885362   0.2387368010
W3[0][0..4] = -0.1239918797   0.4860665624   0.0468852323  -0.3452711613
```

`W3`'s larger σ is intentional; it is what lets layer 3 occasionally produce large
pre-activations, which is what makes its gradients occasionally large (section 13).

---

## 8. The forward pass

The network, for a batch `X` of shape `R × D_in`:

```
Z1 = X · W1 + b1                      # R × H1
N1 = layernorm(Z1; g1, be1)           # R × H1
A1 = relu(N1)                         # R × H1
D1 = dropout(A1; mask1)               # R × H1   -- mask1 drawn here
Z2 = D1 · W2 + b2                     # R × H2
N2 = layernorm(Z2; g2, be2)           # R × H2
A2 = relu(N2)                         # R × H2
D2 = dropout(A2; mask2)               # R × H2   -- mask2 drawn here
Z3 = D2 · W3 + b3                     # R × H3
A3 = gcube(Z3)                        # R × H3   -- the layer-3 activation
Zo = A3 · Wo + bo                     # R × C    -- logits
loss = softmax_cross_entropy(Zo, y)   # scalar, mean over the R rows
```

Note that there is exactly one dropout site after layer 1 and one after layer 2,
and none after layer 3. Layer 3 has no layer norm either; it is a bare linear
followed by the amplifying activation, which is deliberate.

### 8.1 Matmul

`(X · W)[i][j] = Σ_k X[i][k] · W[k][j]`, with the sum accumulated over `k` in
increasing order into an `f64` accumulator initialized to 0.0. Bias is added
afterward by broadcasting `b` across the rows. The reduction order is part of the
contract (section 14).

### 8.2 Layer norm

Per row `i` of a width-`H` input `z`, with learnable gain `γ` and shift `β` (both
length `H`) and `ε_ln = 1e-5`:

```
μ_i   = (1/H) Σ_j z[i][j]
var_i = (1/H) Σ_j (z[i][j] - μ_i)^2          # biased (divide by H, not H-1)
inv_i = 1 / sqrt(var_i + ε_ln)
xhat[i][j] = (z[i][j] - μ_i) · inv_i
y[i][j]    = xhat[i][j] · γ[j] + β[j]
```

The variance is the biased estimator (denominator `H`, not `H-1`) and the epsilon
is inside the square root, added to the variance. Both are pinned; the common
alternative of an unbiased variance or an epsilon added to the standard deviation
changes the result. The backward pass needs `xhat`, `inv`, and `γ`, so those are
what the layer-norm cache retains.

### 8.3 ReLU

`relu(x) = max(x, 0)`, elementwise. The backward pass gates on the *output* being
strictly positive: an element contributes its upstream gradient iff its ReLU output
was `> 0` (equivalently, its pre-activation was `> 0`; at exactly 0 the gradient is
dropped).

### 8.4 Dropout

Inverted dropout with rate `p = 0.2`. For each element, draw `u = uniform_open()`
and set the mask entry to `1/(1-p)` if `u ≥ p`, else `0`; then `D = A ⊙ mask`. The
draws are taken row-major over the `R × H` activation: element `(0,0)`, `(0,1)`, …,
`(0,H-1)`, `(1,0)`, …. That order and count are part of the stream contract. A
batch of `R` rows draws `R · H` uniforms at each of the two dropout sites, so
`R · (H1 + H2) = R · 32` draws per step from dropout alone.

The scale `1/(1-p) = 1.25` is applied on the *kept* elements at training time
(inverted dropout), so no rescaling is needed at inference. Do not instead scale by
`(1-p)` on inference; that is a different convention and changes the forward values.

### 8.5 Layer-3 activation (`gcube`)

```
gcube(z) = z^3 / 3          derivative: gcube'(z) = z^2
```

This is the "unstable" activation. Its derivative grows without bound as `|z|`
grows, so when layer 3's pre-activations are large — which happens on some batches
because of `W3`'s larger init scale — the gradient flowing back through it is large.
This is by design and is handled by clipping (section 13), **not** by changing the
activation. See section 19.5 for why "fixing" this is the classic wrong move.

### 8.6 Softmax cross-entropy

For logits row `zo` (length `C`) and integer label `t`:

```
m     = max_j zo[j]
p[j]  = exp(zo[j] - m) / Σ_k exp(zo[k] - m)
loss_row = -ln(p[t])
```

The batch loss is the mean over rows: `loss = (1/R) Σ_i loss_row_i`. The gradient
w.r.t. logits is `(p - onehot(t)) / R` per row (the `1/R` folds the mean in). The
max-subtraction is for numerical stability and does not change the result.

Worked value — the very first step of the shipped run (seed `0xC0FFEE123`, batch 0
of epoch 0, rematerialization on) has:

```
loss(step 0)                     = 5.387207426858
layer-3 pre-clip gradient norm   = 4.877990213952     (> τ = 3.0, so it clips)
post-clip global gradient norm   = 15.173594405300
```

---

## 9. The reverse pass

The reverse pass walks the tape from the loss back to the parameters, accumulating
a gradient for every parameter tensor. Each op's vector-Jacobian product:

### 9.1 Output layer and softmax

`dZo = (p - onehot(y)) / R` (computed by the softmax-CE backward). Then
`gWo = A3ᵀ · dZo`, `gbo = colsum(dZo)`, and `dA3 = dZo · Woᵀ`.

### 9.2 Layer-3 activation

`dZ3 = dA3 ⊙ gcube'(Z3) = dA3 ⊙ (Z3 ⊙ Z3)`. This is where the large gradients
enter: if `Z3` has entries of magnitude a few units, `Z3^2` is up to tens, and
`dZ3` inherits that amplification.

### 9.3 Layer-3 linear

`gW3 = D2ᵀ · dZ3`, `gb3 = colsum(dZ3)`, `dD2 = dZ3 · W3ᵀ`.

### 9.4 Dropout and ReLU (both layers)

Dropout backward reuses the *same* mask as the forward: `dA2 = dD2 ⊙ mask2`. ReLU
backward gates on the stored ReLU output: `dN2 = dA2 ⊙ [A2 > 0]`. In the
rematerialized configuration, `mask2` and `A2` are the recomputed ones (section
10), which is why the recompute must reproduce them exactly.

### 9.5 Layer norm backward

Given upstream `dy` (shape `R × H`) and the cached `xhat`, `inv`, `γ`, per row `i`:

```
dxhat[i][j] = dy[i][j] · γ[j]
s1_i        = Σ_j dxhat[i][j]
s2_i        = Σ_j dxhat[i][j] · xhat[i][j]
dz[i][j]    = (inv_i / H) · ( H · dxhat[i][j] - s1_i - xhat[i][j] · s2_i )
dγ[j]       = Σ_i dy[i][j] · xhat[i][j]
dβ[j]       = Σ_i dy[i][j]
```

The two per-row reductions `s1` and `s2` are accumulated over `j` in increasing
order; the two per-column reductions `dγ`, `dβ` over `i` in increasing order. This
formula is the standard layer-norm VJP for the biased-variance definition in
section 8.2; if you derived it against an unbiased variance it will be subtly off.

### 9.6 Remaining layers

Symmetrically: `gW2 = D1ᵀ · dZ2`, `gb2 = colsum(dZ2)`, `dD1 = dZ2 · W2ᵀ`, then
dropout/ReLU/layernorm backward through layer 1, ending at `gW1 = Xᵀ · dZ1`,
`gb1 = colsum(dZ1)`. `X` is the batch input and needs no gradient.

Every `Xᵀ · Y` and `Y · Wᵀ` is a matmul with the transpose materialized first and
the same sequential reduction order as section 8.1.

---

## 10. Rematerialization schedule

Rematerialization is per-layer, and the schedule is fixed: **only the layer-2 block
is rematerialized.** "The layer-2 block" is everything from the layer-1 dropout
output `D1` through `D2`: the linear `Z2`, the layer norm `N2`, the ReLU `A2`, the
dropout `D2`, and — critically — the dropout `mask2`. Layer 1's activations and
mask, and layer 3's, are cached normally.

Rationale for choosing layer 2 specifically: it is the one interior block that both
(a) sits behind a stochastic op whose replay is nontrivial and (b) is cheap to
recompute from a single retained tensor (`D1`). Rematerializing layer 1 would
require retaining `X` (fine) but gains little; rematerializing layer 3 would not
exercise the dropout-replay path at all because layer 3 has no dropout. Layer 2 is
the interesting case, so it is the one we rematerialize, and the engine's whole
reason for existing is to get it right.

### 10.1 What the forward pass retains

With rematerialization on, the forward pass still computes the layer-2 block (it has
to; the loss depends on it) but does **not** put `Z2, N2-cache, A2, mask2, D2` on
the tape. Instead it retains exactly one extra scalar: the PRNG state
*immediately before `mask2` was drawn*, call it `rng_pre`. Everything from `D1`
onward that the backward pass needs will be recomputed from `D1` and `rng_pre`.

The memory win is real: for a batch of `R` rows the discarded tensors are
`5 · R · H2` floats plus the layer-norm cache; retained is a single `u64`. On this
toy network that is nothing, but on the real network the layer-2-analogue blocks are
the bulk of activation memory, which is why the technique exists.

### 10.2 What the backward pass does

When the reverse pass reaches the layer-2 block it recomputes it:

```
main ← rng.state()               # remember where the live stream is
rng.set_state(rng_pre)           # jump back to just before the original mask2 draw
Z2 ← D1 · W2 + b2
(N2, cache2) ← layernorm(Z2; g2, be2)
A2 ← relu(N2)
mask2 ← draw R×H2 dropout uniforms   # identical to the forward's, because same state
D2 ← A2 ⊙ mask2
rng.set_state(main)              # restore the live stream; net PRNG effect is zero
```

The recompute draws exactly the `R · H2` uniforms it drew the first time, because it
starts from the same state. Then it restores `main`, so the *net* effect of the
recompute on the live stream is nothing — the stream is exactly where the forward
pass left it, and the next step sees the same position it would have seen with
rematerialization off. This is the discipline that makes rematerialization
invisible.

Two ways to get this wrong, both of which we have shipped:

- **Not restoring `rng_pre` before the recompute.** Then `mask2` is drawn from the
  live post-forward state, so it is a *different* mask than the forward used. The
  recomputed `A2`/`D2` are wrong, `gW2`/`gW3`/... are wrong, and — because the live
  stream has now been advanced by the recompute — every subsequent step's dropout
  and shuffle are shifted too. The step where you introduced the bug still looks
  fine (the loss is computed in the forward pass, which was correct); the loss
  diverges a couple of steps later once the corrupted gradients have moved the
  weights.
- **Restoring `rng_pre` but forgetting to restore `main` afterward.** Then the
  gradients are right but the live stream has been rewound, so the *next* step draws
  the masks the recompute already consumed, and the two runs diverge going forward.

Both are caught by comparing the rematerialized run against the non-rematerialized
run step by step across the whole run — not just at step 0, where they always agree.

---

## 11. Batching and the ragged last batch

Each epoch begins by drawing a fresh permutation of all `num_samples` indices with a
Fisher–Yates shuffle:

```
perm ← [0, 1, ..., N-1]
for i from N-1 down to 1:
    j ← below(i + 1)
    swap perm[i], perm[j]
```

This consumes exactly `N - 1` draws (`49` for the shipped dataset), independent of
the batch layout, because `below` never rejects. The permutation is then cut into
consecutive slices of `batch_size`: indices `perm[0..16]`, `perm[16..32]`,
`perm[32..48]`, `perm[48..50]`. The last slice has two elements. That short slice is
the **ragged batch**, and the rule is simple and absolute:

> The ragged batch is processed at its true length. It is **not** dropped, and it is
> **not** padded to a full batch.

Worked value — the epoch-0 permutation for seed `0xC0FFEE123` begins:

```
22 49 42 18 29 24 20 21 30 12 8 6 10 23 16 15 ...
```

and the batch sizes are `16, 16, 16, 2`.

### 11.1 Why the ragged rule is a stream invariant, not a convenience

Dropout draws one uniform per activation element, and the activation has one row per
batch example. So the number of dropout draws in a step is `R · (H1 + H2) = 32R`.
Across an epoch of batch sizes `16, 16, 16, 2` the dropout draws total
`32 · (16+16+16+2) = 32 · 50 = 1600`, and with the `49` shuffle draws the epoch
consumes `1649` draws. The stream then sits exactly where the next epoch's shuffle
begins.

Now consider the two tempting "tidy" handlings:

- **Drop the ragged batch** (the moral equivalent of a data loader's
  `drop_last=True`). The epoch now does only `16+16+16 = 48` examples of dropout,
  `32 · 48 = 1536` draws, so it consumes `64` fewer draws than the rule requires.
  The next epoch's shuffle starts `64` draws early and produces a *different*
  permutation. It also records one fewer step per epoch, so the step count is wrong.
- **Pad the ragged batch up to 16** (repeat rows, or append the next epoch's first
  examples). The epoch now does `32 · 64 = 2048` dropout draws instead of `1600`,
  `448` too many. Again the next shuffle is displaced.

Either way the divergence appears at the **first batch of the second epoch**, not
during the first epoch, because that is the first shuffle that starts from a
corrupted stream position. This is the ragged-batch analogue of the
rematerialization trap in section 10: a local decision that looks harmless corrupts
a shared resource (the PRNG position) whose damage only surfaces one epoch boundary
later. See section 19.3.

The `64`-draw deficit from dropping is exactly `2 · (H1 + H2) = 2 · 32`: the two
ragged rows times the two dropout sites' widths. That is the number to keep in mind
when reasoning about where the stream ends up.

---

## 12. The optimizer

The update is Adam with decoupled bias correction and a specific epsilon placement.
Hyperparameters, all pinned: `lr = 0.01`, `β1 = 0.9`, `β2 = 0.999`, `ε = 1e-8`. A
single global step counter `t` (the number of updates applied so far, starting at 1
for the first update) drives the bias correction and is part of the optimizer state
that a checkpoint must carry.

For each parameter tensor `θ` with gradient `g`, elementwise:

```
m ← β1·m + (1-β1)·g
v ← β2·v + (1-β2)·(g⊙g)
m̂ ← m / (1 - β1^t)
v̂ ← v / (1 - β2^t)
θ ← θ - lr · m̂ / ( sqrt(v̂) + ε )        # epsilon OUTSIDE the sqrt
```

The moment accumulators `m` and `v` start at 0 and have the same shape as the
parameters; they are iterated in the canonical tensor order (section 15) so that the
update is deterministic.

### 12.1 Epsilon placement is not cosmetic

The epsilon goes **outside** the square root, added to `sqrt(v̂)`, i.e.
`sqrt(v̂) + ε`. The common alternative — adding epsilon *inside*, `sqrt(v̂ + ε)` —
is "the same algorithm" in the sense that both regularize the denominator, but the
two produce different numbers, and the difference is *not* uniformly tiny. It is
largest exactly where it matters: for parameters whose second-moment estimate is
small.

Worked example at `t = 1` (so `m̂ = g`, `v̂ = g²`):

- For a healthy gradient `g = 0.5`: `v̂ = 0.25`, `sqrt(v̂) = 0.5`. Outside gives an
  update of `0.0099999998000000027`; inside gives `0.0099999998000000062`. They
  differ by about `3e-18` — negligible.
- For a near-zero gradient `g = 1e-4`: `v̂ = 1e-8`, `sqrt(v̂) = 1e-4`. Outside gives
  `sqrt(v̂) + ε = 1e-4 + 1e-8`, an update of `0.0099990000999899999`. Inside gives
  `sqrt(v̂ + ε) = sqrt(2e-8) ≈ 1.414e-4`, an update of `0.0070710678118654745`.
  These differ by ~30%.

So for parameters with small gradients — of which there are always some — the two
placements give visibly different updates from the very first step. Fold that back
through many steps and the whole trajectory separates. A run built with the inside
placement diverges from the reference by ~`1e-3` in the loss within a couple of
steps; it is not a rounding difference you can wave away. Use the outside placement.

`β1^t` and `β2^t` are computed by ordinary powering with integer exponent `t`; there
is no running product accumulator to drift. `t` increments once per update and is
shared across all parameters.

---

## 13. Gradient clipping

Layer 3's amplifying activation (section 8.5) means `gW3` and `gb3` are sometimes
large. They are clipped by global norm, and **only** they are:

```
n = sqrt( Σ gW3² + Σ gb3² )          # L2 norm over the layer-3 group only
if n > τ:                            # τ = 3.0
    gW3 ← gW3 · (τ / n)
    gb3 ← gb3 · (τ / n)
```

`τ = 3.0`. No other parameter group is clipped. The clip is applied after the full
backward pass and before the optimizer step. The gradient norm recorded in the
database is the **post-clip** global norm over *all* parameters (section 9's `g`
tensors after this scaling), so on steps where the clip engages the recorded norm
reflects the clipped layer-3 group.

Worked value — on the shipped run the pre-clip layer-3 norm exceeds `τ` on steps
`0, 1, 2, 3, 15` (and stays under it on the rest); at step 0 the pre-clip norm is
`4.877990213952` and the clip scales the group down by `3.0 / 4.877990213952`. The
maximum pre-clip layer-3 norm over the run is about `9.63`, comfortably above `τ`.

The recorded post-clip global norm never becomes NaN or infinite, because the clip
bounds the one group that could blow up. If you ever see a NaN gradient norm in a
row, the clip is not being applied — or it is being applied to the wrong group.

Section 19.5 covers at length why the correct response to "layer 3 has huge
gradients" is this clip and *not* a change to layer 3.

---

## 14. Determinism requirements

Reproducibility here is bit-for-bit between the rematerialized and
non-rematerialized runs, and between reruns of the same mode, and it is
tolerance-tight against the independent reference. That imposes rules:

- **Sequential reductions only.** Every sum — matmul inner products, layer-norm
  mean/variance, column sums, sums of squares for norms — is accumulated
  left-to-right in increasing index order into a scalar `f64`. No pairwise or
  tree reduction, no `rayon`/parallel iterator (which reduce in a
  nondeterministic order), no `HashMap`-keyed accumulation (whose iteration order
  is randomized per process). Reordering floating-point additions changes the
  low-order bits, and the low-order bits are exactly what the cached-vs-recomputed
  comparison checks.
- **Canonical parameter order.** Parameters, gradients, and optimizer moments are
  always visited in the order `W1, b1, g1, be1, W2, b2, g2, be2, W3, b3, Wo, bo`
  (section 15). The global gradient norm sums the per-tensor sums-of-squares in
  this order; the optimizer updates in this order; the snapshot serializes in this
  order; the hashes hash in this order.
- **Exact database round-trip.** Losses and gradient norms are written to the
  database with 17 significant decimal digits (`%.17e`), which round-trips an IEEE
  double exactly; SQLite stores them as 8-byte REALs and returns the identical
  double. So a value written by one run and a value written by another are
  bit-comparable after a round-trip through the database.

None of this is premature rigor. The reason the engine can promise that
rematerialization is invisible is that the recompute runs the *same code* over the
*same inputs* in the *same order*, so it produces the *same bits*. Break the order
and the promise is void.

---

## 15. Parameters, snapshots, and hashes

### 15.1 Parameter layout

The parameter set has twelve tensors. Vectors (`b*`, `g*`, `be*`) are stored as
`1 × width` matrices so the whole set can be iterated as a homogeneous list in the
canonical order `W1, b1, g1, be1, W2, b2, g2, be2, W3, b3, Wo, bo`. Gradients and
the two Adam moment sets use the identical layout, so the `i`-th gradient tensor
lines up elementwise with the `i`-th parameter and moment tensors.

### 15.2 Snapshot file format

A snapshot is the full resumable state, written little-endian:

```
offset      bytes  contents
0           8      magic  = ASCII "CKPTAD01"
8           8      step               (u64)  -- the step index to resume AT
16          8      adam_t             (u64)  -- Adam's update counter
24          8      rng_state          (u64)  -- PRNG state to resume FROM
32          W      weights            = each parameter tensor's f64 values,
                                         canonical order, row-major, 8 bytes each
32+W        W      adam m             = same layout as weights
32+2W       W      adam v             = same layout as weights
32+3W       N·8    epoch permutation  = the current epoch's sample order, N u64
                                         indices in draw order (N = num_samples)
32+3W+N·8   8      checksum           (u64)  = FNV-1a-64 of all preceding bytes
```

`W` is the total parameter byte count (`Σ tensor_size · 8`) and `N` is `num_samples`.
Because the tensor shapes are known from `D_in` and `C`, and `N` from the manifest,
the reader knows exactly how many bytes each region occupies; it does not need a
length table.

The snapshot captures **weights, both Adam moment sets, the Adam step counter, the
PRNG state, the step index, and the current epoch's sample permutation.** That is
precisely the state the training loop needs to continue deterministically from any
step. Leaving out the moments makes Adam restart cold (the first resumed update
behaves like a first update, not a `t`-th update); leaving out the PRNG state makes
the resumed shuffle and dropout diverge; leaving out `adam_t` corrupts the bias
correction; leaving out the permutation makes a mid-epoch resume unable to form the
right batches (section 16). All of it, or the resume is not a resume.

### 15.3 Load-time validation

On load the reader checks: the file is at least the fixed-header-plus-checksum size;
the magic matches; and the trailing checksum equals the FNV-1a-64 of the body. It
then reads the fields and verifies that the consumed length plus the 8-byte checksum
equals the file length exactly. Any failure is a hard error that aborts the run with
a nonzero exit *before* any training or database write happens — a truncated or
corrupted snapshot must never be silently half-loaded and then trained on. This is
what keeps a bad checkpoint from quietly poisoning a resumed run.

### 15.4 State-fingerprint hashes

The database records hashes so that state equality can be checked cheaply and so
that a checkpoint's completeness can be audited. All hashes are FNV-1a-64 over a
canonical byte serialization, formatted as 16 lowercase hex digits.

- `weights_hash` — over the weight bytes only (the `weights` region above).
- `optimizer_state_hash` — over `m` bytes, then `v` bytes, then `adam_t` as 8 LE
  bytes.
- `rng_state_hash` — over the 8 LE bytes of the PRNG state.
- The per-step `checkpoint_hash` in the `steps` table — over the *full* state:
  weights bytes, then optimizer bytes (`m`, `v`, `adam_t`), then the PRNG state
  bytes. This is a fingerprint of the entire post-update state and is what lets two
  runs be compared for exact state equality at a given step.

The three separate hashes exist precisely so that a reviewer (or a test) can confirm
the fingerprint responds to each component: change only the optimizer moments and
`optimizer_state_hash` changes while `weights_hash` does not; change only the PRNG
word and `rng_state_hash` changes while the other two do not. A checkpoint hash that
covers weights alone would be blind to exactly the state (moments, PRNG) whose loss
causes resume to diverge — so the full-state `checkpoint_hash` deliberately spans
everything.

FNV-1a-64 is: start from `0xcbf29ce484222325`; for each byte, XOR it into the hash,
then multiply (wrapping) by `0x00000100000001B3`.

---

## 16. Resume semantics

Resume loads a snapshot and continues the loop from the snapshot's `step`, and the
resumed run must reproduce the remaining steps of an uninterrupted run exactly. The
snapshot's `step` may fall **anywhere**, including in the middle of an epoch; the
shipped resume point is step 6, in the middle of epoch 1.

Mid-epoch resume is the case worth thinking about. At step 6 the epoch-1 shuffle
already happened (at the epoch's first step) and its draws were consumed from the
stream, so the current epoch's batch order is *not* recoverable from the restored
PRNG state — the state has moved past it. It has to come from the snapshot, which is
why the permutation is part of the checkpoint (section 15.2). A run resuming
mid-epoch continues with the current epoch's saved batch order and does not reshuffle
until it next crosses an epoch boundary, at which point it draws a fresh shuffle from
the restored-and-advanced PRNG state — the same shuffle the uninterrupted run drew at
that boundary.

Because the snapshot restores weights, both moment sets, `adam_t`, the PRNG state,
*and* the epoch permutation, the resumed run's step 6 does exactly what an
uninterrupted run's step 6 does, and steps 6..15 of the resumed run equal steps 6..15
of the uninterrupted run value for value. That equality is resume fidelity, and it is
tested from the resume step onward — not just at the resume step, because the loss at
the resume step depends only on the weights and can coincide even when the
continuation diverges.

---

## 17. The run database

All runs write to a single SQLite database at `/app/out/runs.db`. Three tables,
created if absent, with these exact definitions:

```sql
CREATE TABLE IF NOT EXISTS runs (
  run_id       TEXT PRIMARY KEY,
  mode         TEXT NOT NULL,
  seed         INTEGER NOT NULL,
  resumed_from TEXT,
  FOREIGN KEY (resumed_from) REFERENCES runs(run_id)
);
CREATE TABLE IF NOT EXISTS steps (
  run_id          TEXT NOT NULL,
  step            INTEGER NOT NULL,
  loss            REAL NOT NULL,
  grad_norm       REAL NOT NULL,
  checkpoint_hash TEXT NOT NULL,
  PRIMARY KEY (run_id, step),
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
CREATE TABLE IF NOT EXISTS checkpoints (
  run_id               TEXT NOT NULL,
  step                 INTEGER NOT NULL,
  weights_hash         TEXT NOT NULL,
  optimizer_state_hash TEXT NOT NULL,
  rng_state_hash       TEXT NOT NULL,
  PRIMARY KEY (run_id, step),
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
```

- `runs` has one row per run. `mode` is the run mode; `seed` is the master seed;
  `resumed_from` is `NULL` except for a resume run, where it names the run whose
  checkpoint it continued.
- `steps` has one row per training step per run: the loss, the post-clip global
  gradient norm, and the full-state fingerprint hash after that step's update.
- `checkpoints` has one row per persisted snapshot (checkpoint mode only), with the
  three component hashes of the snapshotted state.

Foreign keys are declared and must actually hold: every `steps.run_id` and
`checkpoints.run_id` references an existing `runs.run_id`, and a resume run's
`resumed_from` references the run it continued. Writing a run replaces any existing
rows for that `run_id` (delete-then-insert inside a transaction) so that re-running
a mode is idempotent — a second run with the same seed produces byte-identical rows,
not duplicates. `PRAGMA integrity_check` and `PRAGMA foreign_key_check` must both
pass on the finished database.

The three canonical run variants and their `run_id`s: a `nocheckpoint` run
(rematerialization off), a `checkpoint` run (rematerialization on, persists
snapshots), and a `resume` run (continues from the checkpoint run's snapshot at the
resume step, `resumed_from = 'checkpoint'`). By construction the `checkpoint` and
`nocheckpoint` runs must agree at every step, and the `resume` run must agree with
the `checkpoint` run from the resume step onward. These agreements are checked by
joining the tables across runs on `step`.

---

## 18. Command-line interface

```
engine --mode <nocheckpoint|checkpoint|resume|hash> [options]
```

Options (all have defaults pointing at the standard `/app` layout):

- `--db PATH` — database path (default `/app/out/runs.db`).
- `--manifest PATH` — dataset manifest (default `/app/data/dataset_manifest.toml`).
- `--inputs PATH`, `--targets PATH` — dataset blobs.
- `--seed-file PATH` — the seed fixture (default
  `/app/tests_fixtures/golden_seed.toml`).
- `--resume-file PATH` — the resume-point fixture (default
  `/app/tests_fixtures/resume_point.toml`), consulted by resume mode when no
  explicit `--snapshot` is given.
- `--snapshot PATH` — for resume, the snapshot to load; for hash, the snapshot to
  fingerprint.
- `--snap-dir PATH` — where checkpoint mode writes snapshots (default
  `/app/out/snap`). Each file is named `step_NN.bin`, where `NN` is the step the
  snapshot resumes at, **zero-padded to two digits** — i.e. formatted as
  `step_%02d.bin`, so the snapshot resumable at step 4 is `step_04.bin` and the one
  at step 8 is `step_08.bin`.
- `--run-id NAME` — overrides the default `run_id` (which is the mode name).

Modes:

- `nocheckpoint` — full run, rematerialization off, `run_id` defaults to
  `nocheckpoint`.
- `checkpoint` — full run, rematerialization on; writes a snapshot after each step
  (named by the step it resumes at) and a `checkpoints` row per snapshot; `run_id`
  defaults to `checkpoint`.
- `resume` — loads a snapshot and continues to the end; `run_id` defaults to
  `resume`, `resumed_from = checkpoint`. With no `--snapshot`, the snapshot loaded is
  `<snap-dir>/step_NN.bin` for the fixture's `resume_step` (`NN` zero-padded to two
  digits). An explicit `--snapshot PATH` overrides that default and is loaded
  as-is — whatever step it records is where the run continues from, with no further
  constraint on that step.
- `hash` — prints the four fingerprints for a snapshot (a debugging aid; does not
  verify the checksum, so it can inspect deliberately edited snapshots). The output
  is exactly four lines, one per fingerprint, each a `name=value` pair with no
  spaces around the `=`:

```
weights_hash=<16 lowercase hex digits>
optimizer_state_hash=<16 lowercase hex digits>
rng_state_hash=<16 lowercase hex digits>
full_hash=<16 lowercase hex digits>
```

  where each value is the 16-hex-digit FNV-1a-64 fingerprint of its region
  (section 15.4). For example, a snapshot whose PRNG word is `0xC0FFEE123` prints an
  `rng_state_hash` line of `rng_state_hash=3e60e3f2f86028a2` (section 25.1). The
  four lines may be printed in any order.

Exit code is `0` on success and nonzero on any failure (bad arguments, missing or
corrupt data, corrupt snapshot, sqlite error). A failure must leave no partially
written run behind.

---

## 19. Subtle failure modes

The properties in Parts I are easy to state and easy to violate, because most of the
ways to violate them are locally reasonable changes whose damage is only observable
elsewhere, later. This section names the interactions where that happens; each points
back to the normative rule it depends on, which is where the requirement is defined.

### 19.1 Partial checkpoint state
A snapshot that omits any of the optimizer moments, the Adam counter `t`, the PRNG
state, or (for a mid-epoch resume) the epoch permutation is not sufficient to
continue deterministically. The resumed loss at the resume step depends only on the
weights, so an incomplete snapshot can look correct for exactly one step and then
part ways with the uninterrupted run. What a snapshot must carry is section 15.2.

### 19.2 Stochastic recompute and the PRNG
The rematerialized layer-2 recompute draws a dropout mask; unless the generator is
restored to its pre-mask state and then returned to the live state, the recomputed
mask differs from the forward's and the live stream is left displaced. The discipline
is section 10.2.

### 19.3 The ragged batch and the stream
The number of dropout draws in an epoch is a function of how the ragged final batch
is handled; dropping it or padding it changes that count and moves every subsequent
epoch's shuffle. The rule and its draw-count arithmetic are section 11.

### 19.4 Adam epsilon placement
`sqrt(v̂ + ε)` and `sqrt(v̂) + ε` differ for small second moments, which occur for
any parameter with a near-zero gradient. The pinned placement is section 12.

### 19.5 The layer-3 activation
Layer 3's `z^3/3` is a deliberately stiff activation whose large gradients are the
point, not a defect. It is left exactly as defined; its gradients are bounded by the
clip (section 13). Any change to the activation itself — clamping its input, swapping
it for a bounded function, normalizing in front of it — changes the forward values and
therefore the whole trajectory.

### 19.6 Reduction order
Floating-point addition is not associative, so any reduction whose order is not pinned
— a parallel iterator, a hash-map-keyed accumulation — makes results depend on the
schedule or the hasher. The order rules are section 14.

### 19.7 Fingerprint scope
A state fingerprint computed over the weights alone cannot distinguish states that
share weights but differ in optimizer or PRNG position, which are exactly the states a
resume must reproduce. What each hash spans is section 15.4.

---

## 20. Constants, at a glance

```
architecture        H1 = H2 = H3 = 16 ; D_in, C from manifest (8, 4 shipped)
dataset             num_samples = 50, batch_size = 16 -> batches/epoch = 4 (16,16,16,2)
epochs              4  -> 16 steps total
dropout             p = 0.2 ; inverted scale 1/(1-p) = 1.25 ; sites after L1 and L2
layernorm           eps_ln = 1e-5 ; biased variance (divide by H)
layer-3 activation  gcube(z) = z^3/3 ; derivative z^2 ; no layernorm, no dropout
init sigmas         W1 0.30, W2 0.30, W3 0.50, Wo 0.30 ; biases 0, gains 1, shifts 0
init draw order     W1, W2, W3, Wo ; row-major ; 704 normals = 1408 next_u64 calls
optimizer           Adam, lr 0.01, b1 0.9, b2 0.999, eps 1e-8 OUTSIDE sqrt
clip                layer-3 group only, global-norm, tau = 3.0
rematerialize       layer-2 block only ; restore PRNG around the recompute
resume              from any step incl. mid-epoch (epoch permutation is in the snapshot) ; shipped resume_step = 6
determinism         sequential reductions, canonical param order, %.17e in the DB
```

If a change to the engine would alter any line in that table, it is a spec change,
not a refactor, and it needs to be reflected here first.

---

# Part II — Derivations, worked examples, and reference tables

Part I is the specification. Part II exists so that an implementer can check their
work against known-good intermediate numbers, and so that the formulas in Part I are
grounded in derivations rather than asserted. Nothing here overrides Part I; where a
worked example uses a smaller network or fixed masks, that is only to make the
arithmetic legible, and it is called out explicitly.

None of the worked numbers in Part II are the golden per-step losses of the shipped
run; the shipped run's loss trajectory is not tabulated anywhere in this document on
purpose. The micro-trace uses a deliberately different, tiny network so that it
teaches the mechanics without standing in for the real run's outputs.

---

## 21. Derivations

### 21.1 Layer-norm vector-Jacobian product

Layer norm over a width-`H` row computes, with `μ` and `σ² = var` the biased mean
and variance of the row and `inv = (σ² + ε)^(-1/2)`:

```
xhat_j = (z_j - μ) · inv
y_j    = γ_j · xhat_j + β_j
```

The gains and shifts are straightforward: `∂L/∂γ_j = Σ_i dy_ij · xhat_ij` and
`∂L/∂β_j = Σ_i dy_ij`, summed over the batch. The input gradient is the interesting
one. Fix a row and write `dxhat_j = dy_j · γ_j`. Because `μ`, `var`, and therefore
`inv` all depend on every `z_k`, differentiating `xhat_j = (z_j - μ)·inv` through
those dependencies gives, after collecting terms:

```
dz_j = inv · ( dxhat_j - (1/H) Σ_k dxhat_k - xhat_j · (1/H) Σ_k dxhat_k · xhat_k )
```

which is exactly the form implemented in section 9.5 once the `inv/H` is factored
out. The two intra-row reductions `Σ_k dxhat_k` and `Σ_k dxhat_k·xhat_k` are the
`s1` and `s2` of section 9.5. This derivation assumes the **biased** variance
(division by `H`); the unbiased version (division by `H-1`) produces a different
`inv` and a `(H-1)` in place of one of the `H`s, and is *not* what this engine uses.
That single choice is why an implementation cribbed from a library that defaults to
unbiased variance will be subtly wrong even though it "implements layer norm".

### 21.2 Softmax cross-entropy VJP

With `p = softmax(zo)` and integer label `t`, the per-row loss is `-ln(p_t)`. The
Jacobian of softmax is `∂p_i/∂zo_j = p_i(δ_ij - p_j)`, and `∂L/∂p_i = -δ_it/p_t`.
Composing collapses to the well-known result `∂L/∂zo_j = p_j - δ_jt`. The batch loss
divides by `R`, so the logit gradient the reverse pass starts from is
`(p_j - δ_jt)/R`. The max-subtraction in the forward softmax cancels exactly in both
`p` and the gradient, so it affects numerical range but not the value.

### 21.3 Adam bias correction

Adam's `m` and `v` are exponential moving averages initialized at zero, so early on
they are biased toward zero. After `t` updates with constant gradient statistics,
`E[m_t] = (1-β1^t)·E[g]` and `E[v_t] = (1-β2^t)·E[g²]`, which is why dividing by
`(1-β1^t)` and `(1-β2^t)` de-biases them. The correction is largest at `t=1`
(dividing by `1-β1 = 0.1` and `1-β2 = 0.001`) and decays toward 1 as `t` grows. This
is why `t` must be carried in the checkpoint: a resumed run that restarts `t` at 1
would apply a first-step-sized correction to accumulators that are not first-step
accumulators, producing an update that is wrong by a large factor. The correction is
computed by integer powering of `β1` and `β2`; there is deliberately no running
product `β^t` accumulator, because such an accumulator would itself be state that
drifts and would have to be checkpointed.

### 21.4 Box–Muller and the two-draw rule

Given independent uniforms `u1, u2 ∈ (0,1)`, the pair
`(√(-2 ln u1)·cos 2πu2, √(-2 ln u1)·sin 2πu2)` is two independent standard normals.
We take only the cosine and discard the sine. This "wastes" half the entropy, but it
makes the draw accounting trivial and stateless: one normal is exactly two `next_u64`
calls, with nothing buffered. The alternative — cache the sine deviate for the next
call — halves the draw count but introduces two hidden state variables (the cached
value and a validity flag) that the snapshot format would have to serialize and that
the rematerialized recompute would have to restore. For a generator whose entire
selling point is one-word snapshot fidelity, a buffered spare deviate is exactly the
kind of hidden state we refuse to carry. The open-interval uniform (section 6.2)
guarantees `u1 > 0`, so `ln u1` is finite.

### 21.5 Why the rematerialized recompute is exact

The claim is that recomputing the layer-2 block during the backward pass yields bits
identical to the values the forward pass discarded. The recompute reads `D1` (which
was retained) and the parameters `W2, b2, g2, be2` (which have not changed since the
forward pass — the optimizer step happens after the backward pass), and it draws
`mask2` from a PRNG restored to the exact state the forward pass held immediately
before it drew `mask2`. Every operation — the matmul, the layer norm, the ReLU, the
mask draw, the Hadamard product — is the same code executing the same sequential
reductions over the same inputs. IEEE-754 `f64` arithmetic is a deterministic
function of its inputs and operation order, so the outputs are bit-identical, not
merely close. This is the entire argument, and it is why any deviation in operation
order (section 14) or PRNG state (section 10) breaks exactness rather than merely
perturbing it.

### 21.6 Fisher–Yates draw count

The shuffle runs `i` from `N-1` down to `1`, drawing `below(i+1)` once per `i`. That
is `N-1` draws, and because `below` uses multiply-shift with no rejection, the count
is exactly `N-1` regardless of the values drawn. This constancy is what lets us
reason about stream position across epochs (section 24.2): the shuffle always
advances the stream by `N-1`, so the only per-epoch variability in stream consumption
comes from dropout, which is where the ragged batch enters.

---

## 22. Worked micro-trace — forward

To make the pipeline concrete, here is a complete forward pass on a deliberately
tiny network: `D_in = 3`, `H1 = H2 = H3 = 4`, `C = 2`, batch of `R = 2`, with
explicit small weights and **fixed** dropout masks (so the trace does not depend on
the PRNG). All values are exact to ten places. This is illustrative; it is not the
shipped network and does not reproduce the shipped run.

Inputs and the two randomized-in-reality-but-here-fixed masks:

```
X =
  [0.5000000000, -1.0000000000, 0.2500000000]
  [1.5000000000,  0.5000000000, -0.5000000000]
y = [0, 1]
mask1 =
  [1.2500000000, 1.2500000000, 0.0000000000, 1.2500000000]
  [1.2500000000, 0.0000000000, 1.2500000000, 1.2500000000]
mask2 =
  [0.0000000000, 1.2500000000, 1.2500000000, 1.2500000000]
  [1.2500000000, 1.2500000000, 0.0000000000, 1.2500000000]
```

Weights (`W1: 3×4`, `W2: 4×4`, `W3: 4×4`, `Wo: 4×2`; biases zero, gains one, shifts
zero):

```
W1 = [[0.2,-0.1,0.3,0.0],[0.1,0.2,-0.2,0.4],[-0.3,0.0,0.1,0.2]]
W2 = [[0.1,0.2,-0.1,0.0],[0.0,0.1,0.3,-0.2],[0.2,-0.3,0.0,0.1],[-0.1,0.1,0.2,0.3]]
W3 = [[0.4,-0.2,0.1,0.3],[0.1,0.5,-0.3,0.0],[-0.2,0.2,0.4,-0.1],[0.3,-0.1,0.0,0.2]]
Wo = [[0.3,-0.2],[0.1,0.4],[-0.3,0.1],[0.2,0.0]]
```

Forward, stage by stage:

```
Z1 = X·W1 + b1 =
  [-0.0750000000, -0.2500000000, 0.3750000000, -0.3500000000]
  [ 0.5000000000, -0.0500000000, 0.3000000000,  0.1000000000]
N1 = layernorm(Z1) =
  [0.0000000000, -0.6298489803, 1.6196116637, -0.9897626834]
  [1.3867908224, -1.2662003161, 0.4220667720, -0.5426572783]
A1 = relu(N1) =
  [0.0000000000, 0.0000000000, 1.6196116637, 0.0000000000]
  [1.3867908224, 0.0000000000, 0.4220667720, 0.0000000000]
D1 = A1 ⊙ mask1 =
  [0.0000000000, 0.0000000000, 0.0000000000, 0.0000000000]
  [1.7334885280, 0.0000000000, 0.5275834651, 0.0000000000]
Z2 = D1·W2 + b2 =
  [0.0000000000, 0.0000000000, 0.0000000000, 0.0000000000]
  [0.2788655458, 0.1884226661, -0.1733488528, 0.0527583465]
N2 = layernorm(Z2) =
  [0.0000000000, 0.0000000000, 0.0000000000, 0.0000000000]
  [1.1281352284, 0.5972480621, -1.5263006032, -0.1990826874]
A2 = relu(N2) =
  [0.0000000000, 0.0000000000, 0.0000000000, 0.0000000000]
  [1.1281352284, 0.5972480621, 0.0000000000, 0.0000000000]
D2 = A2 ⊙ mask2 =
  [0.0000000000, 0.0000000000, 0.0000000000, 0.0000000000]
  [1.4101690356, 0.7465600776, 0.0000000000, 0.0000000000]
Z3 = D2·W3 + b3 =
  [0.0000000000, 0.0000000000, 0.0000000000, 0.0000000000]
  [0.6387236220, 0.0912462317, -0.0829511197, 0.4230507107]
A3 = gcube(Z3) = Z3³/3 =
  [0.0000000000, 0.0000000000, 0.0000000000, 0.0000000000]
  [0.0868595709, 0.0002532349, -0.0001902591, 0.0252380637]
Zo = A3·Wo + bo =
  [0.0000000000,  0.0000000000]
  [0.0311878852, -0.0172896461]
P = softmax(Zo) =
  [0.5000000000, 0.5000000000]
  [0.5121170099, 0.4878829901]
per-row loss = [0.6931471806, 0.7176796764]
mean loss    = 0.7054134285
```

Note the first row's activations are almost entirely zeroed: its layer-1 dropout
mask killed the one surviving ReLU output, so `D1` for row 0 is all zeros and stays
zero downstream, and its logits are `[0, 0]` giving `p = [0.5, 0.5]` and the
`ln 2 = 0.6931…` loss. This is the kind of degenerate-but-legal batch the engine has
to handle without special-casing.

---

## 23. Worked micro-trace — backward

Continuing the same micro configuration, the reverse pass. `R = 2`, so the softmax
gradient carries a `1/2`.

```
dZo = (P - onehot(y)) / R =
  [-0.2500000000,  0.2500000000]
  [ 0.2560585050, -0.2560585050]
gWo = A3ᵀ·dZo =
  [ 0.0222411319, -0.0222411319]
  [ 0.0000648430, -0.0000648430]
  [-0.0000487175,  0.0000487175]
  [ 0.0064624209, -0.0064624209]
dA3 = dZo·Woᵀ =
  [-0.1250000000,  0.0750000000,  0.1000000000, -0.0500000000]
  [ 0.1280292525, -0.0768175515, -0.1024234020,  0.0512117010]
dZ3 = dA3 ⊙ Z3² =
  [ 0.0000000000,  0.0000000000,  0.0000000000,  0.0000000000]
  [ 0.0522318208, -0.0006395733, -0.0007047640,  0.0091654556]
gW3 = D2ᵀ·dZ3 =
  [0.0736556964, -0.0009019065, -0.0009938363, 0.0129248417]
  [0.0389941922, -0.0004774799, -0.0005261487, 0.0068425633]
  [0.0000000000,  0.0000000000,  0.0000000000, 0.0000000000]
  [0.0000000000,  0.0000000000,  0.0000000000, 0.0000000000]
gb3 = [0.0522318208, -0.0006395733, -0.0007047640, 0.0091654556]
dZ2 (after dropout, ReLU, and layer-norm backward) =
  [0.0000000000,  0.0000000000,  0.0000000000,  0.0000000000]
  [0.0593880565, -0.0479644470,  0.0305526414, -0.0419762509]
gW2 = D1ᵀ·dZ2 =
  [0.1029485147, -0.0831458187, 0.0529626534, -0.0727653495]
  [0.0000000000,  0.0000000000, 0.0000000000, 0.0000000000]
  [0.0313321567, -0.0253052492, 0.0161190684, -0.0221459759]
  [0.0000000000,  0.0000000000, 0.0000000000, 0.0000000000]
dZ1 =
  [0.0000000000,  0.0000000000,  0.0000000000,  0.0000000000]
  [-0.0636289762, -0.0231337439, 0.1099076593, -0.0231449392]
gW1 = Xᵀ·dZ1 =
  [-0.0954434643, -0.0347006159, 0.1648614890, -0.0347174088]
  [-0.0318144881, -0.0115668720, 0.0549538297, -0.0115724696]
  [ 0.0318144881,  0.0115668720,-0.0549538297, 0.0115724696]
layer-3 group norm ‖(gW3, gb3)‖ = 0.0998747277
```

The `dZ3 ⊙ Z3²` step is where the amplification would live on a real batch: here
`Z3` is small so `Z3²` shrinks the gradient, but with the shipped `W3` init scale the
layer-3 pre-activations are frequently large enough that `Z3²` inflates `dZ3` past
the clip threshold (section 13). On this micro batch the layer-3 group norm is well
under any reasonable threshold, so no clip would fire; on the shipped run it fires on
several steps.

---

## 24. RNG stream reference

### 24.1 Extended test vectors (seed 1234)

The first sixteen `next_u64` outputs:

```
0xbb0cf61b2f181cdb  0x97c7a1364df06524  0x33befae49bc025da  0x4e6241f252d0a033
0xb912e3ff44b145a5  0xb0bfb29e8c72a511  0x7ecc3291b0181b9e  0x3a465f3f8f9ce09f
0x5d68bec608091483  0xcd49a5f64e0a1d63  0x1aa2ee45d0fed26f  0x49176295acb013b7
0xc89c2df590251255  0x997416e6cdf652c8  0xf354cb1188af27e6  0xec4b47848450e0ff
```

The first eight normals (each two draws):

```
-0.661067313513  -0.618260263428  -0.294526492334   0.166019076944
 0.454934664877  -0.470766660294  -0.566412366838   0.282059205829
```

`below(n)` for several bounds, each a fresh generator at seed 1234, ten draws:

```
below(2)  : 1 1 0 0 1 1 0 0 0 1
below(3)  : 2 1 0 0 2 2 1 0 1 2
below(10) : 7 5 2 3 7 6 4 2 3 8
below(16) : 11 9 3 4 11 11 7 3 5 12
below(50) : 36 29 10 15 36 34 24 11 18 40
```

### 24.2 Stream-position algebra

Because every primitive has a fixed draw count, the stream position after any prefix
of the run is computable in closed form. Initialization draws `2·(8·16 + 16·16 +
16·16 + 16·4) = 1408` `next_u64` calls (704 normals). Each epoch then draws `49` for
the shuffle and `32·50 = 1600` for dropout — `1649` per epoch — because the batch
sizes `16,16,16,2` sum to `50` and each example draws `H1 + H2 = 32` dropout
uniforms:

```
stage            stream position at start   draws
init             0                          1408
epoch 0 shuffle  1408                       49
epoch 0 dropout  1457                       1600
epoch 1 shuffle  3057                       49
epoch 1 dropout  3106                       1600
epoch 2 shuffle  4706                       49
epoch 2 dropout  4755                       1600
epoch 3 shuffle  6355                       49
epoch 3 dropout  6404                       1600
end              8004
```

The whole run consumes `8004` `next_u64` calls. If an implementation's dropout draw
count for an epoch is not `1600`, its epoch-`e+1` shuffle starts at the wrong row of
this table and produces a different permutation. Dropping the ragged batch removes
`2·32 = 64` draws per epoch; padding it to a full sixteen adds `14·32 = 448`. Either
way the table above no longer holds from the next shuffle onward.

### 24.3 Epoch permutations (shipped seed 0xC0FFEE123)

These are the four per-epoch permutations produced by the correct handling
(shuffle of all 50 indices, then the exact `1600` dropout draws before the next
shuffle). They are the single most useful self-check for stream fidelity: if your
epoch-1 permutation does not match, your ragged-batch handling or your dropout draw
count is wrong, and it will be wrong in exactly the way that diverges the checkpoint
and resume runs a few steps later.

```
epoch 0: 22 49 42 18 29 24 20 21 30 12 8 6 10 23 16 15 14 38 11 46 40 37 13 39 5
         1 33 43 7 48 47 3 34 32 31 28 19 44 26 4 27 25 41 45 36 0 9 2 35 17
epoch 1: 27 21 35 28 33 14 43 46 23 41 48 12 22 31 29 16 7 30 5 4 24 0 25 17 37
         49 39 40 47 13 34 38 19 11 8 6 3 42 10 32 44 9 1 20 26 36 45 18 15 2
epoch 2: 32 9 35 10 41 2 40 42 18 16 0 49 28 7 23 38 11 31 48 27 3 26 47 12 24
         39 21 22 4 5 19 13 15 30 8 6 45 14 20 36 1 37 17 43 44 25 46 33 34 29
epoch 3: 31 35 20 6 45 25 1 17 32 5 9 49 13 10 4 37 34 3 2 33 46 19 12 24 47
         16 41 0 8 36 27 38 30 43 44 48 15 26 7 39 22 21 18 40 11 42 23 29 28 14
```

The batch decomposition of each is `[0:16], [16:32], [32:48], [48:50]` — three full
batches and the two-element ragged batch.

---

## 25. Snapshot and hash worked examples

### 25.1 FNV-1a-64 spot values

The hash is seeded at `0xcbf29ce484222325`; each byte XORs in and then multiplies by
`0x00000100000001B3` (wrapping in `u64`). Spot values:

```
fnv1a64(empty)                         = 0xcbf29ce484222325
fnv1a64("CKPTAD01")                    = 0xe6af87775393e93d
fnv1a64(rng_state 0xC0FFEE123, 8 LE)   = 0x3e60e3f2f86028a2
```

The last line is `rng_state_hash` for a snapshot whose PRNG state is `0xC0FFEE123`:
serialize the `u64` little-endian (`23 E1 EF 0C 0C 00 00 00`) and hash those eight
bytes. Change any byte of the state and the hash changes completely, which is what
lets a test confirm the fingerprint actually depends on the PRNG state.

### 25.2 Snapshot size

For the shipped network the parameter tensors hold, in canonical order,
`128 + 16 + 16 + 16 + 256 + 16 + 16 + 16 + 256 + 16 + 64 + 4 = 820` floats, so
`W = 820·8 = 6560` bytes. With `N = 50` samples the permutation region is
`50·8 = 400` bytes. A snapshot is `8` (magic) `+ 8` (step) `+ 8` (adam_t) `+ 8`
(rng_state) `+ 6560` (weights) `+ 6560` (m) `+ 6560` (v) `+ 400` (permutation)
`+ 8` (checksum) `= 20120` bytes. A file of any other length for this network is
malformed and the loader rejects it before training. The `hash` subcommand, by contrast, reads fields
without checking the trailing checksum, so it can fingerprint a snapshot whose
optimizer or PRNG region has been deliberately edited — the mechanism a reviewer uses
to confirm each component hash responds only to its own region.

### 25.3 Component-hash sensitivity

Given a valid snapshot, three edits demonstrate the three component hashes:

- Zero the `m` and `v` regions (leaving weights, `adam_t`, and `rng_state`
  untouched): `weights_hash` and `rng_state_hash` are unchanged; `optimizer_state_hash`
  changes.
- Overwrite the eight `rng_state` bytes: `weights_hash` and `optimizer_state_hash`
  are unchanged; `rng_state_hash` changes.
- Perturb one weight byte: `weights_hash` changes; the other two do not.

A `checkpoint_hash` (the per-step full-state fingerprint in the `steps` table)
changes under any of the three edits, because it spans all three regions. An
implementation whose `checkpoint_hash` failed to change when only the optimizer or
PRNG region changed would be hashing the wrong subset (section 19.7).

---

## 27. Design rationale and alternatives considered

This chapter records the decisions that shaped the engine and, more importantly, the alternatives we rejected. None of these choices are arbitrary, and none of them are about taste. Every one of them is downstream of a single non-negotiable property: a rematerialized run and a non-rematerialized run must produce bit-identical results for the entire training trajectory, and a run resumed from a checkpoint must be indistinguishable from the run that was never interrupted. Read this chapter as a defense of that property. Where a "better" engineering answer exists in the abstract, we chose the worse one because the better one could not be made bit-exact, or could not be made bit-exact cheaply enough to trust. The failure catalogue in section 19 is the empirical backing for most of what follows; several of these decisions are scar tissue.

### 27.1 PRNG: a single-word SplitMix64

The generator is the load-bearing wall of the whole determinism story, because dropout is the only stochastic op and its behavior is fully determined by the PRNG state at the moment the mask is drawn. Everything else in the forward pass is a pure function of weights and data. So the question "can we reproduce this run" reduces almost entirely to "can we snapshot and restore the generator with perfect fidelity." We chose SplitMix64: a single 64-bit word of state, advanced by a fixed additive increment (the golden-ratio increment, see section 6) and finalized by a fixed avalanche mixer. The state *is* one `u64`. That is the entire point.

Consider what snapshotting means under rematerialization (section 10). When we drop the layer-2 activations to save memory and later recompute them, the recompute must reproduce the *same dropout masks* the original forward pass drew. That is only possible if we captured the generator state at the block boundary and can rewind to it exactly. With a single-word generator, "capture the state" is a `u64` copy and "restore" is a `u64` assignment. There is no serialization, no framing, no question of whether we captured all of it. The snapshot is total by construction because the state has no parts.

Now walk through the alternatives:

**Mersenne Twister.** Its state is a 624-word array plus an index into that array. To snapshot it you must copy all 625 quantities and, critically, get the index right. The index is exactly the kind of thing that gets dropped on the floor: it is easy to serialize the array and forget the position, at which point you have a generator that produces a valid-looking but wrong sequence, and the wrongness only shows up several draws later when the reload crosses a refill boundary. MT also has a costly reseed and a large cache footprint that we do not want to snapshot on every checkpoint. Nothing about MT's statistical quality is relevant to us — we are not doing Monte Carlo integration, we are drawing dropout masks — so we would be paying the full snapshotting hazard for a quality we do not consume.

**PCG with a larger state, or any generator carrying a separate stream/increment selector.** PCG is a fine generator, and a fixed-increment PCG would actually be snapshot-friendly. But the moment you reach for PCG you are tempted by its per-stream increment, and a multi-field state reintroduces the "did we capture every field" problem. Larger state buys us statistical properties we do not need at the cost of the one property we cannot compromise. We would rather have a generator we can hold entirely in a register and reason about with no ambiguity.

**OS RNG (`getrandom`, `/dev/urandom`).** Disqualified on sight. It is not reproducible even in principle. There is no state to snapshot; there is no "replay." An engine whose thesis is bit-exact replay cannot draw its only stochastic input from an unrepeatable source. This one is not a tradeoff, it is a category error, and it is listed only because someone always asks.

**Per-layer independent streams.** Superficially attractive: give each dropout site its own generator so the layers are decoupled and reordering one does not perturb another. We rejected it for two reasons. First, it multiplies the snapshot surface: now there are N generator states to capture and restore at every boundary, and the resume path must reconstruct all of them in the right order — exactly the multi-field hazard we are trying to eliminate, just spread across sites. Second, and more subtly, independent streams *hide* stream desync bugs rather than exposing them. With a single shared generator, the draw order across the whole run is one totally ordered sequence; if the ragged final batch (section 11) causes the forward pass to draw a different number of masks than the reference, the shared stream slips and the divergence is loud and immediate. That is a feature. We *want* stream fidelity to be a single global property that any desync violates, not a per-site property that can drift quietly in one stream while the others look fine.

**SIMD / buffered RNGs (xoshiro-with-batch-fill, the vectorized generators).** These are the fast ones, and speed is genuinely tempting because dropout mask generation is not free. They are disqualified by their buffer. A batch-filling generator maintains, in addition to its logical state, a buffer of already-generated outputs and a cursor into that buffer. The *logical* state is snapshottable; the buffer-plus-cursor is exactly the Mersenne-Twister index problem wearing a faster jacket. If you snapshot only the logical state, restore refills the buffer from a different phase and your masks are wrong. If you snapshot the buffer too, you have made the snapshot large and coupled it to the generator's internal batching, which is an implementation detail we refuse to pin into the checkpoint format. Any generator whose observable output depends on hidden buffered state is unsnapshottable in the strict sense we require, and "strict" is the only sense that matters here.

One more hazard deserves naming because it is the classic one: **the cached spare normal deviate.** Box–Muller and the polar method generate normals in pairs and stash the second one for the next call. A generator that does this has a hidden boolean ("do I have a spare?") and a hidden `f64` (the spare's value) that are part of its reproducible state and are almost never serialized. We sidestep the entire problem: the normal generator discards its second deviate rather than caching it (section 6), so there is never a spare to lose. If a future op needs Gaussian noise, it must use a method with no retained deviate, and that constraint is a hard rule, not a preference.

The summary judgment: we are not choosing a generator for its output quality, we are choosing it for the triviality of its snapshot. SplitMix64's state is one word, its transition is a fixed increment, and there is nothing else to lose. Every rejected option loses on snapshot fidelity, and snapshot fidelity is the product.

### 27.2 Autodiff representation: a hand-rolled statically-shaped reverse pass

We considered three broad designs for the backward pass and chose the least glamorous one on purpose.

The rejected options first. A **generic dynamic graph** built from `Rc<RefCell<Node>>` is the textbook flexible autodiff: each node holds references to its parents, gradients accumulate through shared mutable cells, and the graph shape is discovered at runtime. It is also a determinism minefield in a language like Rust. The ownership story is the problem. `Rc` means shared ownership, which means drop order is determined by reference-count arithmetic, which means the order in which node buffers are freed depends on the exact topology of sharing at runtime. In most programs that is invisible. In an engine that must be bit-identical between two execution modes, any behavior that depends on drop order is a latent divergence, because rematerialization changes the lifetime and sharing pattern of the very tensors involved. We would be asking the reference-counting runtime to promise us determinism it never promised. On top of that, `RefCell` moves borrow checking to runtime, so aliasing mistakes become panics discovered during a long training run instead of compile errors, and the graph's allocation pattern — when nodes are created and dropped — becomes an emergent property of traversal rather than something we control.

An **operator-overloading tape** (record every primitive op into a growing tape as arithmetic executes, then walk the tape backward) is cleaner than the `Rc<RefCell>` graph and is what many define-by-run frameworks do. But it introduces its own nondeterminism vectors: the tape's growth triggers reallocations whose timing depends on capacity heuristics, and a naive tape fights the borrow checker constantly because recording an op wants to borrow its inputs while they are still live in the forward computation. Working around that friction pushes you back toward interior mutability, and we are right back to reasoning about hidden state. The tape also obscures rematerialization: to recompute a checkpointed block you must replay a *segment* of the tape, and segmenting a linear tape at exactly the right boundary — while preserving the PRNG draw count — is fiddlier than it sounds.

We chose a **hand-rolled reverse pass over statically-shaped cached tensors.** The shapes are known ahead of time (this is not a general framework; it trains one architecture, section 1), so the forward pass writes the exact intermediate tensors that backward will read, and the backward pass is straight-line code that reads those cached tensors and computes each op's vector-Jacobian product (VJP, see the glossary in section 28) in a fixed, hand-written order. There is no graph to traverse, so there is no traversal-order ambiguity. There is no reference counting, so there is no drop-order effect on anything. There is no hidden allocation surprise, because the buffers are the tensors the forward pass already produced. The whole reverse pass is a function you can read top to bottom and predict exactly.

This pays off enormously for rematerialization. Because the reverse pass is explicit code and the forward pass caches exactly the tensors backward consumes, "recompute the layer-2 block" is just "call the block's forward again from the retained boundary tensor with the retained PRNG state, repopulating those tensors, then run the block's backward as usual." There is no tape segment to identify and no graph subregion to isolate. The rematerialized and non-rematerialized paths run the *same backward code* over tensors that were populated either by the original forward or by the recompute; by construction they cannot diverge, because there is only one backward implementation and it does not know or care how its inputs got there. That property — one backward, two ways to fill its inputs, provably identical — is the reason this design was chosen, and it is worth every bit of the flexibility we gave up. We do not need to differentiate arbitrary user programs. We need to differentiate exactly one, bit-exactly, twice.

The cost is honest: adding an op means hand-writing its forward, its cache decision, and its VJP, and getting the reductions right (section 28.4). We accept that cost. The alternative designs make adding an op easier and make being correct harder, and correctness is the deliverable.

### 27.3 Rematerialization granularity: per-layer, at the layer-2 block

Rematerialization trades compute for memory by discarding activations and recomputing them in the backward pass. The design axis is granularity, and the two extremes are both wrong.

**Checkpoint nothing** is the default non-rematerialized mode. It keeps every activation live, so there is no recompute and no memory win. It exists, and it is the reference against which the rematerialized mode is validated (section 28.1) — that is its whole job. As a memory strategy it is not a strategy.

**Checkpoint everything** — retain only inputs, recompute every activation during backward — is the opposite error. It reclaims the maximum memory but recomputes the entire forward pass a second time, and for this architecture the layer-2 block is where the activation memory actually concentrates while the other layers are cheap to keep resident. Recomputing the cheap layers buys almost no memory and costs real time; it is paying the compute tax on activations that were never the problem. Worse, every recomputed stochastic site is another place the PRNG replay must line up, so "checkpoint everything" maximizes not just compute but the surface area of the determinism obligation for no proportional memory return.

So we checkpoint **per-layer, specifically the layer-2 block**, because that is where the memory is and because the block has a clean boundary: a single tensor flows in and a single tensor flows out, and the block's internal activations are exactly what we want to drop. The granularity follows the memory profile, not a general policy.

The mechanism is the part people get wrong, so it is worth stating precisely. Recompute must be driven from **two** retained quantities, not one. The obvious one is the **boundary tensor**: the block's input, which we keep live so we can re-run the block's forward. The non-obvious one is the **PRNG state as of the block's entry**, which we snapshot (a `u64`, per 27.1) at the same instant. Without the retained PRNG state, the recompute would draw *fresh* dropout masks, producing a different masked activation than the original forward and therefore a different gradient — a silent divergence that step-0 testing will not catch because step 0 might not even exercise the ragged path. With both the boundary tensor and the entry PRNG state retained, the recompute is a pure function of retained data and reproduces the original block exactly, masks included. This is the concrete reason 27.1 obsesses over snapshot fidelity: rematerialization is snapshot-and-replay, and the generator is what gets replayed.

The tradeoff in the abstract: we spend one extra forward evaluation of the layer-2 block per step to avoid holding that block's activations resident across the entire backward pass. Memory saved is the block's activation footprint; compute added is the block's forward cost. We took that trade only where the ratio is favorable, which is why the granularity is per-block and not per-op or whole-model. The rule for future blocks is in section 28.4: rematerialization status is a deliberate per-op decision, made by weighing that block's activation footprint against its recompute cost, and never a default.

### 27.4 Optimizer epsilon placement: outside the sqrt, because the reference says so

Adam adds a small epsilon to the second-moment term to avoid division by zero (section 12). There is a genuine and well-worn debate about whether epsilon belongs *inside* the square root (added to the second moment before rooting) or *outside* (added to the root). Both are defensible; the two forms differ numerically and produce different updates; papers and implementations disagree.

We are not going to relitigate that debate, because for this engine it is the wrong debate. Epsilon goes **outside the sqrt** for one reason: that is where the reference implementation puts it. This is a compatibility decision, not a quality decision. The reference trajectory (section 12) is *pinned*, and the engine's contract is to reproduce it bit-for-bit. Under that contract, a mathematically superior epsilon placement is still a bug, because it produces a different number than the reference, and "different from the reference" is the definition of failure regardless of which value is more principled.

This framing generalizes to every constant in the optimizer and beyond: bias-correction ordering, the sequence of moment updates, whether we correct-then-divide or divide-then-correct. None of these are open questions. They are pinned by the reference, verified by the independent recomputation (section 28.1), and changing any of them — even to something "better" — is a regression. The engineering value here is not the placement itself; it is the discipline of treating the reference as ground truth and refusing to "improve" it in place. Improvements happen by re-pinning the reference deliberately, with a version bump and a full revalidation, never by a quiet code edit that happens to be more correct in the abstract.

### 27.5 Float determinism: sequential f64 reductions, no parallelism

Floating-point addition is not associative. `(a + b) + c` and `a + (b + c)` can differ in the last bits, and once they differ the divergence compounds through every subsequent step. This single fact dictates a cluster of decisions that look like performance sabotage and are actually the core of the product.

We do **sequential** reductions. Every sum — every dot product, every norm, every mean, every gradient accumulation — is performed left to right in a fixed, defined order (section 14). We do not use tree reduction, we do not use pairwise summation, we do not use any order that a parallel scheduler would pick. The order is part of the specification. Two runs reduce in the same order and therefore get the same bits.

Consequently we **forbid rayon** and any data-parallel reduction in the numeric core. A parallel sum splits the range across threads, sums each chunk, and combines — and the combination order depends on how the work was partitioned and on thread scheduling, which is not reproducible. Even deterministic-looking parallel reductions with a fixed chunking are a hazard, because the chunk boundaries become part of the numeric result and any change to thread count or chunk size silently changes the trajectory. The safe rule is total: the reduction that feeds a gradient or a parameter update runs on one thread in one order. Parallelism is allowed only where it cannot touch a reduction order that affects results, and in practice that carve-out is small enough that we treat the numeric core as single-threaded and do not apologize for it.

We equally forbid **hashmap-order accumulation.** Summing values by iterating a `HashMap` folds the hasher's iteration order — which is randomized per process by default — into the numeric result. This is the most insidious version of the associativity problem because it looks like ordinary code and passes every same-process test, then diverges across processes. Any accumulation over a collection must iterate a structure with a defined order (a `Vec`, a sorted key list), never a hash-ordered one. This rule is in the failure catalogue (section 19) because we shipped it once.

The performance tension is real and we resolve it in one direction without hedging: reproducibility wins outright for this component. The engine is a correctness instrument first. If sequential f64 reductions make a step slower, the step is slower. We are not building the fastest trainer; we are building one whose two execution modes agree to the last bit, and you cannot have that if the scheduler gets a vote on your arithmetic.

Finally, **f64, not f32.** Two reasons. First, headroom: the unstable cubic activation in layer 3 (section 8) produces large intermediate magnitudes that the global-norm clip then reins in, and f32 would lose precision in exactly that regime, making the clip's behavior sensitive to rounding in a way that threatens reproducibility across compilers and platforms. Wider mantissa means the pre-clip values and the clip decision are computed with margin. Second, storage fidelity: f64 round-trips exactly through SQLite's REAL column (27.6), so the numbers we compute are the numbers we store are the numbers we compare, with no lossy narrowing anywhere in the chain. f32 would force a precision decision at the storage boundary and reintroduce a place for two runs to disagree. f64 end to end removes that decision.

### 27.6 Storage: SQLite, driven by emitted SQL

Training telemetry — per-step losses, gradient norms, and state fingerprints — goes into a SQLite database (section 17), and this was a deliberate choice over the usual candidates.

A **flat log, CSV, or JSON** would all "work" in the sense that they can hold the numbers. What they cannot do is express the correctness properties. The properties we actually check are relational: *for every step, the rematerialized run's fingerprint equals the non-rematerialized run's fingerprint*; *for every step at or after the resume point, the resumed run matches the uninterrupted run*. Those are joins — on step, across run variants — and a relational store lets us write them as queries that read like the property they verify. In a flat log the same check is an ad-hoc script that re-implements a join by hand, and the script is now another thing that can be wrong. Expressing a correctness property in SQL, against foreign-keyed tables, means the store's own structure enforces part of the invariant. If a run is missing a step, or a fingerprint references a run that does not exist, a foreign key catches it as a structural error at insert time rather than as a confusing null in a downstream analysis. The schema is a checker.

The **on-disk REAL type round-trips an f64 exactly**, which is why the storage choice is entangled with the f64 decision in 27.5. A double written to a REAL column and read back is the same double, bit for bit. This means fingerprints and losses survive the store without perturbation, and a cross-run comparison in SQL is comparing the exact computed values, not reconstructions of them. A text format would either serialize doubles to decimal (lossy unless you are very careful with round-trip formatting) or to hex (defeating the point of a human-inspectable log), and either way introduces a conversion where none is needed.

The one non-obvious sub-decision is that we **emit SQL text to the `sqlite3` command-line tool** rather than linking a database library into the engine. The engine produces a stream of SQL statements; the tool applies them. The reason is offline build simplicity: linking a SQLite library means vendoring a C dependency, compiling it, and pinning it, which complicates a build we want to keep pure-Rust and hermetic. By treating the database as an external tool we invoke, the engine has no C in its dependency graph, the build stays trivial to reproduce, and the storage layer is decoupled from the engine's compilation entirely. The emitted SQL is also independently inspectable and replayable — you can read exactly what the engine intended to write — which is itself a debugging affordance. The cost is that we hand-build SQL text and must be disciplined about it, but the statements are simple inserts against a fixed schema, and the idempotent-rewrite property (section 28.5) keeps re-emission safe.

### 27.7 Checkpoint format: flat little-endian blob with a trailing checksum

A checkpoint must capture everything needed to resume bit-identically: parameters, both optimizer moment buffers, the step counter, and the PRNG state (section 15). We serialize this as a **flat little-endian binary blob with a fixed field order and a trailing checksum**, and we rejected every self-describing serialization framework for it.

A **serialization framework** (serde-with-some-format, protobuf, messagepack, anything self-describing) buys schema evolution, tagged fields, and forgiving parsers. We want none of that here, and some of it is actively dangerous. The checkpoint is not an interchange format for third parties; it is an internal snapshot whose shapes are fixed and known (this trains one architecture). A self-describing format spends bytes and code on describing shapes we already know statically, and — worse — its flexibility means a subtly wrong checkpoint can still *parse*, deserializing into plausible-but-wrong tensors that resume into a divergent run. We would rather a structural mistake be impossible to represent than be represented and silently accepted.

The flat format makes structural mistakes loud. Fields are written in a **fixed order tied to the known shapes**: the scalar header, then this many parameter words, then first-moment words, then second-moment, in an order the reader hard-codes. There is no framing, no tags, no lengths to get out of sync — the reader knows the shapes from the architecture and reads exactly that many values. If the writer and reader disagree about layout, the numbers land in the wrong slots and the resume diverges immediately, which the resume-equivalence check (section 28.1) catches on the first compared step. **Little-endian** is fixed rather than native so a checkpoint is portable across hosts without an endianness negotiation that could itself be wrong.

The **trailing checksum** guards against truncation and corruption: a checkpoint that was partially written (crash mid-save) or bit-rotted on disk fails the checksum on load rather than resuming from garbage. This matters specifically because a corrupted checkpoint that happened to parse would produce a divergence that looks like a determinism bug in the engine when it is actually a storage failure — the checksum keeps those two failure classes distinct, which the failure catalogue (section 19) treats as separate concerns for good reason. The checksum's algorithm and position are specified in section 15; the design point here is only that there is one and it is checked on every load, unconditionally.

### 27.8 Ragged-batch policy: process at true length

The dataset size is deliberately not a multiple of the batch size, so every epoch ends on a short, ragged final batch (section 11). There are three standard responses and we chose the one that preserves the stream.

**drop_last** — discard the ragged batch — is the common default and is wrong for us. It changes which examples the model sees per epoch and, more importantly for our purposes, it changes the *number of stochastic draws per epoch*, because the dropped batch's dropout masks are never drawn. That silently shifts the PRNG stream relative to the reference, and since the reference does not drop the last batch, every run would desync at the first epoch boundary. Dropping data to make the arithmetic tidy trades a real correctness property for cosmetic uniformity.

**Padding** the ragged batch up to full size is worse in a subtle way. It draws dropout masks for the padding rows, consuming PRNG state on examples that do not exist, and it feeds fabricated inputs through the unstable layer-3 activation and the clip, perturbing the global norm with values that are not real data. You then have to mask the padding back out of the loss and the gradient, and every one of those mask-out steps is a place to get the bookkeeping wrong. Padding converts a size problem into an accounting problem and expands the PRNG draw count with fictitious rows — exactly the stream perturbation we are trying to avoid.

We **process the ragged batch at its true length.** The final batch is smaller, the loop handles a variable batch dimension, and the number of examples and therefore the number of dropout draws is exactly the real count — no more, no less. The justification is **stream fidelity, not statistics.** We are not claiming processing-at-true-length gives a better gradient estimate (it might or might not; that is not the argument). The argument is that it is the only policy under which the PRNG draw count per epoch equals the reference's, so the shared generator stream (27.1) stays in lockstep across the epoch boundary and into the next epoch. This is why section 28.2 makes testing *past the first epoch boundary* mandatory: the ragged batch is where drop_last and padding would desync, and it is the single most important place to prove that our policy did not. Handling a variable trailing batch is more code than dropping or padding it. It is the code that keeps the stream honest, so it is the code we write.

## 28. Operating, testing, and evolving the engine

This chapter is the operational counterpart to section 27. It tells you how to convince yourself a change is safe, where the landmines are when you edit the core files, and how to extend the engine without breaking the properties that are its reason to exist. Treat it as a checklist you are not allowed to shortcut. The recurring theme is that this engine's bugs are almost all *downstream* bugs — they surface after many steps, at epoch boundaries, or only in one of the execution modes — so the intuitions you brought from ordinary software, where a passing smoke test means something, will mislead you here.

### 28.1 The layered safety checks

There is no single test that proves a change is safe. There are four checks, layered, and a change is safe only when all four pass. Each catches a different class of failure and none subsumes the others.

**Rematerialized versus non-rematerialized agreement, across the whole run.** Run the same configuration twice, once with layer-2 rematerialization on and once off, and assert the per-step losses, gradient norms, and fingerprints (28.6) are identical for *every step to the end of the run*, not just at the start. This is the flagship property from sections 1 and 10. The critical word is "whole." Step-0 agreement proves almost nothing: at step 0 the rematerialized and non-rematerialized paths have barely diverged in state, the ragged batch has not happened yet, and the PRNG replay has not been stressed. The bugs live downstream — a mask that gets redrawn on recompute, a moment buffer that accumulates in a different order, an epoch boundary that desyncs one mode's stream. If your test asserts only early agreement, it will pass while the engine is broken. Assert to the end.

**Resume versus uninterrupted, from the resume step onward.** Run a configuration straight through to the end and record its per-step numbers. Then run the same configuration but checkpoint partway, tear the process down, resume from the checkpoint, and assert that from the resume step to the end the resumed run matches the uninterrupted run exactly. This exercises the checkpoint format (section 15) and, crucially, the PRNG-state restore — a resume that reloads parameters but mis-restores the generator word will match for zero steps and then diverge. Note the asymmetry with the first check: here you compare from the resume step forward, because before the checkpoint the two runs are the same run.

**Same-mode rerun determinism.** Run the identical configuration twice in the identical mode and assert bit-identical rows throughout. This sounds trivial and it is the check that catches the environmental nondeterminism from 27.5: a hashmap-order accumulation, a stray parallel reduction, a platform-dependent transcendental. If this check fails, the problem is not in your algorithm, it is that something in the numeric path is taking a vote from the scheduler or the hasher. This is the cheapest check and the one that catches the most embarrassing bugs.

**Independent reference recomputation.** The above three checks prove the engine agrees *with itself* across modes. They do not prove it computes the *right* thing. The fourth check recomputes the reference trajectory by an independent route — a separate, deliberately simple implementation that does not share code with the engine's hot path — and asserts the engine matches it. This is what pins epsilon placement (27.4), bias-correction order, and every other constant against ground truth rather than against the engine's own possibly-wrong opinion. Without this check the engine could be perfectly self-consistent and uniformly wrong.

The mental model: the first three checks prove *consistency*, the fourth proves *correctness*. Consistency without correctness is a reproducible bug. All four, to the end of the run, or the change is not safe.

### 28.2 Test past the first epoch boundary. Always.

This has its own section because it is the single most common way a change passes review and ships broken. The dataset size is not a multiple of the batch size (sections 5, 27.8), so the first epoch ends on a ragged batch, and the ragged batch is where the PRNG stream is most likely to desync. A test that runs fewer steps than one full epoch never touches the ragged batch, never crosses into the second epoch, and therefore never exercises the exact code path that a stream-fidelity bug lives in.

What specifically breaks there: any change that alters the number of dropout draws on the final batch — a drop_last that sneaks in, a padding that draws masks for fake rows, an off-by-one in the ragged length calculation — leaves the shared SplitMix64 stream at the wrong position when the second epoch begins. From that point every mask in every subsequent epoch is drawn from the wrong state, and all four checks in 28.1 diverge. But only if the test runs long enough to get there. A within-first-epoch test sees a perfectly clean stream and a green check, because the desync happens *at* the boundary the test stopped short of. The rule is absolute: every determinism test runs at least two full epochs, so it crosses the ragged batch and validates that the second epoch's stream picked up exactly where the reference's did. If a test is too slow to run two epochs, make the dataset smaller — but keep it non-divisible by the batch size, or you have tested the wrong thing.

### 28.3 Blast radius of the core files

Four files carry the determinism contract. Editing them is not like editing feature code; each has a blast radius that extends across the whole product, and the discipline for touching them differs by file.

**rng.rs** has the largest blast radius because dropout is the only stochastic op and every reproducibility property flows through the generator. A change here can desync every run against the reference and against every prior checkpoint simultaneously. The specific hazard is that any alteration to the generator's transition, its seeding, or the number of times it is advanced per step changes the entire trajectory from that point on, and *invalidates every existing checkpoint*, because a resumed checkpoint replays the old stream into the new generator. Touch rng.rs only with a deliberate decision to re-pin the reference (27.4) and re-baseline checkpoints, never casually. The snapshot/restore functions in particular must remain a total copy of the single word (27.1); if anyone adds state to the generator, the snapshot must capture all of it or rematerialization and resume both break silently.

**tape.rs** — the reverse pass — has a blast radius bounded by the ops it differentiates, but within that scope a mistake is a wrong gradient, which corrupts every subsequent step. The hazard specific to this file is caching: the forward pass must cache *exactly* the tensors backward reads (27.2), and the rematerialized recompute must repopulate those exact tensors. An edit that changes what is cached, or the order of gradient accumulation, changes the numbers. Because there is only one backward implementation shared by both execution modes, a bug here is at least *consistent* across modes — it will pass the rematerialized-versus-non check while failing the independent-reference check, which is precisely the signature that points you at tape.rs rather than at the rematerialization machinery.

**optimizer.rs** has a blast radius of the entire parameter trajectory but is the most localized to diagnose, because its bugs preserve the forward pass. If a fingerprint diverges while the loss at that step still matches (28.6), the parameters or moment buffers are wrong while the forward computation on the old parameters was right — that is an optimizer or PRNG-state signature, and optimizer.rs is the first place to look. The pinned constants (epsilon placement, bias correction) live here and must never be "improved" in place (27.4).

**checkpoint.rs** has a blast radius limited to resume, but resume is half the product. The hazards are the fixed field order and the trailing checksum (27.7). An edit that reorders fields, changes a width, or forgets to serialize a piece of state (the PRNG word and the step counter are the usual casualties) produces checkpoints that either fail the checksum or resume into divergence. The discipline: any change to what state exists must be reflected in checkpoint.rs *in the same change*, and the resume-equivalence check (28.1) must be run before the change is trusted, because a missing field is invisible until you resume across it.

### 28.4 Adding a new op without breaking determinism

Adding an op to the engine is a hand-written exercise (27.2), and there are exactly three things you must get right, in this order.

First, **all reductions inside the op are sequential f64, left to right, in a defined order** (27.5). No rayon, no tree reduction, no accumulation over a hash-ordered collection. If the op sums anything — and most do — the summation order is part of its specification and must be identical every time it runs. This is the rule that a new op is most likely to violate, because the fast way to write a reduction is the parallel way, and the fast way is forbidden here.

Second, **the forward pass caches exactly what backward needs, and nothing it does not.** Work out the op's VJP on paper, determine which forward tensors the VJP reads, and cache precisely those. Caching too little means backward recomputes or, worse, reads a stale value; caching too much wastes the memory that rematerialization exists to reclaim. The VJP itself is hand-written straight-line code with its own sequential reductions, subject to the same first rule.

Third, **decide the op's rematerialization status deliberately** (27.3). Every op is either resident (its activations are kept) or rematerialized (dropped and recomputed from a boundary tensor plus the entry PRNG state). This is a per-op decision weighed on that op's activation footprint against its recompute cost, and it defaults to nothing — an op is not rematerialized unless someone decided it should be and wired up the boundary-tensor and PRNG-snapshot retention. If the op is stochastic, its rematerialization status interacts with the stream: a rematerialized stochastic op *must* replay from a retained generator state or its recompute draws fresh masks and diverges. Getting this wrong is invisible at step 0 and loud two epochs in, which is why 28.1 and 28.2 exist.

After adding an op, run all four checks in 28.1 to at least two epochs. A new op is a change to tape.rs and possibly rng.rs draw counts; treat it with the blast-radius discipline of 28.3.

### 28.5 Adding a run mode or a column

The database (section 17) encodes cross-run invariants as relational queries, and two kinds of extension threaten them.

**A new run mode** — a fourth execution variant alongside the existing ones, say — must slot into the cross-run comparison without breaking the join structure. The invariant is that comparable runs share a step axis and are joined on step across variants (section 17). A new mode must emit the same per-step rows keyed the same way, or the comparison queries that verify agreement will either silently exclude it or produce spurious mismatches. The rule: a new mode adds *rows*, distinguished by a run id, never a new *shape* of row. If the new mode needs to be checked for agreement against the reference, it participates in the same fingerprint join as everyone else. And it is subject to 28.1 in full — a new mode is a new thing that must agree with the non-rematerialized reference to the end of the run and across a resume.

**A new column** must preserve the **idempotent-rewrite property.** The engine's writes are structured so that re-emitting a run's telemetry produces the same database state — running the same configuration twice, or re-applying the emitted SQL (27.6), does not duplicate or conflict, because rows for a run are replaced wholesale rather than appended. A new column must respect that keying: it must be a function of the same key (run, step) so that a rewrite overwrites rather than duplicates, and it must have a defined value for existing rows or the schema change breaks the foreign-key structure that catches structural mistakes. A column whose value depends on something outside the (run, step) key, or that is nullable in a way that lets two rewrites produce different database states, silently breaks idempotence, and idempotence is what makes re-running safe. Add the column, backfill or default it, and verify that emitting the same run twice leaves the database byte-identical.

### 28.6 Debugging a divergence

When two runs that should agree do not, do not read code first. Localize first, then read. The procedure is a bisection in two dimensions: by step, then by subsystem.

**Bisect by step.** You have two runs and a per-step fingerprint (28.7) for each. Find the *first* step whose fingerprints differ. Everything before it is identical and irrelevant; everything after it is downstream contamination and equally irrelevant. The entire bug lives in the transition from the last-agreeing step to the first-diverging step. This is the highest-leverage move in the whole debugging process, because it converts "the runs differ somewhere in many steps" into "the runs differ in this one step's computation." Compare state fingerprints, not losses, to find this step — a fingerprint captures the full state (28.7) and diverges as soon as *anything* does, whereas a loss can coincidentally match while state has drifted.

**Localize to a subsystem** using the signature of the divergence. This is where the loss-versus-fingerprint distinction pays off. At the first diverging step, compare the loss too:

- If the **fingerprint diverges and the loss also diverges at the same step**, the forward pass on this step's parameters already disagreed, so the bug is upstream in the forward computation — a wrong activation, a mask drawn from a desynced stream, a reduction order. Look at tape.rs forward, rng.rs, or the data stream.
- If the **fingerprint diverges but the loss at that step still matches**, the forward pass agreed but the *state* did not — the parameters or moment buffers were updated differently while the forward computation on the pre-update parameters was identical. That points at **optimizer state or PRNG state**, not the forward pass (28.3). This is the single most useful heuristic in this section: a fingerprint/loss split localizes the bug to the update, not the compute, and sends you straight to optimizer.rs or the generator's per-step advance rather than into the forward code where you would waste hours.

Once you know the step and the subsystem, *then* read code, and read it under the blast-radius lens of 28.3. Most divergences resolve to one of the catalogued failures in section 19 — a redrawn mask on recompute, a ragged-batch desync, a hashmap accumulation, a missing checkpoint field — and the bisection tells you which before you have read a single line.

### 28.7 Fingerprints

Everything above leans on fingerprints, so here is what they are. A fingerprint is a compact, order-sensitive digest of the full training state at a step — parameters, moment buffers, step counter, and PRNG word — computed by a hash over a canonical serialization of that state (section 15) and stored per step in the database (section 17). It is the observable that the safety checks compare and the coordinate the divergence bisection searches. It is designed to diverge the instant *any* component of state diverges, which is why it, and not the loss alone, is a primary comparison signal: the loss is one scalar and can coincide by luck; the fingerprint covers the whole state and does not. When you assert two runs "agree," you mean their per-step fingerprints are identical for every step in the compared range.

### 28.8 Glossary

**Rematerialization** — dropping activations during the forward pass and recomputing them during the backward pass to save memory, at the cost of a second forward evaluation of the dropped region (sections 10, 27.3). Also called gradient checkpointing.

**Tape** — here, the hand-rolled reverse pass over statically-shaped cached tensors (27.2). Not a dynamic record-and-replay tape; the term is retained by convention for the structure that carries the backward computation.

**VJP (vector–Jacobian product)** — the operation a single op contributes to the backward pass: given the gradient flowing in from its output, produce the gradient flowing to its inputs, without ever forming the full Jacobian. Each op's backward is its VJP (27.2, 28.4).

**Ragged batch** — the short final batch of an epoch, arising because the dataset size is not a multiple of the batch size; processed at its true length, not dropped or padded (sections 11, 27.8).

**Inverted dropout** — the dropout convention where the scaling by the keep probability is applied at training time on the kept units, so inference needs no rescaling; the stochastic op whose masks the PRNG draws (section 8).

**Bias correction** — the Adam step that compensates the moment estimates for their initialization at zero, applied in a pinned order (sections 12, 27.4).

**Global-norm clip** — gradient clipping that scales a gradient group by a single factor derived from its norm, used to tame the unstable layer-3 cubic activation without altering the activation itself (sections 13, 27.5).

**Snapshot** — a total capture of a piece of reproducible state, restorable to bit-exactness; for the PRNG it is the single `u64` word, for a checkpoint it is the flat blob (sections 6, 15, 27.1, 27.7).

**Fingerprint** — the per-step order-sensitive digest of full training state used as a comparison signal in the safety checks and the coordinate in divergence bisection (28.7).

---

# Part III — Reference

Part III is the lookup material: the public surface of each module, a worked
optimizer trace, the acceptance criteria, the revision history, and the
environment notes. It repeats nothing from Parts I and II; it is what you consult
while implementing rather than what you read to understand.

## 29. Module and function reference

This is the contract each module owes the rest of the engine. Signatures are given
in the obvious Rust shapes; the point is the pre/postconditions, not the syntax.

### 29.1 `rng.rs`

- `Rng::new(seed: u64) -> Rng` — construct with the given state. No mixing is
  applied to the seed; the first `next_u64` advances it once (section 6.1).
- `Rng::next_u64(&mut self) -> u64` — one SplitMix64 step. Advances the state by
  exactly one golden-ratio increment. This is the unit in which all draw counts
  are denominated.
- `Rng::uniform_open(&mut self) -> f64` — one draw; result in the open interval
  `(0, 1)` (section 6.2).
- `Rng::below(&mut self, n: u64) -> u64` — one draw; uniform integer in `[0, n)`,
  no rejection (section 6.3).
- `Rng::normal(&mut self) -> f64` — two draws; one standard normal, sine companion
  discarded (section 6.4).
- `Rng::state(&self) -> u64` / `Rng::set_state(&mut self, s: u64)` — the snapshot
  primitives. Postcondition: `set_state(state())` is a no-op, and after
  `set_state(v)` the next draw equals what it would have been when `v` was
  captured. Everything about rematerialization and resume rests on this pair.

Invariant for the whole module: the observable output is a pure function of the
current state word. No hidden buffers, no cached deviates, no lazy fields.

### 29.2 `tensor.rs`

- `Mat { rows, cols, data: Vec<f64> }` — dense row-major; element `(i, j)` at
  `data[i*cols + j]`.
- `Mat::zeros(rows, cols)`, `Mat::from_vec(rows, cols, data)` — constructors;
  `from_vec` asserts `rows*cols == data.len()`.
- `Mat::matmul(&self, &Mat) -> Mat` — `self` is `r×k`, other is `k×c`; the inner
  product over `k` accumulates left-to-right into an `f64` seeded at `0.0`. This
  reduction order is normative (section 14).
- `Mat::transpose(&self) -> Mat` — used to form `Xᵀ·Y` and `Y·Wᵀ` as
  `matmul(transpose(X), Y)`.
- `Mat::add_row_bias(&mut self, &[f64])` — broadcast-add a length-`cols` bias.
- `Mat::col_sums(&self) -> Vec<f64>` — length-`cols` column sums, accumulated over
  rows in order (bias gradients and `dβ`).
- `Mat::sq_sum(&self) -> f64` — sum of squares over the flat data in order (norms).

The module contains no randomness and no I/O; it is pure arithmetic with pinned
reduction order.

### 29.3 `ops.rs`

- `layernorm_fwd(z: &Mat, gamma: &[f64], beta: &[f64], eps: f64) -> (Mat, LnCache)`
  — returns the normalized-and-affine output and the cache `(xhat, inv, gamma)`
  needed by backward. Biased variance (section 8.2).
- `layernorm_bwd(dy: &Mat, &LnCache) -> (Mat, Vec<f64>, Vec<f64>)` — returns
  `(dz, dgamma, dbeta)` (section 9.5).
- `relu_fwd(&Mat) -> Mat`, `relu_bwd(dy: &Mat, a: &Mat) -> Mat` — backward gates on
  `a > 0` where `a` is the ReLU output.
- `unstable_fwd(&Mat) -> Mat`, `unstable_bwd(z: &Mat, da: &Mat) -> Mat` — the
  layer-3 activation `z³/3` and its VJP `da·z²`.
- `hadamard(&Mat, &Mat) -> Mat` — elementwise product (dropout apply and dropout
  backward).
- `softmax_ce(logits: &Mat, targets: &[usize]) -> (f64, Mat)` — returns the mean
  cross-entropy and the logit gradient `(p - onehot)/R`.

Every reduction inside these functions (the layer-norm mean/variance, the softmax
denominator, the backward sums `s1`/`s2`) is sequential and in index order.

### 29.4 `tape.rs`

- Spec constants (`H1..H3`, `EPOCHS`, `DROPOUT_P`, `LR`, `BETA1`, `BETA2`, `EPS`,
  `LN_EPS`, `CLIP_TAU`, the four init sigmas) live here as `pub const`.
- `Params` — the twelve parameter tensors in canonical order, with `tensors()` /
  `tensors_mut()` returning them as a uniform array, and `Params::init(rng, d_in,
  c)` performing the draw-ordered initialization (section 7). Reused as the
  gradient and moment container.
- `Tape` — the forward activation record: the layer-1 cache always, the layer-2
  cache only when not rematerialized, plus `rng_pre` (the PRNG state before
  `mask2`).
- `forward(&Params, &Mat, &mut Rng, remat: bool) -> Tape` — computes the full
  forward, drawing `mask1` then `mask2`; retains the layer-2 block iff `!remat`.
  Postcondition: the PRNG has advanced by `R·(H1+H2)` draws regardless of `remat`.
- `backward(&Params, &Tape, dlogits: &Mat, &mut Rng, remat: bool) -> Grads` — the
  reverse pass. When `remat`, recomputes the layer-2 block with the PRNG restored
  to `rng_pre` and then restored to its live value; net PRNG advance is zero
  (section 10.2).
- `clip_layer3(&mut Grads) -> f64` — clips the layer-3 group in place, returns the
  pre-clip norm (section 13).
- `global_norm(&Grads) -> f64` — post-clip global L2 norm in canonical order.

### 29.5 `optimizer.rs`

- `Adam { m: Params, v: Params, t: u64 }` — moment buffers (canonical layout) and
  the shared update counter.
- `Adam::new(d_in, c) -> Adam` — zeroed moments, `t = 0`.
- `Adam::step(&mut self, &mut Params, &Grads)` — increments `t`, then applies the
  outside-epsilon update elementwise in canonical order (section 12).

### 29.6 `dataset.rs`

- `parse_scalars(path) -> HashMap<String, String>` — the tiny TOML-subset reader
  (inline comments, quoted strings, hex/decimal ints, floats).
- `load_manifest(path) -> Manifest` — `{ num_samples, input_dim, num_classes,
  batch_size }`.
- `load_seed(path) -> u64`, `load_resume_step(path) -> usize`.
- `load_data(inputs, targets, n, d) -> Data` — reads the blobs, asserts the exact
  byte lengths, returns `{ x: Mat, y: Vec<usize> }`. A wrong length is an error.

### 29.7 `checkpoint.rs`

- `fnv1a64(&[u8]) -> u64`, `hex16(u64) -> String` — the fingerprint primitives.
- `weights_hash(&Params)`, `optimizer_hash(&Adam)`, `rng_hash(u64)`,
  `full_hash(&Params, &Adam, u64)` — the four fingerprints over their respective
  byte serializations (section 15.4).
- `save(path, step, rng_state, &Params, &Adam) -> Result<(), String>` — writes the
  snapshot blob with trailing checksum (section 15.2).
- `load(path, d_in, c) -> Result<Snapshot, String>` — validates magic, checksum,
  and exact length before returning; any failure is an `Err`. `load_lenient` skips
  only the checksum, for the `hash` subcommand.

### 29.8 `dbwriter.rs`

- `write_run(db_path, &RunReport) -> Result<(), String>` — emits the DDL and a
  delete-then-insert transaction for the run to the `sqlite3` tool. Losses and
  gradient norms are formatted `%.17e`. Idempotent per `run_id`.

### 29.9 `report.rs` and `main.rs`

- `report.rs` holds `StepRow`, `CheckpointRow`, `RunReport`, and a one-line
  summary printer.
- `main.rs` parses the CLI (section 18), loads config and data, drives the loop
  for the training modes, and dispatches `hash`. It creates `out/` and the snapshot
  directory as needed and returns a nonzero exit on any error without leaving a
  partial run in the database.

## 30. Worked optimizer trace

A single scalar parameter, starting at `θ = 1.0`, driven by an illustrative
gradient sequence, under the pinned Adam (`lr 0.01`, `β1 0.9`, `β2 0.999`, `ε 1e-8`,
epsilon outside). This is not from the shipped run; it isolates the optimizer.

```
t |   g   |      m       |      v       |    m̂        |     v̂       | sqrt(v̂)+ε |   update   |     θ
1 | +0.80 | +0.080000000 | 0.0006400000 | +0.8000000 | 0.640000000 | 0.8000000 | +0.01000000 | 0.990000000
2 | -0.20 | +0.052000000 | 0.0006793600 | +0.2736842 | 0.339849925 | 0.5829665 | +0.00469468 | 0.985305318
3 | +0.05 | +0.051800000 | 0.0006811806 | +0.1911439 | 0.227287425 | 0.4767467 | +0.00400934 | 0.981295980
4 | +0.40 | +0.086620000 | 0.0008404995 | +0.2518755 | 0.210440315 | 0.4587378 | +0.00549062 | 0.975805358
5 | -0.10 | +0.067958000 | 0.0008496590 | +0.1659495 | 0.170271996 | 0.4126403 | +0.00402165 | 0.971783706
6 | +0.02 | +0.063162200 | 0.0008492093 | +0.1348010 | 0.141889134 | 0.3766818 | +0.00357864 | 0.968205063
```

Two things to read off it. First, at `t = 1` the update is exactly `lr = 0.01`
because `m̂ = g` and `sqrt(v̂) = |g|`, so `m̂ / (sqrt(v̂) + ε) ≈ 1` up to the
`ε` in the denominator — this is the sign-descent behavior Adam has on the first
step, and it is a quick sanity check that bias correction and epsilon placement are
right. Second, the denominator `sqrt(v̂) + ε` is where the epsilon-inside variant
would differ: had we written `sqrt(v̂ + ε)`, every denominator in the table would
shift by a hair, and for a parameter whose `v̂` was near zero the shift would be
large (section 12.1). Reproduce this table before trusting an optimizer change.

## 31. Acceptance criteria

The engine is correct when all of the following hold. Each is established either by an
independent recomputation of the expected values or by a comparison of the relevant
rows across the run variants in the database.

1. The crate builds offline against the standard library only.
2. Each of the three training modes runs to completion and writes its rows.
3. For every step, the checkpoint-mode loss and gradient norm equal the
   nocheckpoint-mode values (bit-exact).
4. For every step, both modes' loss and gradient norm equal the independent
   reference within a tight tolerance, including across the first epoch boundary.
5. The resumed run's steps from the resume point onward equal the uninterrupted
   run's corresponding steps (bit-exact), and equal the reference's resume tail.
6. A snapshot captures weights, both Adam moment sets, `adam_t`, and the PRNG state;
   this is observable because resume reproduces the uninterrupted trajectory, which
   is impossible if any of those are missing.
7. The layer-3 pre-clip gradient norm exceeds `τ` on the steps where the reference
   says it does, and the recorded post-clip global norm equals the reference's
   clipped norm — not an unclipped or an architecturally-altered value — and is
   never NaN or infinite.
8. The recorded step count equals `epochs × batches_per_epoch`, confirming the
   ragged batch was neither dropped nor padded.
9. `PRAGMA integrity_check` is `ok` and `PRAGMA foreign_key_check` is empty; the
   schema matches the DDL; the resume run's `resumed_from` is the checkpoint run.
10. Two runs of the same mode with the same seed produce identical rows.
11. The three component hashes each respond only to their own state region, and the
    full-state `checkpoint_hash` responds to all of them.
12. A truncated or corrupt snapshot causes a nonzero exit with no partial run
    written.

## 32. Revision history

- **rev 7 (this document).** Split into the specification (Part I), the derivations
  and worked examples (Part II), and the reference (Part III). Added the module API
  contracts and the acceptance criteria. No behavior change.
- **rev 6.** Pinned the Adam epsilon placement to *outside* the square root and the
  layer-3 clip threshold to its current value, after two regressions were traced to
  "equivalent" rewrites that were not bit-equivalent. Added section 12.1.
- **rev 5.** Documented the ragged-last-batch rule and its interaction with the PRNG
  stream across epoch boundaries (section 11), after a checkpoint saved mid-run
  failed to resume correctly and the cause turned out to be an epoch-boundary
  desync introduced three epochs earlier by a `drop_last`.
- **rev 4.** Introduced the per-step full-state `checkpoint_hash` and the three
  component hashes (section 15.4), replacing a weights-only fingerprint that could
  not distinguish states differing only in optimizer or PRNG state.
- **rev 3.** Moved rematerialization from "checkpoint everything" to the per-layer
  layer-2-block schedule (section 10) after profiling showed the other layers were
  cheap to keep resident; formalized the PRNG save/restore discipline around the
  recompute.
- **rev 2.** Replaced the `Rc<RefCell<Node>>` dynamic graph with the hand-rolled
  statically-shaped reverse pass (section 27.2) after a determinism bug was traced
  to drop-order-dependent behavior.
- **rev 1.** Initial engine: forward/backward MLP, Adam, SQLite telemetry, no
  rematerialization and no resume.

## 33. Environment, build, and portability notes

- **Toolchain.** The crate targets stable Rust and uses only the standard library.
  There are no external crates, so the build needs no registry access and no
  vendoring; `cargo build --release --offline` works in a sealed environment. This
  is a deliberate consequence of the storage decision in section 27.6 — by shelling
  to the `sqlite3` tool rather than linking a database library, the dependency graph
  is empty and the build is trivially reproducible offline.
- **The `sqlite3` tool.** The engine invokes the `sqlite3` command-line binary to
  apply its emitted SQL. The tool is expected on `PATH`. If it is absent the
  database write fails and the run exits nonzero, which is the correct behavior — a
  run that cannot record its results has not succeeded.
- **Determinism across hosts.** All arithmetic is `f64` and all reductions are
  sequential (section 14), so the numbers do not depend on core count, vector width,
  or thread scheduling. The one portability caveat is the transcendental functions
  (`ln`, `cos`, `exp`, `sqrt`): these come from the platform math library, and while
  `sqrt` is correctly rounded everywhere, the others can differ by a bit across
  libraries. Within a single host and library they are deterministic, so same-host
  reruns and the rematerialized-versus-non comparison are bit-exact; the independent
  reference comparison uses a tolerance precisely to absorb any cross-library
  last-bit differences in the transcendentals, which are far smaller than any real
  bug.
- **Little-endian assumption.** The dataset blobs and the snapshot format are
  little-endian (sections 5, 15.2). The engine reads and writes little-endian
  explicitly rather than using native byte order, so a checkpoint written on one
  host loads on another without an endianness handshake.
- **Memory and time.** The network and dataset are tiny by design; a full run is a
  few dozen steps over 16-wide layers and completes in well under a second. The
  point of the engine is not throughput but the reproducibility properties, so the
  scale is chosen to make the tests fast while still forcing every ragged batch and
  every epoch boundary the properties depend on. Keep the dataset non-divisible by
  the batch size if you resize it (section 28.2).
- **Output layout.** The engine writes `out/runs.db` and, in checkpoint mode,
  `out/snap/step_NN.bin` snapshots (with `NN` zero-padded to two digits, e.g.
  `step_08.bin`; see section 18). `out/` is runtime state, not part of the
  repository, and is recreated as needed. Nothing in `out/` is an input to a later
  run except the snapshots a resume explicitly loads.

---

# Part IV — Formats, analysis, and appendices

## 34. Dataset blob format, byte by byte

The dataset is two flat little-endian blobs plus the manifest that describes them.
There is no header, no length prefix, no framing — the manifest's `num_samples`,
`input_dim`, and the fixed dtypes tell the reader exactly how many bytes to consume.

`train_inputs.bin` is `num_samples × input_dim` binary64 values in row-major order:
example 0's `input_dim` features, then example 1's, and so on. With the shipped
shape (`50 × 8`) that is `3200` bytes. The first thirty-two bytes are the first four
features of example 0:

```
5d 6c 13 8e f6 6d e3 bf   08 51 a6 a0 dc ac d5 bf
3b f5 5b d4 4d a4 f0 3f   ae 77 f7 a7 0b cd d4 3f
```

decoding (little-endian `f64`) to:

```
-0.6071732306403522  -0.3386756485790703  1.0401132865220706  0.3250149860667716
```

`train_targets.bin` is `num_samples` little-endian signed 64-bit integers, one class
label per example in `[0, num_classes)`. With the shipped shape that is `400` bytes.
The first three labels are:

```
01 00 00 00 00 00 00 00   03 00 00 00 00 00 00 00   02 00 00 00 00 00 00 00
```

that is, labels `1, 3, 2` (the first six are `1, 3, 2, 1, 1, 3`).

The reader must validate the lengths — `num_samples · input_dim · 8` for the inputs
and `num_samples · 8` for the targets — and reject anything else. A blob of the
wrong length is not a dataset to be salvaged; it is a configuration error, and
loading a truncated blob and training on whatever bytes happened to be there is
exactly the kind of silent corruption the length check exists to prevent. Labels are
read as signed 64-bit and must be non-negative and less than `num_classes`; a
negative or out-of-range label is an error.

Endianness is fixed at little-endian rather than native so the blobs are portable.
The engine reads with an explicit little-endian decode, not by reinterpreting bytes
in host order, so the same blob decodes identically on any host.

## 35. Complexity and memory analysis

The network is tiny, so absolute cost is irrelevant; the analysis matters only
because it justifies *where* rematerialization is applied (section 10) and *why* the
schedule is per-layer rather than global.

Per step, for a batch of `R` rows, the four linear layers cost (in multiply-adds):

```
layer      matmul shape      MACs (R=16)
L1 linear  R × 8  × 16       2048
L2 linear  R × 16 × 16       4096
L3 linear  R × 16 × 16       4096
out linear R × 16 × 4        1024
```

plus the elementwise layer-norm, ReLU, dropout, and activation passes, each `O(R·H)`.
The backward pass roughly doubles the matmul cost (each linear contributes a
weight-gradient matmul and an input-gradient matmul), and rematerialization adds one
more forward evaluation of the layer-2 block, i.e. one extra `R × 16 × 16 = 4096`-MAC
matmul plus its elementwise ops. That extra ~4k MACs per step is the entire compute
cost of rematerialization here.

The memory side is what the schedule optimizes. Each layer's activation is `R·H`
`f64`, i.e. `16 · 16 · 8 = 2048` bytes for a hidden layer at `R = 16`. The layer-2
block, if kept resident for the backward pass, retains its intermediate tensors —
`Z2`, the layer-norm cache, `A2`, `mask2`, `D2` — on the order of `5 · R · H2` `f64`,
about `10240` bytes at this scale. Rematerializing the block trades that retained
footprint for the one `u64` (`8` bytes) of retained PRNG state plus the boundary
tensor `D1` (which is retained anyway, since it is layer 1's output). On this toy the
saving is bytes; on the real network the layer-2-analogue blocks dominate activation
memory, and the same trade saves a meaningful fraction of the activation footprint
for one extra block-forward of compute. That ratio — large retained footprint, cheap
recompute — is exactly the condition under which rematerialization pays, and it is
why the schedule targets that block and leaves the cheap-to-retain layers resident
(section 27.3).

The snapshot's size is dominated by the three parameter-sized regions (weights, `m`,
`v`): `3 · Σ|θ| · 8` bytes plus the `40`-byte header and checksum and the `N·8`
permutation. For the shipped network that is `3 · 820 · 8 + 400 + 40 = 20120` bytes
(section 25.2). Adam's two moment buffers are the reason a snapshot is roughly three
times the weight size, and they are non-negotiable payload: dropping them to shrink
the file is the weights-only
checkpoint failure (section 19.1).

## 36. Numerical considerations

Several small choices exist purely to keep the arithmetic well-behaved without
perturbing reproducibility.

**Softmax max-subtraction.** The softmax subtracts each row's maximum logit before
exponentiating (section 8.6). This prevents `exp` overflow when logits are large —
and layer 3's cubic activation can make logits large — while leaving the softmax
probabilities and the loss mathematically unchanged, because the subtracted constant
cancels in the ratio. It changes the numerical range, not the value. Omitting it
risks `inf` from `exp` on the exact batches the unstable layer is designed to
produce.

**Layer-norm epsilon.** The `1e-5` added inside the square root (section 8.2) keeps
the normalization finite when a row's variance is near zero — which happens, for
instance, when a dropout mask has zeroed most of a row so the surviving values are
nearly constant. It is inside the root and added to the variance, a placement pinned
for the same reason the Adam epsilon placement is pinned: a different placement is a
different number.

**The cubic activation and the clip.** `z³/3` has no bound and its derivative `z²`
grows quadratically, so on batches where layer 3's pre-activations are a few units in
magnitude the gradient flowing back is tens of units. In `f64` these values are far
from overflow — `f64` reaches ~`1.8e308` — so the forward and backward computations
are exact; the danger is not overflow but an update large enough to destabilize
training. That is precisely what the layer-3 global-norm clip addresses (section 13):
it bounds the *update* by rescaling the gradient group, without touching the forward
values or the activation's shape. This is why `f64` matters here (section 27.5): the
wide mantissa computes the large pre-clip values and the clip decision with margin,
so the clip behaves identically regardless of platform. In `f32` the pre-clip
magnitudes would lose low-order precision and the clip boundary would become
rounding-sensitive.

**Inverted-dropout scale.** The kept units are scaled by `1/(1-p) = 1.25` at train
time (section 8.4). This keeps the expected activation magnitude constant so no
inference-time rescaling is needed, and it is applied on the mask, so the backward
pass — which multiplies by the same mask — inherits the scale automatically.

**Bias-correction powers.** `β1^t` and `β2^t` are computed by integer powering, not
by a running product (section 21.3). A running product would be additional state that
drifts and would have to be checkpointed; integer powering of the pinned `β` values
by the checkpointed counter `t` is exact-enough and stateless.

## 37. Notation and symbols

```
D_in, C            input width and class count (from manifest; 8 and 4 shipped)
H1, H2, H3         hidden widths, all 16
R                  rows in the current batch (16, or 2 for the ragged batch)
N                  num_samples (50); B batch_size (16); bpe batches/epoch (4)
X                  batch input, R × D_in
W1,W2,W3,Wo        linear weights; b* biases; g*,be* layernorm gain/shift
Z*                 pre-activation (linear output); N* layernorm output
A*                 post-activation (ReLU or cubic); D* post-dropout
mask1, mask2       dropout masks (values 0 or 1/(1-p))
Zo                 logits, R × C; p softmax probabilities; y labels
gWx, gbx, ...      gradients of the correspondingly named parameters
m, v, t            Adam first moment, second moment, update counter
τ                  layer-3 clip threshold (3.0)
ε, ε_ln            Adam epsilon (1e-8), layernorm epsilon (1e-5)
inv, xhat          layernorm reciprocal-std and normalized value (backward cache)
rng_pre            PRNG state retained before mask2 for rematerialization
⊙, ᵀ, ‖·‖          Hadamard product, transpose, Euclidean norm
```

## 38. Non-goals and known limitations

This engine is a correctness instrument, and several things it deliberately does not
do are worth stating so they are not mistaken for bugs.

- **It is not fast.** Single-threaded sequential reductions, an extra block-forward
  for rematerialization, and shelling out to a database tool are all choices that
  trade speed for reproducibility or simplicity. Making it fast is a non-goal; making
  it bit-reproducible is the goal.
- **It trains one fixed architecture.** There is no model configuration surface
  beyond the manifest's data shape. The statically-shaped reverse pass (section 27.2)
  depends on this; generalizing to arbitrary graphs would reintroduce the dynamic-
  graph determinism hazards we rejected.
- **Resume is exact, not approximate.** A resume from any step, including mid-epoch,
  must reproduce the uninterrupted trajectory bit-for-bit; there is no "close enough"
  resume. Mid-epoch resume is why the snapshot carries the current epoch's permutation
  (section 16), since it cannot be re-derived from the advanced PRNG state.
- **The dataset is synthetic and fixed.** The numbers the network learns are
  meaningless; the point is the trajectory's reproducibility, not its accuracy. Do
  not read anything into the loss values beyond "they must match the reference".
- **Cross-library transcendental bit-exactness is not promised.** Same-host reruns
  and the rematerialized-versus-non comparison are bit-exact; the independent-
  reference comparison is tolerance-based to absorb `ln`/`cos`/`exp` last-bit
  differences across math libraries (section 33). Promising bit-exactness against a
  differently-compiled reference would be promising something the platform math
  library does not.

## 39. Extended test-vector appendix

Row 0 of each weight matrix after initialization from the shipped seed
`0xC0FFEE123` (the first entries; the full matrices follow the draw order of
section 7):

```
W1[0] = 0.2233087383  0.2500335658 -0.2555885362  0.2387368010 -0.2961472205  0.6630748433 ...
W2[0] = 0.0346050179  0.2009699846  0.0024714252  0.0503166121  0.3995834662  0.0645054593 ...
W3[0] = -0.1239918797 0.4860665624  0.0468852323 -0.3452711613 -0.8737658696 -0.7690526921 ...
Wo[0] = -0.4124368634 0.3561886674  0.1344532829  0.1720588776
```

Draw-count checkpoints for the shipped run, restating section 24.2 as a lookup:

```
event                     cumulative next_u64 calls
after weight init                     1408
after epoch 0 shuffle                 1457
after epoch 0 (all dropout)           3057
after epoch 1 shuffle                 3106
after epoch 1                         4706
after epoch 2 shuffle                 4755
after epoch 2                         6355
after epoch 3 shuffle                 6404
after epoch 3 (end of run)            8004
```

FNV-1a-64 anchors for implementers checking their hash:

```
fnv1a64(empty)               = 0xcbf29ce484222325
fnv1a64("CKPTAD01")          = 0xe6af87775393e93d
```

A correct implementation reproduces every number in this document. If any of the
RNG test vectors (section 24.1), the epoch permutations (section 24.3), the micro-
trace (sections 22–23), or the draw-count ledger above disagrees with your build,
fix that before looking at the loss trajectory — a disagreement here guarantees a
disagreement there, and this is the cheaper place to find it.

# Part V — Mathematical foundations and error analysis

## 44. Complete derivations

### 44.1 Layer normalization: forward and the full vector-Jacobian product

We normalize a single row `z = (z_1, …, z_H)` of width `H = 16`. The forward pass is fully specified by

- `mu   = (1/H) Σ_k z_k`
- `var  = (1/H) Σ_k (z_k − mu)^2`  (biased: the divisor is `H`, not `H − 1`)
- `inv  = (var + eps)^(−1/2)`      (`eps = 1e-5` sits *inside* the sqrt)
- `xhat_j = (z_j − mu) · inv`
- `y_j   = gamma_j · xhat_j + beta_j`

The upstream gradient is `dy_j = dL/dy_j`. We want three quantities: `dL/dgamma_j`, `dL/dbeta_j`, and the full `dL/dz_j`. The first two are immediate; the third is the whole point of the section, because `mu`, `var`, and `inv` each depend on *every* `z_k`, so `z_j` reaches the loss through `H` distinct paths, not one.

**Parameter gradients.** For a single row, `y_j` is affine in `gamma_j` and `beta_j`, and each parameter touches exactly one output coordinate:

- `dL/dgamma_j = dy_j · (∂y_j/∂gamma_j) = dy_j · xhat_j`
- `dL/dbeta_j  = dy_j · (∂y_j/∂beta_j)  = dy_j`

Because `gamma` and `beta` are shared across the batch, the implemented accumulation sums these over rows: `dL/dgamma_j = Σ_r dy_j^(r) xhat_j^(r)` and `dL/dbeta_j = Σ_r dy_j^(r)`. The reduction runs in the pinned row order of section 14; nothing about layer norm relaxes that ordering constraint.

**Setting up the input gradient.** Introduce the intermediate adjoint on the normalized activations,

```
dxhat_k := dL/dxhat_k = dy_k · gamma_k.
```

`gamma_k` is a fixed multiplier here; the `gamma`/`beta` gradients are handled above and do not re-enter. The loss depends on `z_j` only through the collection `{xhat_k}`, so by the chain rule

```
dL/dz_j = Σ_k dxhat_k · (∂xhat_k/∂z_j).                                   (1)
```

Everything reduces to computing the `H × H` Jacobian block `∂xhat_k/∂z_j`. Write `xhat_k = (z_k − mu)·inv`. Differentiating a product,

```
∂xhat_k/∂z_j = (∂(z_k − mu)/∂z_j)·inv  +  (z_k − mu)·(∂inv/∂z_j).          (2)
```

We evaluate the three constituent derivatives one at a time.

**Derivative of the mean term.** `∂mu/∂z_j = (1/H) Σ_k ∂z_k/∂z_j = 1/H`. Hence

```
∂(z_k − mu)/∂z_j = delta_kj − 1/H.                                        (3)
```

**Derivative of the variance.** With biased `var = (1/H) Σ_m (z_m − mu)^2`,

```
∂var/∂z_j = (1/H) Σ_m 2 (z_m − mu) · (delta_mj − 1/H)
          = (2/H) [ (z_j − mu) − (1/H) Σ_m (z_m − mu) ].
```

The second bracketed term vanishes identically because `Σ_m (z_m − mu) = 0` by definition of `mu`. This cancellation is not incidental — it is the reason the layer-norm backward collapses to a compact three-term form rather than carrying a residual mean-of-adjoints on the variance path. Therefore

```
∂var/∂z_j = (2/H) (z_j − mu).                                            (4)
```

**Derivative of the inverse standard deviation.** Since `inv = (var + eps)^(−1/2)`,

```
∂inv/∂z_j = −(1/2)(var + eps)^(−3/2) · ∂var/∂z_j = −(1/2) inv^3 · ∂var/∂z_j.
```

Substituting (4),

```
∂inv/∂z_j = −(1/2) inv^3 · (2/H)(z_j − mu) = −(1/H) inv^3 (z_j − mu).
```

Now use `(z_j − mu) = xhat_j / inv` to fold one factor of `inv` into `xhat_j`:

```
∂inv/∂z_j = −(1/H) inv^2 · xhat_j.                                       (5)
```

**Assembling the Jacobian block.** Substitute (3) and (5) into (2), and again rewrite `(z_k − mu) = xhat_k / inv`:

```
∂xhat_k/∂z_j = (delta_kj − 1/H)·inv  +  (xhat_k/inv)·(−(1/H) inv^2 xhat_j)
             = inv·(delta_kj − 1/H)  −  (1/H) inv · xhat_k xhat_j
             = inv · [ (delta_kj − 1/H) − (1/H) xhat_k xhat_j ].          (6)
```

**Contracting with the adjoint.** Insert (6) into (1):

```
dL/dz_j = Σ_k dxhat_k · inv · [ (delta_kj − 1/H) − (1/H) xhat_k xhat_j ]
        = inv [ Σ_k dxhat_k delta_kj − (1/H) Σ_k dxhat_k − (1/H) xhat_j Σ_k dxhat_k xhat_k ]
        = inv [ dxhat_j − (1/H) Σ_k dxhat_k − (1/H) xhat_j Σ_k dxhat_k xhat_k ].
```

Factor `1/H` out to reach the implemented form:

```
dL/dz_j = (inv/H) [ H·dxhat_j − Σ_k dxhat_k − xhat_j Σ_k dxhat_k xhat_k ],
          with dxhat_j = dy_j · gamma_j.                                 (7)
```

This is exactly the shape used in the reverse pass (section 9). Note its structure: two batch-level (row-level) reductions — the plain sum `Σ_k dxhat_k` and the projection `Σ_k dxhat_k xhat_k` — are computed once per row, then broadcast back. The first subtracts the mean adjoint (the `mu` path); the second subtracts the component of the adjoint along `xhat` (the `var`/`inv` path). Geometrically, the backward operator projects `dxhat` onto the subspace orthogonal to both the all-ones vector and `xhat`, then rescales by `inv`. This is the numerically clean statement of why layer norm is invariant to shift and scale of its input: gradients in those two directions are annihilated.

**Where the biased-variance choice enters, and how unbiased would differ.** The biased divisor `H` appears in exactly one place with observable consequence: equation (4), `∂var/∂z_j = (2/H)(z_j − mu)`. Had we used the unbiased estimator `var_u = (1/(H−1)) Σ (z_m − mu)^2`, then `∂var_u/∂z_j = (2/(H−1))(z_j − mu)`, and (5) would become `∂inv/∂z_j = −(1/(H−1)) inv^2 xhat_j`. Crucially, `mu` still divides by `H` regardless — the mean is an average of `H` numbers either way — so the `(delta_kj − 1/H)` term in (6) is *unchanged*. The two normalization constants would then disagree: the mean-subtraction path carries `1/H`, the variance path carries `1/(H−1)`. The compact factorization (7) would no longer hold with a single `inv/H` prefactor; one would instead carry two distinct coefficients, e.g.

```
dL/dz_j = inv [ dxhat_j − (1/H) Σ_k dxhat_k − (1/(H−1)) xhat_j Σ_k dxhat_k xhat_k ],
```

and the forward `inv` would itself be computed from `var_u`, changing every downstream bit. For `H = 16` the numerical gap `1/16` vs `1/15` is ~6.7% on the variance path — far above any f64 rounding tolerance and immediately fatal to bit-exact reproduction. We pin biased variance; the derivation above is the canonical one for that choice, and it is the only one that reconciles with the golden trajectory.

A parallel remark on `eps`: because it sits inside the sqrt, `inv = (var+eps)^(−1/2)` and the chain rule produced the clean `inv^3` in (5). Had `eps` sat outside — `1/(sqrt(var)+eps)` — the derivative would carry `sqrt(var)^(−1)` factors that do not fold into powers of `inv`, and (7) would not close in the implemented form. The two epsilon conventions (layer norm inside, Adam outside — see 44.4) are deliberately different and both are pinned.

### 44.2 Softmax cross-entropy VJP

Let `zlog = (z_1, …, z_C)` be a row of logits, `t` the integer target class. Define

```
S = Σ_k exp(z_k),   p_i = exp(z_i) / S,   L = −ln p_t.
```

**Softmax Jacobian.** Differentiate `p_i` with respect to `z_j`. Using the quotient rule and `∂S/∂z_j = exp(z_j)`:

```
∂p_i/∂z_j = [ (∂exp(z_i)/∂z_j)·S − exp(z_i)·∂S/∂z_j ] / S^2
          = [ delta_ij·exp(z_i)·S − exp(z_i)·exp(z_j) ] / S^2
          = delta_ij·(exp(z_i)/S) − (exp(z_i)/S)(exp(z_j)/S)
          = p_i·delta_ij − p_i·p_j
          = p_i (delta_ij − p_j).                                        (8)
```

**Loss gradient with respect to probabilities.** `L = −ln p_t` depends on the probability vector only through coordinate `t`:

```
∂L/∂p_i = −(1/p_t) · delta_it.                                           (9)
```

**Compose.** By the chain rule and (8),(9),

```
dL/dz_j = Σ_i (∂L/∂p_i)(∂p_i/∂z_j)
        = Σ_i [ −(delta_it)/p_t ] · p_i (delta_ij − p_j).
```

The `delta_it` collapses the `i`-sum to the single term `i = t`:

```
dL/dz_j = −(1/p_t) · p_t (delta_tj − p_j) = −(delta_tj − p_j) = p_j − delta_jt.  (10)
```

This is the well-known "probabilities minus one-hot" result: `dL/dz = p − e_t`. It is exact, requires no special handling of the target coordinate, and is what the reverse pass emits at the classifier head (section 9).

**Batch mean.** The reported loss over a batch of `R` rows is `L_batch = (1/R) Σ_{r=1}^R L^(r)`. Since rows are independent through the head, the `1/R` factor passes straight through:

```
dL_batch/dz_j^(r) = (1/R) ( p_j^(r) − delta_{j, t_r} ).                  (11)
```

The batch sizes are ragged — `16, 16, 16, 2` — so `R` takes the value `2` on the fourth batch of each epoch. The `1/R` uses the *true* row count of the batch (`R = 2` there), not the nominal `16`; this is the same true-length policy that keeps the PRNG stream aligned (section 11, and formally in 45.2). A `1/16` on a 2-row batch would both misscale the gradient and, more subtly, is a different arithmetic expression that would not reproduce.

**Max-subtraction cancels exactly.** For numerical safety the head computes `p_i = softmax(z − m·1)` where `m = max_k z_k`. Claim: this leaves both `p` and `dL/dz` bit-consistent with the definition, up to the deliberate rounding of the shifted exponentials. As *functions*, for any scalar `c`,

```
softmax(z − c·1)_i = exp(z_i − c) / Σ_k exp(z_k − c)
                   = (e^{−c} exp(z_i)) / (e^{−c} Σ_k exp(z_k))
                   = exp(z_i)/S = p_i.
```

The common factor `e^{−c}` cancels between numerator and denominator. This holds even though `c = m(z)` depends on `z`, because the identity `softmax(z − m(z)·1) ≡ softmax(z)` is a functional identity in `z`: subtracting a common scalar from all coordinates is an exact symmetry of softmax. Consequently the entire gradient (10) is unchanged — one does *not* need to differentiate through `m`, since the composed function is literally equal to the unshifted one. The stabilization changes only the magnitudes of the intermediate exponentials (keeping them ≤ 1, avoiding overflow), not the mathematical map. In floating point this means the shift changes *which* representable value each `exp` rounds to, but because the reference also applies the identical max-subtraction in the identical order, the two agree bit-for-bit; the cancellation is what makes the stabilization free of trajectory consequences.

### 44.3 The layer-3 activation and gradient amplification

Layer 3 uses `g(z) = z^3/3`, whose derivative is `g'(z) = z^2`. This is not a squashing nonlinearity; it is monotone, unbounded, and its slope grows without limit. The consequences for the backward pass are the subject here.

**VJP.** For a pre-activation vector `z3` and elementwise activation `a3 = g(z3)`, the upstream adjoint `da3` maps back as

```
dz3_i = da3_i · g'(z3_i) = da3_i · z3_i^2.                               (12)
```

The parameter gradient for the layer-3 weight `W3` (with input `h2`, the layer-2 output) is the outer product `dW3 = dz3 ⊗ h2`, so

```
dW3_{ik} = da3_i · z3_i^2 · h2_k.                                        (13)
```

**Amplification.** The local Jacobian of `g` is diagonal with entries `z3_i^2 ≥ 0`. Wherever `|z3_i| > 1` the coordinate *amplifies* its incoming gradient quadratically; wherever `|z3_i| < 1` it attenuates. Unlike a bounded activation (slope ≤ 1 everywhere), `z^2` has no upper bound on its multiplier, so the layer-3 gradient group is the natural place for norm spikes to originate.

**Quantitative estimate from init scale and widths.** We reason at initialization, where the pinned `sigma` values set the scale. The pre-activation is `z3 = W3 h2` (a sum over the `H2 = 16` inputs). Treating `h2` as an approximately unit-scale, roughly decorrelated vector (layer 2 is followed by normalization/activation that keep it O(1)), and `W3` entries iid with standard deviation `sigma_{W3} = 0.50`, the variance of a single pre-activation coordinate is approximately

```
Var(z3_i) ≈ H2 · sigma_{W3}^2 · Var(h2) ≈ 16 · 0.25 · O(1) ≈ 4,
```

so `std(z3_i) ≈ 2`. The elementwise backward multiplier is `z3_i^2`, whose *mean* is therefore `≈ Var(z3_i) ≈ 4`, and whose tail is heavy: a 2σ pre-activation (`|z3| ≈ 4`) contributes a multiplier `≈ 16`, and a 3σ coordinate (`|z3| ≈ 6`) contributes `≈ 36`. Across a width-16 layer and a batch, at least one coordinate landing in the tail is likely, so on some batches the group norm `‖dW3‖ = sqrt(Σ dW3_{ik}^2)` inherits a factor of order `10`–`40` relative to a group whose local Jacobian is O(1). Against the pinned clip threshold `tau = 3.0` (section 13), it is entirely expected that `‖dW3‖` exceeds `tau` on the batches where `z3` has large-magnitude entries, while the other groups — layers with O(1) slopes — sit comfortably under it. This is a per-group, per-batch phenomenon, not a runaway.

**Bounded by f64.** The same estimate shows the norm cannot overflow. Every factor in (13) is finite: `h2` is finite (finite inputs, finite weights, and the layer-2 nonlinearity does not manufacture infinities), `z3` is a finite sum of products of finite numbers, `z3^2` is at most order `10^1`–`10^2` at init, and `da3` is finite. The product of a handful of O(1)–O(100) quantities is O(10^2)–O(10^3) per element, and the group norm over 256 elements stays many orders of magnitude below the f64 ceiling `≈ 1.8×10^308`. There is headroom of hundreds of orders of magnitude. So the failure mode `g` introduces is *large-but-finite gradients*, an optimization concern, not overflow, not NaN.

**Why clipping is the correct response, and why touching `g` is not.** Clipping (section 13) is a gradient-space operation: when `‖dW3‖ > tau` it rescales `dW3 ← dW3 · (tau/‖dW3‖)`, shrinking the magnitude while preserving direction, and — importantly — leaving the forward function `g` and the loss exactly as defined. It changes the *step*, never the *model*. The optimizer still descends the same landscape; it just takes a shorter step along the same descent direction on the offending batch. Altering the activation instead — replacing `z^3/3` with, say, a scaled or saturating variant — changes the represented function `f(x; theta)`, hence the loss surface, hence every gradient, hence the golden trajectory. That would not be a bug fix; it would be a different model. The stability issue lives in the optimization dynamics, so the intervention belongs in the optimizer/gradient path, and clipping is precisely that intervention with the minimal footprint.

### 44.4 Adam: bias correction and epsilon placement, derived

Adam maintains two EMAs, both initialized at zero: `m_0 = 0`, `v_0 = 0`, and updates

```
m_t = beta1·m_{t−1} + (1 − beta1)·g_t
v_t = beta2·v_{t−1} + (1 − beta2)·g_t^2
```

with `beta1 = 0.9`, `beta2 = 0.999`. The zero initialization is the source of the bias.

**Why m and v are biased toward zero.** Unroll the first-moment recursion. Since `m_0 = 0`,

```
m_t = (1 − beta1) Σ_{i=1}^{t} beta1^{t−i} g_i.
```

Take expectations under the working assumption that the gradient is (locally) stationary, `E[g_i] = E[g]`:

```
E[m_t] = (1 − beta1) E[g] Σ_{i=1}^{t} beta1^{t−i}.
```

The geometric sum is `Σ_{i=1}^{t} beta1^{t−i} = Σ_{j=0}^{t−1} beta1^{j} = (1 − beta1^t)/(1 − beta1)`. Therefore

```
E[m_t] = (1 − beta1) E[g] · (1 − beta1^t)/(1 − beta1) = (1 − beta1^t) E[g].   (14)
```

Because `0 < beta1 < 1`, the factor `(1 − beta1^t) < 1`, so `E[m_t]` *underestimates* `E[g]` — biased toward the zero at which the EMA started. The bias is worst at small `t` (`1 − beta1^1 = 0.1`, a 10× underestimate) and decays geometrically. Identical algebra gives `E[v_t] = (1 − beta2^t) E[g^2]`, with the slower `beta2 = 0.999` making the second-moment bias persist far longer (`1 − 0.999^1 = 0.001`).

**Why dividing by `(1 − beta^t)` de-biases.** Define `mhat_t = m_t/(1 − beta1^t)` and `vhat_t = v_t/(1 − beta2^t)`. By linearity of expectation and (14),

```
E[mhat_t] = E[m_t]/(1 − beta1^t) = E[g],   E[vhat_t] = E[g^2].
```

The corrected estimators are unbiased for the (assumed stationary) targets. Operationally, at `t = 1` the correction multiplies `m_1` by `1/(1 − 0.9) = 10` and `v_1` by `1/(1 − 0.999) = 1000`, exactly undoing the shrink toward zero. This is why the very first Adam steps are not vanishingly small despite the EMAs having barely departed from zero.

The parameter update, with epsilon pinned *outside* the sqrt, is

```
theta_t = theta_{t−1} − lr · mhat_t / ( sqrt(vhat_t) + eps ),   lr = 0.01, eps = 1e-8.  (15)
```

**Epsilon placement, quantitatively.** Compare the two conventions as functions of `v ≡ vhat`:

```
f_out(v) = 1/( sqrt(v) + eps )       (pinned)
f_in(v)  = 1/ sqrt(v + eps)          (the common alternative)
```

*Large `v` (the typical regime).* Expand both to first order in `eps/v ≪ 1`. For `f_out`,

```
f_out(v) = (1/sqrt(v)) · 1/(1 + eps/sqrt(v)) ≈ (1/sqrt(v))(1 − eps/sqrt(v)) = 1/sqrt(v) − eps/v.
```

For `f_in`, using `(1 + eps/v)^(−1/2) ≈ 1 − eps/(2v)`,

```
f_in(v) = (1/sqrt(v))(1 + eps/v)^(−1/2) ≈ (1/sqrt(v))(1 − eps/(2v)) = 1/sqrt(v) − eps/(2 v^{3/2}).
```

Both share the leading `1/sqrt(v)`; the correction terms are `O(eps/v)` and `O(eps/v^{3/2})` respectively, and their difference

```
f_in(v) − f_out(v) ≈ eps/v − eps/(2 v^{3/2}) = (eps/v)(1 − 1/(2 sqrt(v)))
```

vanishes like `eps/v` as `v` grows. With `eps = 1e-8` and any `vhat` of order `1e−4` or larger, the two conventions agree to roughly 12+ significant digits — well below the level that would perturb a step in practice, though not below f64 last-bit level, which is the entire reason the choice must still be pinned.

*Small `v` (near-zero gradients).* As `v → 0` the conventions diverge sharply:

```
f_out(v) → 1/eps      = 1e8
f_in(v)  → 1/sqrt(eps) = 1/sqrt(1e−8) = 1e4.
```

The outside placement caps the per-unit-`mhat` step at `1e8`; the inside placement caps it at `1e4`. That is a factor of `1e4` difference in the maximum step size for coordinates whose second moment has collapsed toward zero. The two conventions are therefore *not* interchangeable in the small-gradient regime — precisely the regime that dominates late in training and for rarely-active units.

**Conclusion: pinned for compatibility, not superiority.** Neither placement is universally "better." Inside-sqrt is arguably the more defensible default (it keeps the denominator bounded below by `sqrt(eps)` and has a cleaner interpretation as regularizing the variance), and several mainstream frameworks use it. We nonetheless pin **outside** because the reference implementation whose golden trajectory we must reproduce uses outside, and the divergence in the small-`vhat` regime means the choice is observable — swapping it would produce a slowly compounding drift (analyzed in chapter 46), not an immediate crash. Compatibility, not merit, fixes the convention.

**Why `t` must be checkpointed.** The bias-correction denominators `(1 − beta1^t)` and `(1 − beta2^t)` are explicit functions of the global step counter `t`. Two runs that agree on `m`, `v`, and `theta` but disagree on `t` will compute different `mhat`, `vhat`, hence different updates, from the very next step. Resuming from a checkpoint with a stale or reset `t` (for instance restarting `t` at 1, or off by one) silently rescales every subsequent step — most violently in the first few resumed steps where `(1 − beta^t)` is far from 1. Therefore `t` is not derivable from `m`/`v`/`theta` and must be persisted as first-class optimizer state (sections 12 and 15). The checkpoint format stores it alongside the moment buffers for exactly this reason.

### 44.5 Box-Muller and the two-draw invariant

The PRNG (section 6) is a single-word SplitMix64. Normals are produced by the cosine branch of Box-Muller, consuming exactly two uniform draws.

**The transform.** Let `u1, u2` be iid `Uniform(0,1)`. Define

```
R     = sqrt(−2 ln u1)
theta = 2·pi·u2
Z0    = R·cos(theta)
Z1    = R·sin(theta).
```

Claim: `Z0` and `Z1` are iid standard normal.

*Derivation via the polar decomposition of a 2-D Gaussian.* Suppose `(Z0, Z1) ∼ N(0, I_2)`, joint density `(1/2π) exp(−(Z0^2 + Z1^2)/2)`. Change to polar coordinates `Z0 = r cos φ, Z1 = r sin φ`, with area element `dZ0 dZ1 = r dr dφ`. The density factors:

```
(1/2π) exp(−r^2/2) · r dr dφ = [ r exp(−r^2/2) dr ] · [ (1/2π) dφ ].
```

So `φ ∼ Uniform(0, 2π)` independently of `r`, and `r` has density `r e^{−r^2/2}` on `r ≥ 0` (a Rayleigh distribution). The radial *squared* variable `W = r^2` has, by the change `dW = 2r dr`,

```
density of W = (1/2) e^{−W/2},   W ≥ 0,
```

which is `Exponential(mean 2)` (equivalently chi-squared with 2 degrees of freedom). Now invert: to *generate* such a pair we need `W ∼ Exp(mean 2)` and `φ ∼ Uniform(0, 2π)`. Both are producible from uniforms. For the angle, `φ = 2π u2` is immediate. For the radius, note that if `u1 ∼ Uniform(0,1)` then `−2 ln u1 ∼ Exp(mean 2)`: for `x ≥ 0`,

```
P(−2 ln u1 > x) = P( ln u1 < −x/2 ) = P( u1 < e^{−x/2} ) = e^{−x/2},
```

which is exactly the `Exp(mean 2)` survival function. Hence `W = −2 ln u1` has the correct radial law, `r = sqrt(−2 ln u1) = R`, and `(R cos θ, R sin θ)` reconstructs a pair distributed as `N(0, I_2)`. The Jacobian bookkeeping is exactly the `r dr dφ` factor used above; the construction is the inverse of the polar decomposition, so it is exact, not approximate. `Z0` and `Z1` are therefore independent standard normals. ∎

**Why we discard the sine deviate.** Box-Muller naturally yields *two* normals per two uniforms. The tempting optimization is to cache `Z1` and return it on the next `normal()` call, halving uniform consumption. We deliberately do **not**: we compute `Z0` (cosine branch) and throw `Z1` away. The reason is stream discipline. Caching `Z1` introduces hidden state — a "pending gaussian" flag plus a stored f64 — that is *not* part of the SplitMix64 word. That state would have to be captured in every snapshot and checkpoint (section 15), restored on resume, and — worst of all — would make the per-normal draw count alternate `2, 0, 2, 0, …` depending on the parity of prior normal requests. Determinism of the stream *position* (the invariant of 45.2) would then depend on the entire history of how many normals had been requested, coupling unrelated code paths. By discarding `Z1`, every `normal()` consumes exactly two draws, unconditionally, and the only state is the single 64-bit word. The mapping "one normal ↔ two draws" becomes a constant, which is what makes the closed-form stream algebra of 45.2 possible. The wasted deviate is a cheap price for a stateless, snapshot-trivial generator.

**Why `uniform_open` must be strictly in `(0,1)`.** The transform evaluates `ln u1`. If `u1` could equal `0`, `ln 0 = −∞`, `R = +∞`, and `Z0 = ±∞` (or NaN through `∞·cos`), poisoning the run irrecoverably. So the generator must exclude `0`: `u1 > 0` is mandatory for finiteness. The upper end matters too but less catastrophically: at `u1 = 1`, `ln 1 = 0`, `R = 0`, and `Z0 = 0` exactly — a degenerate (though finite) deviate that biases the tail count and is not what the reference emits. We therefore pin `uniform_open ∈ (0,1)`, open at both ends: open at `0` for finiteness of `ln`, open at `1` to avoid the degenerate exact-zero radius. The cosine branch consumes `u1` first, then `u2`, in that fixed order, so the two draws are attributed deterministically.

### 44.6 Fisher-Yates: uniformity and the constant draw count

The per-epoch data shuffle (section 11) is Fisher-Yates driven by `below(n)`, the Lemire multiply-shift index generator that consumes exactly one draw and does not reject. The loop is

```
for i from N−1 down to 1:
    j = below(i+1)          # j uniform-ish in {0, 1, …, i}
    swap a[i], a[j]
```

with `N = 50`.

**Uniformity.** We prove that if `below(i+1)` were exactly uniform on `{0, …, i}`, the shuffle outputs each of the `N!` permutations with probability `1/N!`.

*Counting the choice space.* The loop makes `N − 1` independent draws; at step `i` the draw `j = below(i+1)` has `i + 1` equally likely outcomes. The total number of distinct choice-sequences is

```
∏_{i=1}^{N−1} (i + 1) = 2 · 3 · 4 · … · N = N!,
```

and each specific choice-sequence occurs with probability `∏_{i=1}^{N−1} 1/(i+1) = 1/N!`.

*Bijection between choice-sequences and permutations.* It suffices to show the map (choice-sequence) → (output permutation) is a bijection from an `N!`-element set to the `N!`-element symmetric group; then each permutation is the image of exactly one equiprobable choice-sequence and thus has probability `1/N!`. Injectivity/surjectivity follows from invertibility: given any output arrangement, reconstruct the draws backward. At the final executed step `i = 1` we swapped position `1` with position `j = below(2) ∈ {0,1}`; the value now sitting in position `1` and its provenance pin down that last draw uniquely given the pre-swap state, and so on upward. More directly, run the loop *in reverse*: for `i = 1` up to `N − 1`, the element that step `i` placed into position `i` is exactly `a[i]` in the final array (no later step `i' > i` touches position `i`, since later steps only write positions `> i` on their high end... in the descending loop, step `i` writes positions `i` and `j ≤ i`; subsequent steps use smaller `i`, so position `i` is never written again). Hence position `i`'s final occupant records which value was routed there, which determines `j` for step `i` given the array state just before step `i`; peeling from `i = N−1` downward recovers the entire draw sequence deterministically. The map is invertible, therefore bijective, therefore uniform. ∎

The key structural fact is the *fixed point* property: once step `i` writes position `i`, no later step disturbs it, so each output slot carries exactly one draw's worth of information, giving the clean `N!`↔`N!` correspondence with no collisions and no gaps.

**Constant draw count.** `below(n)` in the pinned single-multiply Lemire form computes `(rand_u64() * n) >> 64` (the high word of a 128-bit product) and consumes exactly one 64-bit draw with **no rejection loop**. Standard Lemire optionally rejects a thin residue to erase the modulo bias; the pinned variant omits that step, trading a negligible bias (of order `n / 2^64`, i.e. ~`50/2^64 ≈ 3×10^−18`, far below any observable effect) for a *deterministic* draw count. Consequently step `i` consumes exactly one draw regardless of the value it returns, and the whole shuffle consumes exactly

```
draws_per_shuffle = N − 1 = 49,
```

independent of the seed, the data, and the returned indices. The uniformity proof above idealizes `below` as exactly uniform; the single-draw variant is uniform only up to the `~10^−18` bias, which does not affect determinism (both reference and engine share the identical biased map) and is immaterial to the permutation statistics.

**Why constancy enables stream-position algebra.** Because `draws_per_shuffle` is a constant `49` — not a random variable, not data-dependent — the PRNG word offset at every epoch boundary is a closed-form function of the epoch index. Had `below` used rejection, the shuffle would consume a *random* number of draws (49 plus an occasional retry), and the stream position after epoch `e` would be a random variable, making it impossible to state where the stream "should" be or to detect a desync by position comparison. The rejection-free design is what converts stream position from an empirical quantity into an algebraic one, which is exactly what section 45.2 relies on.

## 45. Determinism invariants, stated and argued

### 45.1 The rematerialization-exactness invariant

**Statement.** Let `S_pre` be the SplitMix64 state immediately before the layer-2 dropout mask is drawn during the forward pass, and `S_post` the state immediately after that draw. Let `S_live` be the PRNG state at the moment the backward pass reaches the layer-2 rematerialization point. The remat protocol (section 10) does three things in order: (i) save `S_live`; (ii) set the PRNG to `S_pre` and recompute the layer-2 activations, including re-drawing the dropout mask, which advances the PRNG to some `S_post'`; (iii) restore the PRNG to `S_live`. The invariant asserts:

1. The recomputed layer-2 activations equal the discarded forward-pass activations **bit-for-bit**.
2. `S_post' = S_post` (the recompute's internal PRNG advance is identical to the forward's).
3. The **net** PRNG advance across the remat is zero, because step (iii) restores `S_live`.

**Argument.** By section 14, f64 arithmetic is a deterministic, total function of its inputs *under a fixed operation order*, and the recompute executes the identical op sequence as the forward pass for layer 2. The recompute is a *pure* function of exactly three inputs:

- the retained boundary tensor `D1` (the layer-1 output that was kept as the checkpoint boundary, section 15) — bit-identical because it was stored, not recomputed;
- the parameters feeding layer 2 (e.g. `W2`, its bias, `gamma`/`beta`) — bit-identical because parameter updates happen *after* the entire backward pass (section 12), so no weight has changed since the forward;
- the PRNG state — set to `S_pre`, bit-identical to the forward-time value by construction.

Three bit-identical inputs plus an identical pure op sequence yield a bit-identical output (claim 1). In particular, the dropout mask is drawn from the same starting state `S_pre` with the same Box-Muller/`below`-free per-element uniform draws (dropout draws one `uniform_open` per element), advancing to the same `S_post'`; since the draw sequence is identical, `S_post' = S_post` (claim 2). Claim 3 is immediate: whatever the recompute advanced internally, step (iii) overwrites the word with the saved `S_live`, so an external observer sees the PRNG at `S_live` both before and after the remat block — net advance zero. The discarded activations are thus reproduced exactly and the stream is left where the live computation expects it.

**The two ways to break it (section 10), and why each is invisible at step 0.**

*Break A — failing to restore `S_pre` before recompute.* The recompute then draws its dropout mask from `S_live` (or wherever the PRNG happens to be), producing a *different* mask, hence different layer-2 activations, hence a corrupted `dz` flowing back. But note what is and isn't affected at step 0: the *loss* at step 0 was produced by the forward pass, which used the correct mask and correct activations; the corrupted mask only enters the *gradient*. A gradient does not change the current loss — it changes the *next* parameter update. So at step 0 the reported loss is bit-exact with golden, and the corruption is latent in `theta_1`. It surfaces only once the wrong gradient has moved the weights and the *next* forward pass is evaluated at the perturbed `theta` (chapter 46).

*Break B — failing to restore `S_live` after recompute.* Here the recompute leaves the PRNG at `S_post'` instead of `S_live`. The activations themselves are correct (claims 1–2 hold), but every subsequent stochastic op reads from a shifted stream. If the layer-2 remat is the last dropout-related consumer before the next shuffle, the shift is exactly one mask's worth of draws; regardless, the step-0 *loss* is again untouched, because it was already computed before backward ran. The desync manifests at the next PRNG consumer — typically the next epoch's shuffle — as an altered permutation. Once more the effect is delayed: at step 0 nothing looks wrong.

Both failures share the signature: **the forward-pass loss at the injection step is bit-exact, and divergence appears only downstream.** This is precisely why step-0 (or early-step) loss comparison cannot catch remat bugs, motivating the end-of-run fingerprint tests of chapter 46 and section 19.

### 45.2 The stream-position invariant

**Statement.** Let `Pos(n)` denote the SplitMix64 word offset consumed after the run has processed the first `n` events (an event being an init draw, a shuffle, or a batch's dropout draws). Then `Pos` is a fixed, closed-form function of the seed's consumption schedule — it does not depend on any data value, gradient, or loss. Concretely, at an epoch boundary after `E` completed epochs,

```
Pos = D_init + E · ( D_shuffle + D_dropout ),                            (16)
```

where

- `D_init` = total draws consumed by parameter initialization = `2 · (|W1| + |W2| + |W3| + |Wo|)` (each normal costs two draws, section 44.5), plus any bias/aux normals, all fixed by the architecture;
- `D_shuffle = N − 1 = 49` (section 44.6), constant;
- `D_dropout` = per-epoch dropout draws = `(rows processed in the epoch) × (dropout width per row)`. Dropout draws one `uniform_open` per eligible unit, so with `50` rows processed per epoch (batch sizes `16+16+16+2`) and dropout applied at fixed hidden widths, `D_dropout = 50 · W_drop` for the effective dropout width `W_drop`, independent of the values.

Every term on the right of (16) is a constant determined by the architecture and schedule, so `Pos` at any boundary is computable in closed form from the seed's fixed consumption plan.

**The uniqueness of true-length processing.** The reference processes the ragged final batch (size `2`) at its *true* length, contributing exactly `2 · W_drop` dropout draws for that batch, so the fourth-batch contribution completes the epoch total to `50 · W_drop`. We claim true-length processing is the *unique* policy under which the per-epoch dropout draw count matches the reference.

*Proof.* Let a policy process `m` effective rows over the epoch (summed over the four batches). Dropout draws one uniform per unit per row, so the epoch's dropout consumption is `m · W_drop`, a strictly increasing function of `m`. The reference has `m = 16+16+16+2 = 50`. Any policy that **drops** the ragged batch processes `m = 48`, consuming `48 · W_drop` — short by `2 · W_drop`. Any policy that **pads** the ragged batch to `16` processes `m = 64`, consuming `64 · W_drop` — long by `14 · W_drop`. Since `m · W_drop` is injective in `m` and `W_drop > 0`, the *only* `m` reproducing `50 · W_drop` is `m = 50`, i.e. the true lengths with neither drop nor pad. Hence true-length processing is unique. ∎

**Consequence: any mishandling shifts every subsequent shuffle.** Suppose an epoch's dropout consumption is off by `Δ = (m − 50) · W_drop ≠ 0`. The ragged batch is the *last* batch of its epoch, so no further dropout draws occur in that epoch — meaning within the offending epoch, all forward/backward values are still computed from the correct stream up to and including the ragged batch, and the only observable is a shifted final position. The **next** PRNG consumer is the following epoch's shuffle, which now reads `below(·)` from a stream advanced by `Δ`. Since `below` maps stream words to indices, a nonzero `Δ` yields a *different permutation*, hence a different assignment of samples to batches, hence different gradients, hence a divergent trajectory from that epoch onward. And because `D_shuffle` and `D_dropout` are constants, the shift `Δ` propagates *unchanged* into every later boundary (each later `Pos` inherits the same additive offset), so once desynced the run never self-heals.

**Connection to delayed divergence.** The desync is injected at the end of one epoch but has *no consumer* until the next epoch's shuffle. Therefore the run remains bit-exact through the remainder of the injecting epoch and diverges *discontinuously* at the first shuffle drawing from the shifted position. This is the "delayed divergence" phenomenon: the causal event (mishandling the ragged batch) and the observable symptom (a different loss curve) are separated by the gap to the next shuffle. It is the stream-position analogue of the gradient-error delay in 45.1, and both are analyzed quantitatively in chapter 46.

### 45.3 The reduction-order invariant

**Statement.** Bit-exact agreement between the rematerialized run and a hypothetical non-rematerialized run (and, more generally, between any two runs claiming determinism) requires that every floating-point reduction execute in an *identical operation order*. Sequential reductions over a *pinned index order* are what guarantee this; parallel/tree reductions and container-iteration-order accumulations do not.

**Why order matters: non-associativity of f64 addition.** IEEE-754 double addition is commutative but **not associative**, because each `+` rounds its result to the nearest representable double, and rounding does not commute with regrouping. The canonical witness:

```
(0.1 + 0.2) + 0.3  =  0.6000000000000001
 0.1 + (0.2 + 0.3) =  0.6
```

These differ in the last bit purely from grouping. More generally, summing a set that mixes magnitudes is order-sensitive: adding many small numbers *before* a large one accumulates them into a value big enough to survive the large add, whereas adding each small number *after* the large one lets each vanish below the large value's unit-in-last-place. Any reduction that sums the same multiset in two different orders can therefore land on two different doubles.

**Why the pinned sequential order fixes it.** A dot product, a batch reduction (`Σ_r`), or a layer-norm statistic (`Σ_k`) computed left-to-right over a *fixed* index sequence performs a fully determined chain of rounded additions. The rematerialized recompute, executing the *same* pinned order, produces the *same* chain and hence the same last bit. This is why claim 1 of 45.1 (bit-for-bit recompute) holds: it silently depends on the recompute using the identical reduction order as the forward pass. Reduction order is a hidden premise of rematerialization exactness.

**How parallel/tree reductions break it.** A tree (pairwise) reduction sums `((a+b)+(c+d))` instead of `(((a+b)+c)+d)`. By non-associativity these generally differ in the trailing bits. A tree reduce is often numerically *better* (lower worst-case error), but "better" is irrelevant here — determinism requires *identical*, not *superior*, arithmetic. If the forward pass used a sequential reduce and the remat recompute used a tree reduce "for speed," the two would disagree in the last bits of the reduced value, and that disagreement would seed a divergence. The engine must therefore fix one order everywhere and forbid opportunistic reassociation, including compiler-level fast-math reassociation.

**How hashmap-ordered accumulation breaks it.** Accumulating contributions by iterating a hash map (or any container whose iteration order is unspecified or depends on insertion history / address layout) sums the multiset in a *nondeterministic* order that can vary run-to-run — across processes, allocator states, or library versions. This is worse than a tree reduce: it is not even stable within one binary across runs. Any gradient accumulation keyed by such a container inherits last-bit nondeterminism that defeats fingerprint comparison. The engine pins accumulation to explicit integer index order for exactly this reason.

**Amplification closes the loop.** A last-bit reduction difference is not self-limiting. It feeds the nonlinearities of the next layer — `g'(z) = z^2` in layer 3, the exponentials in softmax, the `inv^3` in layer norm — and, over training steps, the optimizer's division by `sqrt(vhat) + eps`. Each nonlinear op can magnify the perturbation (chapter 46), and the training recurrence then either amplifies or slowly drifts it. So "just the last bit" is never safe: reduction order must be pinned, not approximately matched.

## 46. Error propagation and the timing of divergence

The characteristic failures of this engine — a wrong recompute mask, a mishandled ragged batch, a flipped epsilon placement — share a counter-intuitive property: they almost never announce themselves at the step where they occur. This chapter models *why*, treating the training loop as a discrete dynamical system and reasoning about how, and how fast, an injected perturbation reaches an observable.

**The loop as a dynamical system.** Write the state at step `k` as the parameter vector `theta_k` together with the optimizer buffers `(m_k, v_k, t=k)`. One step is the map

```
g_k       = ∇_theta L(theta_k ; batch_k)                 (gradient, from a forward+backward)
m_k, v_k  = EMA update of (m_{k−1}, v_{k−1}) with g_k
theta_{k+1} = theta_k − lr · mhat_k / ( sqrt(vhat_k) + eps )   =: theta_k − lr · A_k g_k,   (17)
```

where `A_k` denotes the (diagonal, step-dependent) Adam preconditioner absorbing bias-correction and the `1/(sqrt(vhat)+eps)` scaling. The **reported loss at step `k`** is `L_k = L(theta_k ; batch_k)` — a function of the *current* parameters, produced by the *forward* pass, *before* backward and before the update. This single fact — loss is read off the forward pass at `theta_k`, while errors typically live in the *backward/update* path — is the root of every delayed divergence below.

Let `theta_k^gold` be the reference trajectory and `e_k = theta_k − theta_k^gold` the parameter error. Subtracting the golden recurrence from (17) and linearizing the update map about the golden path,

```
e_{k+1} ≈ (I − lr · J_k) e_k + lr · η_k,                                  (18)
```

where `J_k = ∂(A_k g_k)/∂theta` is the local Jacobian of the preconditioned gradient (an Adam-scaled curvature operator, roughly `A_k` times the Hessian of `L`), and `η_k` is the *injected* error at step `k` — the discrepancy between the engine's and the reference's computed update that is *not* explained by `e_k` itself. The homogeneous factor `M_k := I − lr·J_k` governs how a past perturbation is transported forward; its spectral radius `ρ := ‖M_k‖` sets the amplification per step. With `lr = 0.01` and bounded curvature, `ρ` is close to `1` — updates are small, so the map neither explodes nor contracts quickly. The three failure classes differ in the *structure of `η_k`* (one-shot vs recurring, gradient-space vs stream-space), and that structure dictates the timing signature.

**Class 1 — gradient-only error (wrong dropout mask on recompute).** Here the forward pass at step `k` is correct, so `L_k` is bit-exact with golden: the loss came from `theta_k` via the forward pass, and the mask error lives only in the *backward* recompute (45.1, Break A). The injected error is a one-shot gradient perturbation `η_k = A_k · δg_k` at the single step `k`, with `η_{k'} = 0` for `k' > k` (assuming the mask logic is otherwise correct thereafter). Its consequences:

- **Step `k`: loss bit-exact.** `L_k` does not depend on `g_k`. Observationally invisible.
- **Step `k+1`: first appearance.** `e_{k+1} ≈ lr · η_k = lr · A_k δg_k`. The next forward pass evaluates `L_{k+1} = L(theta_{k+1}; batch_{k+1})`, and to first order `L_{k+1} − L_{k+1}^gold ≈ ⟨∇L, e_{k+1}⟩ = O(lr · ‖δg_k‖)`. With `lr = 0.01`, this first deviation is *two orders of magnitude smaller* than the raw gradient error — small, but nonzero.
- **Steps `k+1+n`: propagation.** With no further injection, (18) gives `e_{k+1+n} ≈ M_{k+n}···M_{k+1} · e_{k+1}`, so `‖e_{k+1+n}‖ ≲ ρ^n · lr · ‖δg_k‖`. Because `ρ ≈ 1`, the error neither vanishes nor detonates; it *persists and slowly evolves*, and the loss gap tracks it. If the local dynamics are mildly expanding (`ρ > 1`, common near a poorly-conditioned direction early in training), the gap grows geometrically but off a tiny `O(lr·‖δg‖)` base, so it takes several steps to climb above a fingerprint tolerance.

The signature is therefore: **exact loss at the injection step, a faint deviation one step later, then compounding.** A test that inspects only `L_k` (or the first couple of losses) sees nothing.

**Class 2 — stream desync (ragged batch mishandled).** From 45.2, the injected error is *not* in gradient space at all until a shuffle consumes the shifted stream. Structurally, `η_{k'} = 0` for every step until the first shuffle after the desync; the run is **bit-exact**, not merely close, through the rest of the injecting epoch, because every value up to the ragged batch was computed from the correct stream and the ragged batch is the epoch's last draw-consumer. Then, at the first shuffle drawing from the shifted position, the permutation changes *discontinuously*: samples are reassigned to batches, so `batch_{k'} ≠ batch_{k'}^gold` for the entire next epoch. The gradient `g_{k'} = ∇L(theta_{k'}; batch_{k'})` is a different (still valid) vector — not an infinitesimal perturbation but an `O(1)` change. The observable is a **step-change (jump) in the loss** at the epoch boundary, not a drift:

```
L_{k'} − L_{k'}^gold = L(theta; batch_{k'}) − L(theta; batch_{k'}^gold) = O(1).
```

Contrast with Class 1: there the perturbation entered through `e` (parameters) and was scaled by `lr`; here it enters through the *data assignment*, unscaled, and appears the instant the shifted stream is read. The signature is **a long stretch of exact agreement followed by a sharp discontinuity at a shuffle boundary** — the delayed, then abrupt, divergence of 45.2.

**Class 3 — epsilon-placement difference.** From 44.4, `1/(sqrt(vhat)+eps)` and `1/sqrt(vhat+eps)` differ by `O(eps/vhat)` for large `vhat` and by up to a `10^4` factor for `vhat → 0`. This is a **recurring** injection: `η_k ≠ 0` at *every* step, but with tiny magnitude in the typical (large-`vhat`) regime. Model it as a small persistent forcing `η_k = η̄` (roughly constant sign and scale over a stretch, since the discrepancy is a smooth function of `vhat` that changes slowly). Summing (18) over steps with `M ≈ ρ I`,

```
e_{K} ≈ lr · Σ_{k<K} ρ^{K−1−k} η̄.
```

For `ρ ≈ 1` this is approximately `e_K ≈ lr · K · η̄` — a drift that grows *linearly* in the step count (or geometrically if `ρ` is slightly above 1), rather than jumping. Each step nudges the trajectory by a hair in a consistent direction; the nudges accumulate. The signature is a **small, monotonically compounding drift**: indistinguishable from golden for the first several steps (the per-step `η̄` is far below fingerprint resolution), then a slowly widening gap. It never jumps and never (in the `f64`-bounded regime) blows up abruptly; it simply diverges by accumulation. This is the hardest class to catch early precisely because its early-step footprint is smallest.

**Comparative timing summary.**

| Failure class | Loss at injection step | First observable | Growth shape | Set by |
|---|---|---|---|---|
| Gradient-only (recompute mask) | bit-exact | step `k+1` | `O(lr·‖δg‖)` base, `∝ ρ^n` | optimizer step scale `lr`, curvature `ρ` |
| Stream desync (ragged batch) | bit-exact (whole epoch) | next shuffle boundary | discontinuous `O(1)` jump | data reassignment, unscaled |
| Epsilon placement | bit-exact | many steps later | monotone `≈ lr·k·η̄` drift | recurring tiny forcing, `∝ k` |

**Why "run to the end and fingerprint."** All three signatures defeat early-loss comparison, each for a different reason: Class 1 because the injection-step loss is forward-derived and correct; Class 2 because the desync has no consumer until a later boundary; Class 3 because the per-step forcing is sub-tolerance and only its accumulation is visible. The only test that catches all three is one that (a) runs the *full* `16`-step, `4`-epoch schedule, and (b) compares a **state fingerprint** — a hash over all parameters, both Adam moment buffers, the step counter `t`, and the final PRNG word — against the golden fingerprint, rather than comparing an early loss scalar. The fingerprint is sensitive to last-bit differences anywhere in state, so a Class-1 perturbation that has grown over the remaining steps, a Class-2 permutation shift, and a Class-3 accumulated drift all register. Comparing the PRNG word specifically catches Class 2 even in the (unlikely) event that the shifted permutation happened to produce a numerically close loss, because the *position* itself is wrong. And storing `t` in the fingerprint guards the bias-correction dependency of 44.4.

This is the operational moral tying back to section 19: each entry in the failure catalogue has a *timing signature*, and the test harness must be designed around the *slowest-to-surface* class. A green early-loss check proves nothing about determinism; only an end-of-run, full-state fingerprint comparison does. The delayed-divergence structure is not a nuisance to be worked around — it is a direct, provable consequence of the loop being a discrete dynamical system in which errors enter the backward/update path while observables are read from the forward path, and it is precisely why the invariants of chapter 45 are stated over *whole-run* state rather than per-step loss.

## 47. Worked multi-step micro-training trace

Sections 22–23 traced a single forward and backward on the micro network with fixed
masks. This section runs the *whole loop* — forward, backward, clip, Adam update —
for three consecutive steps, so the optimizer's effect on the weights is visible. It
uses the same tiny `3 → 4 → 4 → 4 → 2` network and batch of two as section 22, with
the dropout masks now drawn from a seeded generator (`Rng(0x00051ACE)`) rather than
fixed, so the masks change from step to step exactly as they would in a real run. The
initial weights are those listed in section 22. This is illustrative; it is not the
shipped `8 → 16 → 16 → 16 → 4` run and does not reproduce its numbers.

On this micro network the layer-3 pre-clip gradient norm stays well under the
threshold `τ = 3.0` on every step (the micro `W3` is small), so no clip fires here —
which is itself worth seeing: clipping is conditional, and on well-behaved batches it
is a no-op, exactly as on the steps of the real run where the layer-3 norm happens to
stay under `τ`. The recorded gradient norm is still the post-clip global norm; here
post-clip equals pre-clip because the clip did not engage.

### Step 0

```
mask1 =
  [0.00000000, 1.25000000, 0.00000000, 1.25000000]
  [0.00000000, 1.25000000, 1.25000000, 1.25000000]
mask2 =
  [1.25000000, 1.25000000, 1.25000000, 1.25000000]
  [1.25000000, 1.25000000, 0.00000000, 1.25000000]
logits Zo =
  [0.00000000,  0.00000000]
  [0.04832690, -0.03131123]
softmax P =
  [0.50000000, 0.50000000]
  [0.51989902, 0.48010098]
loss = 0.7134529966
layer-3 pre-clip norm = 0.1298269821   (tau = 3.0, clipped = false)
post-clip global grad-norm = 0.2913513432
W3 after the Adam step =
  [ 0.39000000, -0.19000001, 0.10999996, 0.29000001]
  [ 0.10000000,  0.50000000, -0.30000000, 0.00000000]
  [-0.20000000,  0.20000000,  0.40000000, -0.10000000]
  [ 0.29000000, -0.09000002,  0.00999992, 0.19000001]
Wo after the Adam step =
  [ 0.29000000, -0.19000000]
  [ 0.10999997,  0.39000003]
  [-0.30999952,  0.10999952]
  [ 0.19000001,  0.00999999]
```

Notice the first-step Adam signature: every parameter that received a nonzero
gradient moved by almost exactly `lr = 0.01` in magnitude, because at `t = 1` the
update is `lr · m̂ / (sqrt(v̂) + ε)` with `m̂ = g` and `sqrt(v̂) = |g|`, so the ratio
is ≈ 1 regardless of the gradient's size. `W3`'s third row is unchanged because that
row's gradient was zero on this batch (its inputs were dropped). This is the
sign-descent behavior of Adam's first step and a quick check that bias correction and
epsilon placement are right (section 44.4).

### Step 1

```
mask1 =
  [1.25000000, 1.25000000, 1.25000000, 1.25000000]
  [1.25000000, 0.00000000, 1.25000000, 1.25000000]
mask2 =
  [1.25000000, 1.25000000, 0.00000000, 1.25000000]
  [1.25000000, 1.25000000, 0.00000000, 1.25000000]
logits Zo =
  [0.02241890, -0.01023038]
  [0.01099083,  0.02700216]
softmax P =
  [0.50816160, 0.49183840]
  [0.49599725, 0.50400275]
loss = 0.6810646704
layer-3 pre-clip norm = 0.0827402577   (tau = 3.0, clipped = false)
post-clip global grad-norm = 0.4096783999
W3 after the Adam step =
  [ 0.38696882, -0.17999020, 0.11934125, 0.28745739]
  [ 0.09255863,  0.50744137, -0.29255864, -0.00744134]
  [-0.20000000,  0.20000000,  0.40000000, -0.10000000]
  [ 0.28840469, -0.08784969,  0.00861269, 0.18798706]
Wo after the Adam step =
  [ 0.28680562, -0.18680562]
  [ 0.10389950,  0.39610050]
  [-0.30298908,  0.10298908]
  [ 0.18779144,  0.01220856]
```

The masks are different from step 0 — the generator advanced — and the loss has moved.
`W3`'s third row is still unchanged: on this batch too its inputs happened to be
dropped or the upstream gradient did not reach it. The update magnitudes are now
smaller than a flat `lr`, because at `t = 2` the bias correction and the accumulating
second moment have begun to shape the step.

### Step 2

```
mask1 =
  [1.25000000, 1.25000000, 1.25000000, 0.00000000]
  [1.25000000, 1.25000000, 1.25000000, 0.00000000]
mask2 =
  [1.25000000, 1.25000000, 1.25000000, 0.00000000]
  [1.25000000, 1.25000000, 1.25000000, 0.00000000]
logits Zo =
  [-0.01018726, 0.01331931]
  [ 0.01832304, 0.10232626]
softmax P =
  [0.49412363, 0.50587637]
  [0.47901153, 0.52098847]
loss = 0.6784984558
layer-3 pre-clip norm = 0.1242438900   (tau = 3.0, clipped = false)
post-clip global grad-norm = 0.2942151233
W3 after the Adam step =
  [ 0.38607324, -0.17000114, 0.12715746, 0.28708781]
  [ 0.08460262,  0.51533011, -0.28443632, -0.01395425]
  [-0.19361189,  0.19361217,  0.39361197, -0.09361200]
  [ 0.28717152, -0.08618748,  0.00754036, 0.18643104]
Wo after the Adam step =
  [ 0.28510635, -0.18510635]
  [ 0.09636441,  0.40363559]
  [-0.29516496,  0.09516496]
  [ 0.18725928,  0.01274072]
```

Now `W3`'s third row finally moves — this step's masks let a gradient reach it. The
loss is drifting down. Three things this trace makes concrete: the masks change every
step because they are drawn from the advancing stream (so a checkpointed recompute
must replay the *right* step's masks, section 10); the weights evolve smoothly under
Adam (so a resume must restore the moment buffers, not just the weights, or the next
update is wrong, section 19.1); and the clip is conditional (so recording the
post-clip norm is correct whether or not the clip engaged, section 13).

A resumed run that reloaded the weights shown after step 1 but restarted Adam's
moments at zero would, at step 2, apply the flat-`lr` first-step update again instead
of the shaped `t = 3` update, and `W3` would land at different values than the row
above — the weights-only-checkpoint divergence, made visible.


---

# Part VI — Building and verifying

## 48. Implementation order and the self-check ladder

The engine has a natural build order, and each stage has a cheap self-check that must
pass before the next stage is worth writing. Building bottom-up and checking at every
rung is the difference between finding a bug in five minutes and finding it after a
full run diverges for reasons that could be any of a dozen subsystems. The ladder
below is the order the reference was built in, and the order we recommend.

**Rung 1 — the PRNG (`rng.rs`).** Nothing works until the generator reproduces the
test vectors in section 24.1 exactly. Implement SplitMix64, then verify the first six
`next_u64` outputs from seed `1234` against the hex in section 6.1, the four
`uniform_open` values, the four `normal` values, and the `below(50)` sequence. These
are integer and floating-point checks that isolate the generator completely. If any
`next_u64` word is wrong, stop — every downstream value depends on this and there is
no point implementing anything else. A common early bug is non-wrapping arithmetic
(using checked or panicking multiplication instead of wrapping) which fails only on
the mixing multiplies; the test vectors catch it immediately. Verify `state()` /
`set_state()` round-trip: `set_state(state())` must be a no-op, and after
`set_state(v)` the next draw must equal the draw captured when `v` was taken. This is
the single most important property in the whole engine (section 45.1) and it is
trivial to test in isolation now and painful to debug later.

**Rung 2 — the tensor type and the ops (`tensor.rs`, `ops.rs`).** Implement the
matrix type with sequential-order matmul (section 14), then each op's forward and
backward. Verify against the micro-trace in sections 22–23: feed the exact tiny
inputs, weights, and fixed masks, and check every intermediate matrix — `Z1`, `N1`,
`A1`, `D1`, `Z2`, …, `Zo`, the per-row losses, and then the backward gradients — to
ten decimal places. This is a complete, self-contained gradient check that does not
touch the PRNG, the training loop, or the database. If layer-norm backward is wrong,
it shows up here as a mismatch in `dZ1` or `dZ2` against the printed values; if the
matmul reduction order is subtly off it shows up in the last digits. The micro-trace
exists precisely so this rung has a golden reference.

**Rung 3 — the forward pass and draw accounting (`tape.rs` forward).** Assemble the
ops into the forward pass and verify two things: the loss on a real batch matches the
worked value in section 8.6 (step-0 loss for the shipped seed), and the *draw count*
per step matches. Instrument the generator to count `next_u64` calls and confirm that
initialization consumes exactly 1408 draws (section 7), each epoch's shuffle consumes
49, and each batch's dropout consumes `rows × 32`. Cross-check the epoch-0 permutation
against section 24.3. If the permutation is right but the loss is wrong, the bug is in
the ops (rung 2 regressed); if the permutation is wrong, the draw accounting or the
shuffle is wrong. Getting the draw counts right *now*, before writing backward, means
the ragged-batch and epoch-boundary behavior (the hardest part) is already correct
when you reach it.

**Rung 4 — the backward pass and rematerialization (`tape.rs` backward).** Implement
the reverse pass with the layer-2 block cached, verify the full-batch gradients with a
finite-difference check (perturb each parameter by a small `h`, recompute the loss
with a *fixed* PRNG state so dropout is held constant, and compare the central
difference to the analytic gradient — they should agree to about `1e-5` relative).
Then add the rematerialized path and verify the key invariant directly: the gradients
from the cached path and the recomputed path must be *bit-identical* (section 45.1).
If cached and recomputed gradients differ, the mask replay is wrong; if they agree but
disagree with finite differences, the math is wrong. The two checks localize the bug
to different subsystems.

**Rung 5 — the optimizer (`optimizer.rs`).** Implement Adam with the pinned epsilon
placement and verify against the scalar trace in section 30: a single parameter driven
by the illustrative gradient sequence must reproduce the `m`, `v`, `mhat`, `vhat`,
denominator, update, and resulting `theta` at each step. This isolates bias
correction and epsilon placement from the network entirely. Then run the full loop for
a few steps and check the multi-step micro-trace in section 47 — the weights after
each Adam step must match, confirming the optimizer and the loop are wired correctly.

**Rung 6 — checkpoint save/load and hashing (`checkpoint.rs`).** Implement the binary
format (section 15.2) and the FNV fingerprints (section 15.4). Verify the FNV anchors
in section 25.1 (`fnv1a64("CKPTAD01")` and the empty-string seed). Verify a
round-trip: save a snapshot, load it, and confirm the loaded state is bit-identical to
the saved state. Verify the load-time validation rejects a truncated file and a
checksum-corrupted file with a clean error. Verify the three component hashes respond
only to their own regions using the byte-edit procedure in section 25.3. Only after
this rung is resume worth attempting.

**Rung 7 — resume (`main.rs` resume path).** With rungs 1–6 solid, resume is
assembly: load the snapshot, restore weights, moments, `t`, the PRNG word, and the
epoch permutation, set the step counter, and continue the loop from wherever the
snapshot's step falls — including mid-epoch, where the loop must use the restored
permutation rather than reshuffling (section 16). Verify that a resume reproduces the
uninterrupted run's remaining steps bit-for-bit. If it diverges immediately, the
checkpoint dropped optimizer state (section 19.1); if it cannot even form the right
mid-epoch batches, the permutation was not restored; if it diverges only at the next
epoch, the ragged-batch handling from rung 3 was wrong after all and the PRNG state,
though correctly saved, was already pointing at the wrong place.

**Rung 8 — the database (`dbwriter.rs`).** Emit the schema and rows to `sqlite3`
(section 17). Verify `PRAGMA integrity_check` is `ok`, `PRAGMA foreign_key_check` is
empty, and re-running a mode replaces rather than appends. This rung has no numerical
content; it is pure plumbing, and it comes last because it depends on everything above
producing correct numbers to record.

The discipline is the same at every rung: a cheap, isolated check that a human can run
in seconds, positioned so that a failure points at exactly one subsystem. Skipping
rungs — writing the whole engine and then running the full suite — replaces eight
five-minute diagnoses with one multi-hour bisection.

## 49. Numerical ranges, conditioning, and reproducibility bounds

This section analyses the magnitudes that flow through the network and the sense in
which the engine's `f64` arithmetic is both safe (no overflow, no catastrophic
cancellation that matters) and reproducible to the last bit. None of it changes what
the engine computes; it is the justification that the computation is well-behaved.

### 49.1 Value ranges, layer by layer

Track a representative coordinate from input to loss.

- **Input.** The dataset is a fixed synthetic blob of standard-normal-scale features,
  so `|x| ` is order 1, almost always below 4.
- **Layer-1 linear.** `Z1 = X·W1 + b1` sums `D_in = 8` products of an order-1 input
  with a `σ = 0.30` weight, so `Var(Z1) ≈ 8 · 0.30² · Var(x) ≈ 0.72`, and `Z1` is
  order 1.
- **Layer norm.** By construction the normalized `xhat` has zero mean and unit
  variance per row, so `N1 = γ⊙xhat + β` with `γ = 1, β = 0` is order 1, with
  entries essentially never outside `±5` (five standard deviations of a
  mean-zero-unit-variance quantity). This is the point of normalization: it caps the
  dynamic range entering the next layer regardless of the incoming scale.
- **ReLU and dropout.** ReLU only zeroes; dropout scales survivors by `1/(1-p)=1.25`.
  Neither expands the range beyond the layer-norm output times `1.25`, so `D1` stays
  order 1.
- **Layer 2** repeats the pattern: another normalized, order-1 block.
- **Layer 3.** `Z3 = D2·W3 + b3` sums `H2 = 16` products of order-1 activations with
  `σ = 0.50` weights, so `Var(Z3) ≈ 16 · 0.25 ≈ 4` and `std(Z3) ≈ 2`; a three-sigma
  coordinate reaches `|Z3| ≈ 6`. The activation `A3 = Z3³/3` then reaches
  `|A3| ≈ 6³/3 ≈ 72` on such a coordinate — the one place in the forward pass where
  the magnitude leaves the order-1 regime. There is no layer norm after it, by
  design; this is the "stiff" layer.
- **Logits.** `Zo = A3·Wo + bo` sums `H3 = 16` products of the (possibly tens-scale)
  `A3` with `σ = 0.30` weights, so `|Zo|` can reach a few tens on the batches where
  `Z3` had large coordinates. The softmax max-subtraction (section 8.6) then brings
  the exponent arguments to `≤ 0`, so `exp` never sees a large positive argument.

The only place magnitudes exceed order 1 is layer 3, and its output feeds a linear
layer and then a max-stabilized softmax — so nothing downstream amplifies it into a
range problem. The large *gradients* layer 3 produces are handled by the clip
(section 13); the large *values* are handled by the max-subtraction and by `f64`'s
range.

### 49.2 Overflow and underflow headroom

`f64` represents magnitudes up to `≈ 1.8 × 10³⁰⁸` and down to `≈ 2.2 × 10⁻³⁰⁸`
(normal), with subnormals reaching `≈ 5 × 10⁻³²⁴`. Against the ranges above:

- The largest forward value is `A3`, order `10¹`–`10²`. Its square (which appears in
  the layer-3 backward multiplier `Z3²`) is order `10¹`–`10²`; its cube is order
  `10²`–`10³`. Products and sums of a few hundred such terms stay below `10⁶`. The
  overflow ceiling is `10³⁰⁸`. There are roughly three hundred orders of magnitude of
  headroom; overflow is impossible for this network at this scale.
- Underflow appears only inside `exp(zo − m)` for logits far below the row max. Such
  terms round to `0` harmlessly — they are the classes the softmax assigns
  vanishing probability, and a `0` there is the correct limit, not a loss of
  information that matters. The cross-entropy reads `−ln p_t` for the *true* class,
  whose probability is never the underflowing one for a batch the network is fitting.
- The layer-norm `inv = (var + ε_ln)^(−1/2)` cannot blow up because `ε_ln = 1e-5`
  floors the radicand; even a constant row (variance 0) gives `inv = (1e-5)^(−1/2) ≈
  316`, a finite number. The `1e-5` is a range guard as much as a regularizer.

The gradient norm the database records is therefore never `NaN` or `±∞` for a correct
implementation: every intermediate is finite, and the layer-3 clip bounds the one
group whose magnitude could otherwise grow across steps.

### 49.3 Conditioning of the individual operations

Reproducibility is about rounding, and rounding hurts most where an operation is
ill-conditioned (small input changes cause large output changes). The engine's ops
are benign:

- **Matmul / dot product.** A sum of `k` products is well-conditioned unless the
  partial sums cancel massively (adding large opposite-sign terms). Here the summands
  are order-1 products and `k ≤ 16`, so the condition number of each reduction is
  small and the relative error is a handful of `f64` epsilons (`ε ≈ 2.2 × 10⁻¹⁶`).
- **Layer norm.** The mean and biased variance are sums of `H = 16` order-1 terms;
  the subtraction `z − μ` is the only cancellation, and it is a *deliberate*
  centering, not an accidental one, so the result carries the true centered value to
  full precision. The `+ε_ln` before the root removes the ill-conditioning of `x^(−1/2)`
  near zero.
- **Softmax.** The max-subtraction makes every exponent argument `≤ 0`, so `exp`
  operates in its well-conditioned regime `(0, 1]`, and the normalizing sum is a sum
  of `C = 4` positive terms — no cancellation at all.
- **The cube.** `z³` is smooth and its relative condition number is `3` (a 1% change
  in `z` is a 3% change in `z³`), which is mild; it amplifies *gradients* through
  `z²` but does not amplify *rounding error* pathologically.

No operation in the pipeline is ill-conditioned in a way that would make rounding
error grow faster than linearly in the number of operations.

### 49.4 Rounding-error accumulation across a step

A single `f64` operation commits a relative error of at most `ε/2`. A sequential sum
of `k` terms (section 14) accumulates a worst-case relative error bounded by about
`(k−1)ε` in the standard model, and in practice far less because the errors are not
adversarially aligned. With `k ≤ 16` per reduction, the per-reduction error is at
most a few times `10⁻¹⁵`. A forward-plus-backward pass chains a few dozen such
reductions, so the accumulated relative error in a step's loss or gradient is at
most order `10⁻¹⁴` — ten to twelve significant digits are exact. Over the sixteen
steps of a run, with the optimizer contracting rather than amplifying (the update is
`lr = 0.01` times a bounded direction), the error does not blow up; it stays in the
low-order bits.

This is why the independent-reference comparison uses a *relative* tolerance a little
looser than the accumulated `f64` error: the tolerance has to absorb the genuine
last-bit differences between two correct implementations that use different math
libraries for the transcendental functions, which are of the same `10⁻¹⁴`–`10⁻¹⁵`
order. It does not have to absorb anything larger, because nothing larger occurs in a
correct implementation; any disagreement above that order is a real algorithmic
difference, not rounding.

### 49.5 Why two runs of the same binary agree to the last bit

Within a single binary the argument is stronger than "small error": it is *no* error.
Bit-for-bit agreement between two runs (or between the cached and rematerialized
passes) does not rely on the errors being small; it relies on them being *identical*.
Two evaluations of the same sequence of `f64` operations on the same inputs produce
the same rounding at every step, because IEEE-754 rounding is a deterministic function
of the operands and the operation. So the two evaluations produce the same bits, not
merely nearby bits. The engine's within-binary reproducibility (checkpoint versus
nocheckpoint, resume versus uninterrupted, same-mode reruns) is exactness by this
argument, and it holds no matter how large or ill-conditioned the intermediate values
are — the cube's tens-scale outputs and the clip's rescalings are reproduced exactly
because they are the same operations on the same bits. The only prerequisites are the
ones section 14 pins: identical operation order and no nondeterministic reduction. Get
those right and the low-order bits, which every comparison ultimately inspects, are
not approximately equal but equal.

### 49.6 The clip's effect on the trajectory, quantified

Global-norm clipping of the layer-3 group replaces `(gW3, gb3)` by
`(τ/n)·(gW3, gb3)` when the group norm `n` exceeds `τ`. Two properties follow. First,
the clip is *direction-preserving*: it is a positive scalar multiple, so the update
still points along the same descent direction in the layer-3 subspace; only the step
length changes. Second, the clip is *idempotent under repetition*: applying it twice
is the same as applying it once, because after one application the group norm is
exactly `τ` (or unchanged if it was already below), so a second pass finds `n ≤ τ` and
does nothing. These two facts are why the clip can be described as "bound the update
without changing the model": it is a projection of the gradient onto a ball of radius
`τ` in the layer-3 group, and projections are direction-preserving and idempotent. The
recorded post-clip global norm mixes the clipped layer-3 group with the unclipped
other groups, so it is neither the raw global norm nor `τ`; it is the norm of the
gradient the optimizer actually consumed, which is the quantity a downstream reader
would want.

### 49.7 Fingerprint collision behaviour

The state fingerprints are FNV-1a-64 digests. FNV-1a is not a cryptographic hash, and
that is fine here: the fingerprints are used to detect *accidental* divergence between
runs that should be identical, not to resist an adversary constructing a collision. For
accidental divergence the relevant question is the probability that two genuinely
different states hash to the same 64-bit value, which for a well-mixing 64-bit hash is
about `2⁻⁶⁴ ≈ 5 × 10⁻²⁰` per comparison. Across the handful of per-step comparisons in
a run the union bound keeps the false-agreement probability far below any threshold
that matters. When two fingerprints differ, the states certainly differ; when they
agree, the states agree with overwhelming probability. The three component digests
(weights, optimizer, PRNG) and the full-state digest are computed over disjoint or
nested byte ranges, so each responds to its own region: flipping a byte in the
optimizer region changes the optimizer digest and the full-state digest with the same
`≈ 2⁻⁶⁴`-collision certainty, and leaves the weight and PRNG digests untouched because
their inputs did not change. This is what makes the fingerprints a usable audit of
*which* part of the state moved, not merely *that* it moved.

### 49.8 Database round-trip precision

Losses and gradient norms are `f64` computed in the engine and stored in the database
as REAL, which SQLite represents as an 8-byte IEEE double — the same format. The only
place precision could be lost is the text encoding the engine emits for the value: a
decimal string with too few significant digits would not round-trip. Seventeen
significant decimal digits are sufficient to round-trip any `f64` exactly (the
well-known `DBL_DIG + 2` bound), so a value written with that many digits and parsed
back by SQLite recovers the identical double. This is why the within-binary
comparisons can demand *exact* equality after a round-trip through the database rather
than a tolerance: the store is lossless for the values it holds, and two equal doubles
emitted by the same code produce the same decimal string and therefore parse back to
the same double. The tolerance-based comparisons are reserved for the cross-
implementation case (engine versus the independent reference), where the difference is
genuine low-order rounding from different math libraries, not a storage artefact.
