# Behavioural contract

Your program is graded by comparing its emitted JSON against an independent replay of the behaviour
specified below. Every rule, ordering, and boundary condition is binding. All arithmetic is exact: the
retained Gram and right-hand side are exact integers, and every weight and prediction is an exact reduced
rational. No floating point and no tolerance appear anywhere in this contract or in your output.

## Inputs

A bundle directory holds six CSV files.

`config.csv` has header `key,value` with five integer keys:

- `grace_G`: the absence grace `G` (see the active set below).
- `ridge_lambda_num`, `ridge_lambda_den`: the ridge regulariser `lambda = ridge_lambda_num /
  ridge_lambda_den`, a strictly positive rational.
- `value_scale`: a power of ten. Every reading, multiplied by `value_scale`, is an exact integer. Work
  with these **scaled integer** values throughout: for a raw reading `r`, its integer value is `x =
  value_scale * r`. Feature values and targets are scaled the same way.
- `label_delay`: the label latency `L >= 1` (see labels below).

`events.csv` has header `event_id,ts,<feature_id>,<feature_id>,...`, one row per event **already in stream
order**; process the rows in file order. `event_id` is `0,1,2,...`. `ts` is an opaque ordering label with
no arithmetic meaning. Every remaining column header is an integer **feature id**. A cell is **empty** when
that feature is not reporting at that event; otherwise the cell is that feature's reading. Feature ids are
arbitrary integers and carry no meaning beyond identity.

`targets.csv` has header `event_id,y`, one row per event in the same order. `y` is the target reading at
that event, or empty when the target is missing there.

`schema_changes.csv` has header `change_id,at_event,feature_id,kind` with `kind` in `{ONSET, OFFSET}`. It
is a disclosed log of the feature-lifecycle transitions the rules below produce on this stream, always
consistent with applying those rules to `events.csv`. It introduces no independent obligation.

`queries.csv` has header `query_id,at_event`. `checkpoints.csv` has header `checkpoint_id,at_event`. In
both, `at_event` is the `event_id` during whose processing the emission is made, as fixed by the per-event
order below. Rows may appear in any order.

## The active set and the model

You maintain **one** ridge / recursive-least-squares regressor over the currently **active** features. A
feature is active between the event at which it starts reporting and the event at which it is retired. The
retained state is the identified active set, a shared symmetric integer Gram matrix `A` over pairs of
active features, an integer right-hand-side vector `b` over active features, and, per active feature, the
number of consecutive events it has been absent.

- A present feature that is not active **onsets**: it joins the active set with an all-zero row and column
  in `A`, a zero `b` entry, and a zero absence count. A feature that had been retired and reports again
  onsets in exactly this way — freshly, never resuming any earlier state.
- An active feature that is present resets its absence count to zero. An active feature that is absent
  increments its absence count, and once that count exceeds `G` it is **retired**: its row and column
  leave `A`, its entry leaves `b`, and it leaves the active set, so the model dimension drops by one.
  Because `A` couples the active features, retiring one changes the solved weights of those that remain.

`A` and `b` are the coupled sufficient statistics accumulated by the folds described below — the summed
outer products of folded feature sub-vectors and the summed products of those sub-vectors with their
target. There is no event-replay buffer beyond the bounded set of labels still awaiting arrival.

The **weight vector** `w` over the active features is the exact solution of `(A_active + lambda * I) w =
b`, where `A_active` is `A` restricted to the active features. Because `lambda > 0` this system is
symmetric positive definite, so `w` is unique; solve it exactly over the rationals.

## Labels arrive late

The target reading in `targets.csv` at event `e` is the label for the feature vector observed at event
`e`, but it is not available until `label_delay` events later. An event whose target is present therefore
contributes a **deferred update**: the scaled-integer readings of the features that are present and active
at `e` are captured together with that target, and the update is folded into `A` and `b` only when its
label arrives, during the processing of event `e + label_delay`. Captures whose arrival event would fall
past the end of the stream are never folded. A feature vector captured at `e` uses the same present-and-
active features that a prediction at `e` would use; nothing is imputed for absent features.

A deferred update contributes only for the features that stay active continuously from its capture until
its fold. Concretely, when a feature is retired it is dropped from every deferred update still awaiting a
label — its captured reading never folds and never resurrects its row. So at the moment a deferred update
is folded, exactly its surviving captured features (all currently active) contribute their coupled
sufficient statistics; a feature that onsets again after retirement is a fresh feature and receives
nothing from any update captured before it retired.

## Per-event processing

For each event, in stream order, apply these steps in exactly this order.

1. **Onset** every present feature that is not active.
2. **Retire** by the grace rule above; a retirement also drops that feature from every deferred update
   still awaiting its label.
3. **Predict.** If this `event_id` appears in `queries.csv`, emit, for every such `query_id`, the
   prediction `y_hat = sum over the present-and-active features f of w[f] * x[f]` using the current `w` —
   computed **before** any fold at this event. If no feature is both present and active, the prediction is
   `0`.
4. **Fold** the deferred update whose label arrives now, i.e. the one captured `label_delay` events ago
   (if any), into `A` and `b` over its surviving captured features.
5. **Capture** this event's deferred update: if the target is present, remember the present-and-active
   feature readings and the target for folding `label_delay` events later.
6. **Checkpoint.** If this `event_id` appears in `checkpoints.csv`, emit the retained-state readout for
   every such `checkpoint_id`, taken **after** steps 1–5 of this event.

## Output

Write one JSON document to stdout:

```json
{
  "n_events": <int>,
  "predictions": [[<query_id>, "<num>/<den>"], ...],
  "checkpoints": [
    {
      "id": <checkpoint_id>,
      "active": [<feature_id>, ...],
      "gram": [[<i>, <j>, <int>], ...],
      "b": [[<feature_id>, <int>], ...],
      "weights": [[<feature_id>, "<num>/<den>"], ...]
    },
    ...
  ]
}
```

- `n_events`: the number of event rows.
- `predictions`: one entry per row of `queries.csv`, ordered by ascending `query_id`. Each prediction is
  an exact rational rendered as `"num/den"` in lowest terms with a positive denominator (zero is `"0/1"`).
- `checkpoints`: one object per row of `checkpoints.csv`, ordered by ascending `checkpoint_id`. Within a
  checkpoint:
  - `active`: the active feature ids, ascending.
  - `gram`: for every pair `i <= j` of active feature ids (both ascending), the entry `A[i,j]` as an exact
    integer, including entries that are zero.
  - `b`: for every active feature id (ascending), its `b` entry as an exact integer.
  - `weights`: for every active feature id (ascending), its weight as an exact `"num/den"` rational in
    lowest terms with a positive denominator.

Every integer is exact and every rational is exact. The comparison has no tolerances.
