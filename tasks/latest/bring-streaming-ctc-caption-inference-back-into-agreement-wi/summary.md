# Bring streaming CTC caption inference back into agreement with the speech recogn

- **UUID:** `514f0f78-ace8-4966-a9cf-50d9efb3332a`
- **Slug:** `bring-streaming-ctc-caption-inference-back-into-agreement-wi`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Bring streaming CTC caption inference back into agreement with the speech recognition model used for acoustic-frame decoding. Softmax-normalized logits must become a deterministic n-best transcript set—collapsed tokens, acoustic and phrase-bias log scores, token-frame alignments, and calibrated confidence—matching batch and streamed evidence alike.

The accepted inference behavior is defined in `/app/decoder-notes/` (`ctc-prefix-probability-note.md`, `streaming-state-note.md`, `phrase-bias-note.md`, `alignment-and-confidence-note.md`). Utterance packages reach `/app/build/caption-beam` with per-frame class logits, a token vocabulary and blank index (blank text `_`), optional hotword and phrase-bias weights, and a stream operation of `OP_DECODE` (1, append frames and return a provisional n-best), `OP_FINISH` (2, append frames, return the finalized n-best, then clear that stream), or `OP_RESET` (3, clear only the named stream and return an empty successful n-best).

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
