# A short secret message has been encrypted with a stream cipher whose keystream c

Submission: `9fa4d98a-7392-42bc-80f9-4a8cec627a09`  
Slug: `a-short-secret-message-has-been-encrypted-with-a-stream-ciph`  
Latest archive: `9fa4d98a-7392-42bc-80f9-4a8cec627a09_submission_2026-07-19T13_27_55.675Z.zip`  
Revisions: 1

## Task summary

A short secret message has been encrypted with a stream cipher whose keystream comes from a linear congruential generator, and your job is to recover the message. Each challenge file describes one generator in a few key equals value lines. It gives the modulus width in bits, a run of consecutive full width outputs the generator produced from its seed, the number of high order bytes taken from each later output to form keystream, and the ciphertext in hexadecimal. The modulus, the multiplier, and the increment are all secret, and the multiplier is never one. The keystream is drawn from the outputs that come after the published run, so the published outputs are not themselves the keystream. The full contract, covering the recurrence, the input fields, the keystream rule, the encryption, and the plaintext shape, is in /app/environment/docs/CHALLENGE.md, and everything graded is stated there, so read it first. Grading uses a family of fresh challenges, not the one in front of you, so a recovery that only guesses the visible message will not pass. A Rust program lives at /app/environment, with the input parsing and output path already in place and the recovery left for you in /app/environment/src/main.rs. Build it with the provided Makefile. It takes one challenge file path as its argument and prints the recovered plaintext on one line, exiting zero, while malformed input prints the single line ERROR and exits one. Output is compared byte for byte, so print nothing else.

Required artifacts include: `/app/environment/docs/CHALLENGE.md`, `/app/environment`, `/app/environment/src/main.rs`.

Author anonymous tagged this **medium** security task (lcg, prng, stream-cipher, keystream-recovery, cryptanalysis).

Time estimates: expert ~150 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `9fa4d98a-7392-42bc-80f9-4a8cec627a09_submission_2026-07-19T13_27_55.675Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
