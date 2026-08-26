# Hold adjacency ledger

Bind materializes /app/state/hold-adjacency-ledger.json after DSC peak capture and before torque residual snapshot.

## Pairing rule

Within each batch, scan consecutive hold_profiles in capture order. When abs(temp_c left - temp_c right) is greater than or equal to adjacency_gap_c from the conching window table (default 1.5 when omitted), record one pair:

- pair_seq is a global contiguous integer starting at 1 across batches in batch_id order then capture order
- batch_id, left_polymorph, right_polymorph
- temp_gap_c is abs(temp difference) rounded to three decimals under the same Perl JSON::PP whole-number rules as kiln traces
- adjacency_contrib is abs(temp difference) times adjacency_pair_weight (default 0.01) times min(effective_hold_s of the two holds), then stored as a JSON number

## Ledger schema

Top-level keys are schema hold-adjacency-ledger-v1, pairs, and adjacency_digest. adjacency_digest is SHA-256 over stable JSON of schema and pairs only (key-ordered, Perl JSON::PP encoding).

## Residual coupling

Lattice residual for a batch adds the sum of that batch adjacency_contrib values to the HOLD deviation sum before the three-decimal round. Emit must not recompute pairs from kiln traces; residual rows remain the on-disk bind snapshot under asymmetric trust.

## Emit verification

Emit loads the ledger, recomputes adjacency_digest from capture plus window gap and weight fields recorded in the bind manifest (or window defaults), rejects missing or tampered digests, and includes adjacency_digest in the phase seal preimage.
