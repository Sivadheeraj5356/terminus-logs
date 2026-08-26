# Mode-seal contract

Public report path: `/app/output/invariant_proof_log.json`

Coupled mode gap for a fixture cell:

`mode_gap = (omega_obs - omega_ref) - weight[locale] * excit * (gain[mode]*fringe[mode] + coupling[mode]*gain[next(mode)]*fringe[next(mode)])`

where `next` cycles M1→M2→M3→M4→M1.

Digest encoding: for each panel id in sorted order, join rounded gaps with six digits after the decimal point, then hex-digest over `panel:g1,g2,...` segments joined by `|`. Helper routines live under `/app/scripts/digest_encoding.py`.

Metamorphic arms:

- `permute_modes`: remap modes M1→M2→M3→M4→M1 and rotate gain, fringe, and coupling with the inverse map (M1←M4, M2←M1, M3←M2, M4←M3)
- `reverse_locale_bands`: reverse sorted locale labels on cells and reverse the sorted weight vector
- `cascade_compose`: apply permute then reverse; digest must equal the full seal

`chain_digest` is the hex digest of `digest_full|digest_permute_modes|digest_reverse_locale_bands|digest_cascade_compose`.

Peel selection:

- When `/app/data/tb_state/clock.json` `epoch` is at least `require_epoch` from `/app/data/bands_live/index.json`, peel locale weights from `/app/data/bands_live/*.json` files (never index `weights_decoy`).
- Otherwise peel from `/app/data/bands_shadow/*.json`.
- `authority_agreement` requires `/app/data/num_auth/ref_weights.json` to match the peel source locale-for-locale.

Journal tip:

- Binary frames under `/app/data/ms_store/mesh.wal` bind digest, table hash, chain digest, epoch bind, lineage, and violations.
- `/app/data/ms_store/seal.bind` must agree with tip; resume requires matching `table_hash`, `epoch_bind`, and lineage.
- Torn WAL trailers rewrite intact frames and advance lineage.
