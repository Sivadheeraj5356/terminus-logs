# fxctl runbook

Maintainer notes for driving the harness inside the container.

## Build

make -C /app/environment produces bin/fxctl and bin/peek. Harbor scoring always rebuilds from current sources via bash /tests/compile_verifier_binary.sh, which runs go build -C /app/environment -o /tmp/fxctl ./cmd/fxctl. Local rebuilds under bin/ are fine for iteration but do not substitute for pipeline repairs in Go sources.

## Invocation shape

/tmp/fxctl --case <id> --phase <seal|verify|append> --out /app/output/sync_record.json

Case ids are listed in payload/cases.json. Phases are seal, verify, and append. Each case carries an epoch id resolved against payload/ring_seg.bin.

## Session behavior

Some verify arms assume earlier seal or append steps left group prefixes in var/work/state.json. The h3 path expects footer cache state to reflect a prior append. Re-running the same case and phase should yield byte-identical sync_record.json output.

Bundled blobs under payload/ladder_blobs/ and the epoch journal under payload/ring_seg.bin are fixtures; do not delete them.
