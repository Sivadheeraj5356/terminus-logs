# Bring streaming CTC caption inference back into agreement with the speech recogn

Submission: `514f0f78-ace8-4966-a9cf-50d9efb3332a`  
Slug: `bring-streaming-ctc-caption-inference-back-into-agreement-wi`  
Latest archive: `514f0f78-ace8-4966-a9cf-50d9efb3332a_submission_2026-07-15T08_13_09.781Z.zip`  
Revisions in Dropbox: 1

## Task summary

Bring streaming CTC caption inference back into agreement with the speech recognition model used for acoustic-frame decoding. Softmax-normalized logits must become a deterministic n-best transcript set—collapsed tokens, acoustic and phrase-bias log scores, token-frame alignments, and calibrated confidence—matching batch and streamed evidence alike. The accepted inference behavior is defined in `/app/decoder-notes/` (`ctc-prefix-probability-note.md`, `streaming-state-note.md`, `phrase-bias-note.md`, `alignment-and-confidence-note.md`). Utterance packages reach `/app/build/caption-beam` with per-frame class logits, a token vocabulary and blank index (blank text `_`), optional hotword and phrase-bias weights, and a stream operation of `OP_DECODE` (1, append frames and return a provisional n-best), `OP_FINISH` (2, append frames, return the finalized n-best, then clear that stream), or `OP_RESET` (3, clear only the named stream and return an empty successful n-best). A successful reply is JSON `{"ok": true, "requestId": <uint>, "hypotheses": [...]}`. Each hypothesis object has fields `ids`, `text`, `acoustic`, `bias`, `total`, `confidence`, and `spans` (half-open `[start, end)` frame indexes, one span per collapsed token; empty transcript ⇒ `spans: []`). A rejection is JSON `{"ok": false, "code": "<CODE>"}` with stable codes including `CTC_MALFORMED` and `CTC_NONFINITE`. Rejections leave later utterances' decode state unaffected.

Required artifacts include: `/app/decoder-notes/`, `/app/build/caption-beam`, `/app/rehearse_caption_beam.sh`.

Author anonymous tagged this **hard** machine-learning task (speech-recognition, ctc-inference, prefix-beam-search, asr-confidence, phrase-biasing).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `514f0f78-ace8-4966-a9cf-50d9efb3332a_submission_2026-07-15T08_13_09.781Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
