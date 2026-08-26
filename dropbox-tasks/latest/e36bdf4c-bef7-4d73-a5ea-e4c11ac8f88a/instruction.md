This host runs an OpenSSL 3 ENGINE→provider migration steward under `/app/environment`. Prefer-arm property queries, provider activation order, and URI loader schemes decide which cryptographic arm is authorized to satisfy a case. After migration, the graded matrix still publishes unauthorized outcomes: strict queries fall back off the prefer-arm, first-wins activation order collapses, and `slotA` rows keep the legacy engine URI scheme so material that should require the preferred arm still opens under `eng://`. Mid-cycle arming state under `/app/output/.ov_persist/` can leave a later suite able to seal with a stale nonce or a residue-shaped digest.

## Requirements

- Restore coherent authority in the live publication sources under `/app/environment` so the normal pipeline regenerates `/app/output/ov_trace.json`. Static hand-authored traces are insufficient. Both frozen baseline files under `/app/environment/share/ref_blobs/` (`ord.go` and `bind.go`) must remain unmodified byte-for-byte for the whole graded run; the verifier keeps protected copies and hashes under `/opt/verifier/` and compares both files before and after grading.
- First-wins activation order and URI-scheme binding must be realized in the live publication modules that isolation restores from those baselines (`/app/environment/r4/ord.go` and `/app/environment/t6/bind.go`). Equivalent-looking fixes only in `ov_probe` wrapper or probe helper sources are insufficient: swapping a stock baseline onto the matching live module must re-expose the original broken fetch_seq or scheme outcomes.
- Graded schemas, eight-segment digests (including weight), first-wins activation order, arming nonce binding (weight and `auth_gen`), joint scheme ternary with `file:` override under `slotA`, seal-stamp mismatch handling, and persist surfaces must match `/app/environment/docs/ov_contract.md` (status tokens: `/app/environment/docs/evt_lex.md`).
- Every graded row must be `WIT_FRESH` with coherent `uri_scheme`, `scheme`, `sel_id`, `fetch_seq`, and digest for both arms on every indexed case under `/app/environment/cases/`, including held-out cases the verifier may inject.
- A full graded suite and a rebuild at the same cycle must both exit 0 with matching authority rows. Property-only smoke may look green while the graded matrix still fails and must not replace `/app/output/ov_trace.json`.
- A leftover `/app/output/.ov_persist/arm_token` must keep graded seal non-zero. After recovery wipe, the graded trace and `/app/environment/var/mig/suite_gen` must be absent until the next successful full suite. Token tampering between prepare and finalize must keep finalize non-zero. After a completed graded cycle, prepare must bind the arming nonce to the live `bind_stamp.json` `auth_gen` (not `suite_gen` and not a hardcoded `0`); changing `bind_stamp` between prepare and finalize must keep finalize non-zero.
- After a successful graded finalize, `/app/output/.ov_persist/pref_latch` must exist and contain exactly `sealed` (no extra suffix). Prepare must leave that latch empty or absent before the next arming cycle.
- Live fixtures under `/app/environment/cases/`, arm conf under `/app/environment/conf/`, and `/app/environment/var/mig/` mask/stamp bytes remain authoritative for epoch and weight.

Contract details live in `/app/environment/docs/ov_contract.md` and `/app/environment/docs/evt_lex.md`.

## Verification

```bash
bash /app/environment/scripts/build_workspace.sh
/app/environment/tools/ov_probe/ov_probe --suite all --trace-out /app/output/ov_trace.json
/app/environment/tools/ov_probe/ov_probe --suite rebuild
```

`ov_probe` builds the steward, grades every case on arms `arm_a` and `arm_b`, and writes the authoritative array. Rebuild must agree with a fresh full suite at the same cycle. `--suite prepare` / `--suite finalize` exercise one-shot arming without replacing the graded contract above. `bash /app/environment/migrations/rst9.sh --repair` clears graded state under `/app/output` and removes `suite_gen`.
