# Mutation chain receipt

`mutation_chain_receipt.json`:

| Field | Meaning |
|-------|---------|
| `corpus_stamp` | Must match freeze |
| `cutoff` / `emitted_at` | Must match evaluation clocks |
| `receipt_kind_chain` | Always `mutation_chain` |
| `mutation_attest` | SHA-256 over compact sorted JSON of `{cutoff, corpus_stamp, emitted_at, receipt_kind_chain}` |
