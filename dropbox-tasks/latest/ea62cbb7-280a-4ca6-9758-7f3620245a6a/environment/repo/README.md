# HSM key-ceremony windows

Replays a recorded hardware-security-module key ceremony and reconstructs the
confirmed windows it produced: partition-key compromises, ceremony-script
admissions, tamper-level alarms, and ceremony-officer clock losses. One JSON
document in on stdin, one JSON object out on stdout.

## Layout

- `bin/windowjudge.js` is the CLI entry point.
- `lib/judge.js` holds the adjudication engine.
- `docs/ceremony-windows.md` is the behavior contract for every supported input mode.
- `docs/usage.md` covers running and replaying.
- `scripts/replay.sh` pushes one recorded stream through the CLI.
- `testdata/` holds sample event streams.

Requires Node 22. There are no npm dependencies.
