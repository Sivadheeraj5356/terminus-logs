# Authenticated Beacon Incident Reconstruction

This is an offline security-forensics and incident-reconstruction task. A monitoring station lost its trusted state after suspected telemetry forgery, replay, and cross-station credential misuse. Recover the final trusted sensor dataset from the remaining untrusted binary beacon stream without allowing damaged, stale, unauthenticated, or invalidated evidence to alter later security decisions.

Produce a single C11 source file at `/app/src/beacon_replay.c`. The recovery host has only gcc and libc. The verifier compiles and runs it as:

```text
gcc -O2 -std=c11 /app/src/beacon_replay.c -o /app/beacon_replay
/app/beacon_replay <frames_file>
```

The complete normative evidence format and trust-reconstruction contract are in `/app/spec/beacon_frames.md`. Follow that specification exactly. In particular, replay complete frames in physical order, apply integrity and authentication checks before mutating trusted state, decode Beacon-X records only at the specified stage, maintain independent anti-replay and credential histories, honor hierarchical and cross-station credential invalidation, and emit the exact forensic summary and trusted active-sensor dataset described by the specification.

Rejection categories are part of the required output contract, not interchangeable diagnostics. Pay particular attention to the station-beacon exception: for a type-5 station beacon, an invalid decoded authentication word is a decoded record-shape failure and must be counted as `bad_layout`, before freshness or dependency processing. It is never `dependency`. In contrast, after a snapshot, delta, or delete passes layout and freshness, its missing or mismatched beacon tag (including when carry-auth is selected) is `dependency`. The specification states the complete precedence and the corresponding cases.

The verifier supplies one readable regular evidence file and may generate many different authentic, corrupted, replayed, forged, and dependency-invalid streams. Inputs contain at most 4096 distinct `(station, sensor)` keys. Accepted delta sums fit signed 32-bit range and final calibration arithmetic fits signed 64-bit range. A trailing fragment is part of forensic accounting as defined in the specification.

The visible fixture is `/app/input_data/public_frames.bin`; `/app/input_data/public_frames.sha256` protects it from modification. Do not edit either input artifact. The specification includes the fixture's expected output as a format and sanity check, but hidden streams require general replay logic.

Write replay results to stdout with no additional lines except optional leading `#` comments. Usage, open, or read failures outside verifier inputs must return nonzero and may write a diagnostic to stderr.
