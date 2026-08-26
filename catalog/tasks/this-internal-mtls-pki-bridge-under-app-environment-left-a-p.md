# This internal mTLS PKI bridge under /app/environment left a partial trust-epoch 

Submission: `50111c59-9816-42e5-bfe1-4b4db2c66f13`  
Slug: `this-internal-mtls-pki-bridge-under-app-environment-left-a-p`  
Latest archive: `50111c59-9816-42e5-bfe1-4b4db2c66f13_submission_2026-07-16T16_21_40.075Z.zip`  
Revisions in Dropbox: 1

## Task summary

This internal mTLS PKI bridge under /app/environment left a partial trust-epoch dump at /app/corp after an authority-boundary incident. Issuance and revocation evidence, certificate and keystore material inventories, and incomplete handshake fragments must reconcile so no principal widens role or trust authority past the PKI policy in /app/docs/cq_w3.md. Fix the Java package sources under /app/environment so a sealed trust timeline at /app/output/tl.json proves barrier-style violations stay cleared across every arm listed in /app/corp/arms.toml, including reorder_j, drop_snap, reenc_pem, perm_a, perm_b, hostile_role, base, and the alt pack arms (alt_base, alt_reorder, alt_drop, alt_perm). Digest helpers live under /app/tools/digest_pack.py; cq_w3 is the obligation home for principals, authority outcomes, revocation and handshake rules, closed fixture algebra, digest construction, and ledger field layout. Rebuild and emit through bash /app/environment/tools/build_x7.sh and /app/bin/x7 --evidence /app/corp --out /app/output/tl.json.

Required artifacts include: `/app/environment`, `/app/corp`, `/app/docs/cq_w3.md`, `/app/output/tl.json`, `/app/corp/arms.toml`, `/app/tools/digest_pack.py`, `/app/environment/tools/build_x7.sh`, `/app/bin/x7`.

Author anonymous tagged this **hard** security task (mtls, pki, tls, authentication, privilege-escalation, revocation).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `50111c59-9816-42e5-bfe1-4b4db2c66f13_submission_2026-07-16T16_21_40.075Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
