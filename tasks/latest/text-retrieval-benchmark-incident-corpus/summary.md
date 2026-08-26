# # Text Retrieval Benchmark: Incident Corpus

- **UUID:** `ca236e14-453a-42d7-904c-cc026802e84f`
- **Slug:** `text-retrieval-benchmark-incident-corpus`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

The corpus at `/app/data/incident_transcript.txt` is a multi-day production incident transcript. Build a natural-language retrieval index over this corpus, evaluate its ranking quality against held-out queries, and expose the retrieval and evaluation interfaces so they can be graded.

For a natural-language question, produce a ranked list of the top-k passages and a short synthesised answer:

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
