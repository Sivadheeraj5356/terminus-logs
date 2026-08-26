These are read-only SIEM forensic evidence fixtures used during cryptographic
witness-MAC chain-of-custody attestation. Graders and responders copy them into
scratch packs rather than editing the originals in place. When a drill mutates
input, the usual scratch names are mutated_pack.json, mutated_pack2.json,
mutated_report.json, mutated_report2.json, mutated_epoch_pack.json, and
mutated_epoch_report.json. Rebuilds after source repairs use the Go toolchain
at /usr/local/go/bin/go.
