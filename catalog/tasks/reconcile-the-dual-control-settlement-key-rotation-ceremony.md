# # Reconcile the dual-control settlement key-rotation ceremony

Submission: `f97d92ac-c12e-4fa4-99b8-2a30500a3aa8`  
Slug: `reconcile-the-dual-control-settlement-key-rotation-ceremony`  
Latest archive: `f97d92ac-c12e-4fa4-99b8-2a30500a3aa8_submission_2026-07-21T04_11_23.993Z.zip`  
Revisions in Dropbox: 1

## Task summary

A primary SoftHSM2 token in `/app/ceremony` contains a retiring settlement key whose private half exists only inside that token. A second escrow token contains an escrow private key that also has no filesystem copy. A new settlement key and certificate are staged on disk, but the primary token has no recovery envelope, continuity evidence, escrow receipt, or replacement custody objects yet. Rotate custody without resetting either token or losing unrelated objects. Create an executable `/app/bin/rotate_ceremony`. With no arguments it must read `/app/ceremony/policy.json` and write `/app/ceremony/rotation-attestation.json`. It must also accept `--policy PATH` and `--output PATH` in either order so the same implementation works for other token pairs and policies. Network access is unavailable. SoftHSM2, OpenSC, OpenSSL, `jq`, and a system Python with PyKCS11 and cryptography are installed locally.

Required artifacts include: `/app/ceremony`, `/app/bin/rotate_ceremony`, `/app/ceremony/policy.json`, `/app/ceremony/rotation-attestation.json`, `/app/ceremony/rotation-spec.md`.

Author anonymous tagged this **hard** security task (pkcs11, softhsm, dual-control, hybrid-envelope, crash-recovery).

Time estimates: expert ~360 min, junior ~1080 min.

Harbor timeouts: agent 1800.0s, verifier 360.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `f97d92ac-c12e-4fa4-99b8-2a30500a3aa8_submission_2026-07-21T04_11_23.993Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
