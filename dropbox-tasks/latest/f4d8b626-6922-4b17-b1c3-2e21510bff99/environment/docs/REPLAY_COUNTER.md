# Replay counter

resolve-precedence writes replay_seq 1 on the resolved artifact.

reconcile-observations requires resolved.replay_seq equals 1 before linking observations. If resolved.replay_seq is not 1, exit 1 with REPLAY_MISMATCH on stderr.

After successful reconcile, the reconciled artifact carries replay_seq 2.

export-atlas does not advance replay_seq; it reads reconcile_bind from the on-disk reconciled state file.
