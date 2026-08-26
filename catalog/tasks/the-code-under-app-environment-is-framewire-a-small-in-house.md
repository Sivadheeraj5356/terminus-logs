# The code under /app/environment is framewire, a small in-house Go library that e

Submission: `63297e27-43ef-403c-8ee1-1532b58e3bf0`  
Slug: `the-code-under-app-environment-is-framewire-a-small-in-house`  
Latest archive: `63297e27-43ef-403c-8ee1-1532b58e3bf0_submission_2026-07-12T14_56_35.018Z.zip`  
Revisions in Dropbox: 1

## Task summary

The code under /app/environment is framewire, a small in-house Go library that encodes PostgreSQL frontend protocol messages onto the wire. The encoders live under /app/environment/internal/proto, the buffer helpers under /app/environment/internal/wireio, and a command line driver sits at /app/environment/cmd/framewire. Each message is framed with a one byte type tag and a four byte big endian length prefix, and every well formed message encodes today. Several encoders and the send path can be driven with a crafted message into emitting an oversized or miscounted frame instead of refusing it, and a peer then re splits the stream and treats attacker controlled trailing bytes as a fresh message, which is how an oversized query or bind parameter smuggles a second SQL command past the driver. Audit the encoders, the shared header helper, the buffer helpers, and the send path. Close every place where a length or count taken from a message is used to size, index, or advance a buffer without being validated against the limit that applies to it, and every place where the arithmetic meant to enforce that limit can itself pass when it should fail. Do not assume one weakness per file, that a file holds exactly one, or that an encoder that already performs a size check is safe. The number of fixes is yours to work out, and a limit that one message enforces may be the limit another message forgets.

Required artifacts include: `/app/environment`, `/app/environment/internal/proto`, `/app/environment/internal/wireio`, `/app/environment/cmd/framewire`, `/app/environment/docs/security-spec.md`, `/app/environment/testdata`, `/app/environment/security_notes.md`.

Author anonymous tagged this **hard** security task (security, go, integer-overflow, protocol, audit-and-patch).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 600s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `63297e27-43ef-403c-8ee1-1532b58e3bf0_submission_2026-07-12T14_56_35.018Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
