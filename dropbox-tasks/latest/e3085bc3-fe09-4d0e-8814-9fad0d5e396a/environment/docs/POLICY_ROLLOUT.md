# Policy rollout notes

Staged attachment bundles under `data/authority/` were deployed to offline
replay hosts without restarting the reconcile service. Rollout logs in this
directory record operator intent only.

When replay and reconcile disagree after a lane change, compare the lowered
program, the replay traces, and the manifest attestation fields before changing
any one layer in isolation.
