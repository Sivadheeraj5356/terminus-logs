# Foldpath continuation contract

`foldpath` traces a branch of solutions of `F(x, lambda) = 0` by pseudo-arclength continuation. All vector components and calculations use finite IEEE-754 double precision. The process locale is `C`.

## Command surface

The installed executable accepts only these forms:

```text
foldpath run --model ABS --control ABS --output ABS --checkpoint ABS [--accept-limit N]
foldpath resume --model ABS --control ABS --output ABS --checkpoint ABS [--accept-limit N]
```

Paths must be absolute. Options may appear in any order, exactly once. `N` is a positive decimal integer and counts newly accepted continuation points during this invocation; the initial point created by `run` does not count. Without `--accept-limit`, the invocation continues until `max_points` is reached or continuation stalls. `run` starts a new history after validating both inputs and may replace existing output and checkpoint files. `resume` requires model and control files whose raw bytes produce the same supplied FNV-1a fingerprints stored in the checkpoint. Resuming a complete checkpoint is idempotent.

Successful complete invocations and invocations that reach their requested acceptance limit exit 0 and write nothing to stdout or stderr. Reaching the limit while the history still has fewer than `max_points` points gives status `partial`; reaching exactly `max_points` gives status `complete`, including when both conditions occur on the same point. A numerical stall before the requested limit takes precedence and follows the stalled exit-3 behavior below.

Command, input, or checkpoint errors exit 2, write nothing to stdout, and write one JSON object plus a newline to stderr: `{"error":"CODE"}`. The codes are `usage`, `model_invalid`, `control_invalid`, `state_missing`, `state_invalid`, `state_mismatch`, and `path_conflict`. These errors must leave pre-existing output and checkpoint bytes unchanged. An operating-system read, write, rename, or directory error exits 4, writes nothing to stdout, and emits `{"error":"io_error"}` plus one newline to stderr; it must not expose a partially written target. A stalled continuation exits 3, writes nothing to stdout or stderr, and persists the last accepted history with status `stalled`.

The four path strings supplied as model, control, output, and checkpoint must be pairwise different; otherwise the command reports `path_conflict`. Filesystem aliases—including symbolic links, hard links, and paths containing `.` or `..` components that resolve to another supplied path—are outside the valid caller contract. Each artifact is atomic independently: temporary files are created beside their target, renamed over the target, and removed on failure. The checkpoint is committed before the output. If the later output commit fails, the newer checkpoint and older output may coexist; a subsequent `resume` regenerates the full output from checkpoint history. No temporary file may remain after normal exit.

Validation order is deterministic. First validate command shape, option uniqueness, absolute paths, and pairwise path strings; report `usage` before `path_conflict`. Next load the model, then the control: malformed content reports `model_invalid` or `control_invalid`, while an operating-system failure reports `io_error`. Validate the model start point and initial tangent after both files load, reporting `model_invalid`. For `resume`, only after those checks, load the checkpoint and report `state_missing`, `state_invalid`, then `state_mismatch` in that order as applicable. Only one error object is emitted.

## Text input rules

Model and control files contain `key=value` lines. Leading and trailing ASCII space or tab around a key or value is ignored. Empty lines and lines whose first non-space character is `#` are ignored. Inline comments are not supported. Keys are case-sensitive and may occur only once. Decimal integers have no sign unless the field explicitly permits one. Floating values use C decimal syntax, must consume the entire value, and must be finite. Comma-separated vectors apply the same whitespace and numeric rules to every item.

Unknown keys, missing keys, duplicate keys, malformed numbers, wrong vector lengths, and values outside the stated ranges make the corresponding file invalid.

## Model files

Every model has these keys:

```text
kind=cubic|coupled|bratu
dimension=N
start_lambda=FLOAT
start_x=FLOAT[,FLOAT...]
orientation=FLOAT[,FLOAT...]
```

`start_x` has `N` entries. `orientation` has `N+1` entries ordered as `(x0, ..., xN-1, lambda)` and must have nonzero Euclidean norm. The start point must satisfy `max_i(abs(F_i)) <= residual_tolerance` from the control file. Dimensions greater than 8 are invalid.

Model-specific keys and equations follow. A file may contain only the common keys and the keys for its selected kind.

For `cubic`, `dimension` is 1 and the additional finite parameters are `a` and `bias`:

```text
F0 = x0^3 - a*x0 + lambda - bias
dF0/dx0 = 3*x0^2 - a
dF0/dlambda = 1
```

For `coupled`, `dimension` is 2 and the additional finite parameters are `a`, `coupling`, `gain`, `bias1`, and `bias2`:

```text
F0 = x0^3 - a*x0 + lambda + coupling*x1 - bias1
F1 = x1 - gain*x0^2 - bias2

dF0/dx0 = 3*x0^2 - a      dF0/dx1 = coupling
dF1/dx0 = -2*gain*x0       dF1/dx1 = 1
dF0/dlambda = 1            dF1/dlambda = 0
```

For `bratu`, `dimension` is from 2 through 8 and the only additional parameter is finite `scale > 0`. Let `h = 1/(N+1)`, with fixed boundary values `x[-1] = x[N] = 0`:

```text
F_i = scale*(x[i-1] - 2*x[i] + x[i+1])/(h*h) + lambda*exp(x[i])
dF_i/dx_i = -2*scale/(h*h) + lambda*exp(x[i])
dF_i/dx_(i-1) = scale/(h*h), when i > 0
dF_i/dx_(i+1) = scale/(h*h), when i+1 < N
dF_i/dlambda = exp(x[i])
```

Overflow or a non-finite model evaluation makes that continuation attempt fail.

## Control files

A control file contains exactly these keys:

```text
initial_step=FLOAT
min_step=FLOAT
max_step=FLOAT
grow_factor=FLOAT
shrink_factor=FLOAT
fast_iterations=INTEGER
slow_iterations=INTEGER
max_newton_iterations=INTEGER
residual_tolerance=FLOAT
correction_tolerance=FLOAT
fold_tangent_tolerance=FLOAT
max_points=INTEGER
```

The constraints are:

- `0 < min_step <= initial_step <= max_step`.
- `1e-8 <= min_step`, `max_step <= 10`, and `max_step/min_step <= 1e6`.
- `1.01 <= grow_factor <= 4`.
- `0.1 <= shrink_factor <= 0.8`.
- `0 <= fast_iterations < slow_iterations <= max_newton_iterations <= 64`.
- All three tolerances are finite and strictly positive.
- `2 <= max_points <= 512`.

## Initial tangent

Every linear system in this contract uses the supplied `fp_linear_solve` semantics: Gaussian elimination in row-major order with partial pivoting. At each column choose the remaining row with greatest absolute pivot magnitude, retaining the lowest row index on an exact tie. Only an exactly zero pivot is singular. Elimination visits rows and columns in increasing order, followed by back-substitution in decreasing row order. Non-finite intermediate values fail the solve. Valid scientific inputs are conditioned away from ambiguous underflow and tolerance boundaries.

At the validated start point, solve

```text
Jx * u = -Jlambda
candidate = normalize((u, 1))
```

where `Jx` is the `N x N` state Jacobian and `Jlambda` is the parameter derivative column. A singular solve makes the model invalid. If `dot(candidate, orientation) < 0`, negate the candidate. The absolute dot product must be greater than `1e-14`, otherwise the model is invalid. This oriented unit vector is the initial tangent.

The first point has index 0, arclength 0, step used 0, zero Newton iterations, `fold = none`, and the actual initial residual. `max_points` includes this initial point. Classify the initial tangent's lambda component by the fold rule below: a nonzero class initializes the retained fold-sign memory, while a zero class leaves that memory empty.

## Predictor, corrector, and acceptance

For an accepted point `y = (x, lambda)`, oriented unit tangent `t`, and attempted step `ds`, form the predictor `p = y + ds*t`. Starting from `z = p`, Newton correction solves the augmented system

```text
[ Jx(z)  Jlambda(z) ] delta = -F(z)
[       t^T         ]         -t dot (z - p)
```

and then updates every component of `z` in place with `z = z + delta`. One successful augmented solve counts as one Newton iteration. Before the first solve and after every update, the corrector has converged exactly when both conditions hold:

```text
max_i(abs(F_i(z))) <= residual_tolerance
abs(t dot (z - p)) <= correction_tolerance
```

At most `max_newton_iterations` solves are allowed. A singular augmented system, non-finite value, or failure to converge within that count rejects the attempt.

On rejection, retry from the unchanged last accepted point and tangent with `ds = ds*shrink_factor`. Clamp a retry to `min_step` when the product is below `min_step`; an unsuccessful attempt at `min_step` stalls. The valid control ranges guarantee that a non-clamped product is representably smaller than the current step. Rejected predictors and corrections never enter history, never advance arclength, never change the fold-sign memory, and never influence growth except through the smaller retried step.

After corrector convergence, the corrected point remains an attempt-local candidate. Its `step_used` is the successful predictor step, its Newton count is the number of augmented solves, its residual is `max_i(abs(F_i))`, and its proposed arclength is the previous arclength plus the Euclidean distance between the previous and corrected `(x, lambda)` vectors.

Compute the new tangent at the corrected point by solving

```text
[ Jx  Jlambda ] q = 0
[    t^T     ]     1
```

and normalizing `q`. If `dot(q, t) < 0`, negate `q`; a zero dot is not negated. A singular or non-finite tangent solve rejects the attempted point just as a corrector failure does. Only after this tangent succeeds is the candidate fold-classified, appended, step-adapted, and checkpointed, in that order. Rejection discards every candidate-local value, including its Newton count, tangent, proposed arclength, and fold class.

After an accepted point, choose the next attempted step from its successful `step_used` and Newton count:

- count `<= fast_iterations`: `min(max_step, step_used*grow_factor)`;
- count `>= slow_iterations`: `max(min_step, step_used*shrink_factor)`;
- otherwise: unchanged `step_used`.

This next step and the entire accepted history are checkpointed after every acceptance.

## Fold labels and boundary convention

Classify a tangent's lambda component with `fold_tangent_tolerance`:

- `positive` when `t_lambda > tolerance`;
- `negative` when `t_lambda < -tolerance`;
- `zero` otherwise.

The checkpoint retains the most recent nonzero class. A zero class neither emits a fold nor replaces that memory. When a newly accepted nonzero class differs from the retained nonzero class, label that new point `max_lambda` for positive-to-negative or `min_lambda` for negative-to-positive, increment the fold count, and replace the retained class. A same-sign class has label `none` and refreshes the retained class. If no earlier nonzero class exists, store the new class without emitting a fold.

Points are ordered only by acceptance index. No parameter-based reordering is allowed.

## Checkpoint and resume semantics

The checkpoint must preserve the raw-byte fingerprints of both input files, dimension, status, complete point history, tangent at every point, next attempted step, fold count, and retained nonzero tangent-lambda class. It must carry integrity protection over the complete serialized state: truncation, appended bytes, or any single-byte alteration of a checkpoint produced by `foldpath` must be rejected as `state_invalid`, without changing either artifact. The supplied FNV-1a helper defines the fingerprints and provides suitable byte-hashing semantics for the starter toolkit. Checkpoint representation is otherwise an implementation detail.

`resume` validates and loads the checkpoint before changing either artifact. It continues from the last accepted point with the saved tangent and next step. The output after resume contains the full history, including points from earlier invocations. Given identical inputs, a `run` split at any acceptance limit and completed with one or more `resume` calls must produce the same point records, fold labels, next step, and complete summary as an uninterrupted run; insignificant JSON whitespace and object-key order are ignored.

## NDJSON output

The output is UTF-8 NDJSON ending with exactly one newline. It contains one point object for every accepted point in increasing index order, followed by exactly one summary object. JSON object-key order and insignificant whitespace are not meaningful. Arrays are ordered and numeric values must be finite JSON numbers; emit negative zero as `0`.

Each point object has exactly these keys:

```json
{
  "type": "point",
  "index": 0,
  "arclength": 0,
  "step_used": 0,
  "lambda": 0,
  "x": [0],
  "residual_inf": 0,
  "newton_iterations": 0,
  "tangent": [0, 1],
  "fold": "none"
}
```

`x` has `N` entries and `tangent` has `N+1` entries ordered `(x0, ..., xN-1, lambda)`. `fold` is exactly `none`, `max_lambda`, or `min_lambda`.

The final summary has exactly these keys:

```json
{
  "type": "summary",
  "status": "complete",
  "dimension": 1,
  "points": 20,
  "folds": 1,
  "arclength": 2.5,
  "next_step": 0.1
}
```

`status` is `partial`, `complete`, or `stalled`. Summary arclength is the last point's arclength. Summary point and fold counts cover the full history.

## Included tooling

The toolkit source is located at `/opt/foldpath`.
`/usr/local/bin/foldmodel-check --model ABS --control ABS` validates the
public file formats, equations, start residual, and initial-tangent orientation
and prints a semantic JSON summary. `/opt/foldpath/scripts/smoke.sh` is a
public regression suite covering the included models, strict limit parsing,
corrected-point arclength and Newton counting, split/resume equivalence, and
checkpoint-first output-rename recovery. The task image also contains working
`tmux` and `asciinema` commands under a UTF-8 terminal locale. No network
installation is part of agent setup, and none of these commands changes model
or control files.
