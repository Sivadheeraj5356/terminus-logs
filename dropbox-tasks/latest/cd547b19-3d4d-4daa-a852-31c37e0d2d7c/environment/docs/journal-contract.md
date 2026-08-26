# Lane journal contract

Each lane keeps a JSON journal at
`/app/build/sdk-abi-index/<lane>/.sdk-lane.journal`. It records what the last
successful pass built for that lane so a subsequent pass can decide whether the
warm tree is still trustworthy.

## Fields

| field | meaning |
| --- | --- |
| `schema_version` | journal format version (`1`) |
| `lane` | lane label |
| `profile_sha256` | sha256 of the resolved lane profile file |
| `idl_digest` | fingerprint of the IDL inputs (see `idl_fingerprint.sh`) |
| `tool_digest` | fingerprint of the generator sources |
| `last_matrix_sha256` | sha256 of the matrix that last drove this lane |
| `configure_epoch` | monotonically increasing configure counter |
| `generation_lineage` | monotonically increasing regeneration counter |

## Freshness

A warm tree may skip reconfigure only when the journal is *current*: it must
carry a non-empty `idl_digest` **and** a non-empty `tool_digest`, and both must
equal the values computed from the present inputs. A journal that is missing
either fingerprint (for example a truncated or torn file) is never current and
forces a fresh configure.

## Counters

- `configure_epoch` advances by one whenever the lane reconfigures.
- `generation_lineage` advances by one whenever the lane regenerates its header
  (a fresh configure, or a reconcile of a missing header). Recovery from a torn
  journal rewrites the journal in full — including both fingerprints — and
  advances the lineage; the first generation for a lane is lineage `1`.

When no input has changed, both counters stay put and the released artifacts are
byte-for-byte identical across re-runs.
