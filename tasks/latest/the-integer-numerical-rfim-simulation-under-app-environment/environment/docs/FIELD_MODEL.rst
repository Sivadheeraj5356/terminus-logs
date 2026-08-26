RFIM quasi-static avalanche contract
====================================

``rfimhyst`` evolves a zero-temperature ferromagnetic random-field Ising network along an externally supplied field history. All physical quantities are signed base-10 integers in milli-units. The bundled inputs stay within signed 64-bit arithmetic and no floating-point arithmetic is used.

Command
-------

Build and run from ``/app/environment``::

  go build /app/environment/cmd/fieldloop
  go run ./cmd/fieldloop --model MODEL.json --field FIELD.tsv [--output-dir DIR] [--resume CHECKPOINT.json] [--stop-after N]

The bundled study command is::

  go run /app/environment/cmd/fieldloop --model /app/environment/fixtures/model.json --field /app/environment/fixtures/field.tsv --output-dir /app/output

``--model`` and ``--field`` are required. ``--output-dir`` defaults to ``/app/output``. ``--stop-after N`` limits this invocation to at most ``N`` field samples, where ``N=0`` means all remaining samples. ``--resume`` continues the same complete model and field history.

Success exits 0. Any malformed model, field, option, or checkpoint exits 2, writes one diagnostic beginning ``rfimhyst: input error:``, and removes ``trajectory.tsv``, ``avalanches.jsonl``, ``checkpoint.json``, and their ``.name.tmp`` files from the selected output directory. Parent directories are created as needed.

Model
-----

The model is strict JSON. Extra keys are invalid::

  {
    "schema": "rfim-v1",
    "initial_external_milli": -600,
    "initial_direction": 1,
    "spins": [
      {"id": "a", "bias_milli": 20, "initial": -1}
    ],
    "edges": [
      {"a": "a", "b": "b", "coupling_milli": 100}
    ]
  }

``schema`` must be ``rfim-v1``. ``initial_direction`` and every spin state are either ``-1`` or ``1``. Spin IDs are unique non-empty strings matching ``[A-Za-z0-9._-]+``. Edges are undirected, have two known distinct endpoints, use non-negative couplings, and may occur only once for an unordered endpoint pair. Spin order, edge order, and edge endpoint orientation have no meaning.

The model digest is lowercase SHA-256 of this UTF-8 byte stream after sorting spins by ID and edges by ``(smaller_id, larger_id)``::

  spin<TAB>id<TAB>bias_milli<TAB>initial<LF>
  edge<TAB>smaller_id<TAB>larger_id<TAB>coupling_milli<LF>

Field history
-------------

The field file is UTF-8 TSV with LF line endings and this exact header::

  sample<TAB>external_milli

It contains at least one row. ``sample`` starts at 0 and increases by exactly one. ``external_milli`` is a signed 64-bit integer. Blank lines, extra columns, alternate headers, and non-canonical sample numbering are invalid.

The field digest is lowercase SHA-256 of the canonical UTF-8 bytes consisting of the exact header plus every parsed row rendered as decimal ``sample<TAB>external_milli<LF>``. It binds the entire history, including samples not yet processed by a checkpoint.

The direction at a sample is ``1`` when its target field exceeds the previous target field, ``-1`` when it is lower, and the previous direction when they are equal. Before sample 0, the previous field and direction come from the model. On resume they come from the checkpoint.

Quasi-static event traversal
----------------------------

For spin ``i`` at field ``H``, using the complete current state::

  local_force_milli(i, H) = H + bias_milli(i)
                            + sum(coupling_milli(i,j) * state(j))

For the current state, define its instability threshold::

  threshold_milli(i) = -bias_milli(i)
                       - sum(coupling_milli(i,j) * state(j))

An increasing interval considers only spins currently at ``-1``. A decreasing interval considers only spins currently at ``1``.

At the start of each event search, first inspect the current field. On an increasing branch, any ``-1`` spin with local force greater than or equal to zero is already eligible and the next trigger is the current field. On a decreasing branch, any ``1`` spin with local force less than or equal to zero is already eligible and the next trigger is the current field. This rule handles reversals and equal-field holds.

When no spin is eligible at the current field:

* On an increasing interval, select the smallest threshold strictly greater than the current field and less than or equal to the sample target.
* On a decreasing interval, select the largest threshold strictly less than the current field and greater than or equal to the sample target.
* If no such threshold exists, the interval reaches the target without another event.

All spins tied at the chosen trigger field participate in the first synchronous round of the same event. Event numbers start at 1 for each field sample.

Synchronous avalanche rounds
----------------------------

At one fixed trigger field, calculate every local force from the complete state at the start of the round. On an increasing branch, every spin currently at ``-1`` with local force greater than or equal to zero is eligible. On a decreasing branch, every spin currently at ``1`` with local force less than or equal to zero is eligible. All eligible spins flip simultaneously. Forces are recomputed from the new complete state and rounds continue at the same trigger field until no spin is eligible.

Round numbers start at 1 for each event. A field sample may contain several events, each with one or more rounds. A sample with no event has zero events and zero rounds. Within a round, flipped IDs are sorted lexicographically. Non-negative couplings and one-way branch updates guarantee termination.

Energy and state digest
-----------------------

At any field ``H``::

  energy_milli = -H * sum(state(i))
                 -sum(bias_milli(i) * state(i))
                 -sum(coupling_milli(i,j) * state(i) * state(j))

Each undirected edge contributes exactly once. ``magnetization_sum`` is ``sum(state(i))``.

The state digest is lowercase SHA-256 of UTF-8 lines sorted by spin ID::

  id<TAB>state<LF>

``avalanches.jsonl``
--------------------

Write one compact JSON object per synchronous round, followed by LF. Keys occur in this order::

  sample, event, round, direction, trigger_external_milli, flipped,
  before_digest, after_digest, energy_before_milli, energy_after_milli

Energy values in a round use its trigger field. There are no lines for a sample with no event. The file may be empty and never contains blank lines.

``trajectory.tsv``
------------------

Write this exact header::

  sample<TAB>external_milli<TAB>direction<TAB>avalanche_events<TAB>avalanche_rounds<TAB>flipped_total<TAB>magnetization_sum<TAB>energy_milli<TAB>state_digest<TAB>chain_digest<LF>

Rows use original field sample numbers. ``avalanche_events`` counts distinct event numbers for that sample. ``avalanche_rounds`` counts JSONL records. ``flipped_total`` counts all flipped IDs across those records. Trajectory energy is evaluated at the sample target field after all reachable events have completed.

A continuation writes only the samples processed in that invocation, but always writes the header.

For each sample, form the trajectory prefix through ``state_digest``, including the tab after ``state_digest``. Let ``sample_avalanche_bytes`` be the exact JSONL bytes written for that sample. The chain seed is 64 ASCII zeroes for a fresh run or the checkpoint chain on resume. Then::

  chain_digest = SHA256_ASCII_HEX(
      previous_chain_ascii + LF
      + sample_avalanche_bytes
      + trajectory_prefix_ascii + LF
  )

The complete row is the prefix, the new lowercase chain hex, and LF.

``checkpoint.json``
-------------------

Write strict JSON with two-space indentation and a final LF. Keys occur in this order::

  schema, model_digest, field_digest, next_sample, last_external_milli,
  last_direction, spins, chain_digest

``schema`` is ``rfim-checkpoint-v2``. ``next_sample`` is the first unprocessed field index. ``spins`` contains every spin exactly once in lexicographic ID order, each object using key order ``id, state``. The last external field equals the model initial field when ``next_sample`` is 0, otherwise the target field at ``next_sample - 1``.

A checkpoint is invalid when it has extra or missing keys, the wrong schema, a model or complete-field digest mismatch, an out-of-range next sample, an invalid direction or state, a non-canonical spin list, an inconsistent last external field, or a chain digest other than 64 lowercase hexadecimal characters.

The resume path may be the selected output directory's existing ``checkpoint.json``. The program must read and validate that checkpoint before replacing output artifacts. On any later failure, the normal failure cleanup still removes all selected output artifacts.

Continuation equivalence
------------------------

For any split point, concatenating the first and resumed trajectory data rows must equal a one-shot run byte for byte. Concatenating their ``avalanches.jsonl`` bytes must equal the one-shot log byte for byte. The resumed final checkpoint must equal the one-shot checkpoint byte for byte. The same equivalence applies across three or more invocations.

Changing any field row, including an unprocessed future row, invalidates an existing checkpoint. Input array reordering, repeated clean runs, same-directory continuation, and alternate absolute output directories must not change semantic or canonical output bytes.
