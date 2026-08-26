# latmon

`latmon` is a small offline command-line tool. It reads one JSON scenario of
per-endpoint latency (ms) samples on standard input and writes a canonical JSON
alarm ledger on standard output.

```
go build -o latmon ./cmd/latmon
./latmon < scenario.json > ledger.json
```

Each scenario replays a piecewise-constant stream of samples against per-endpoint
limits. `latmon` tracks arm and reset dwell timers, honors service windows, keeps a
cumulative alarm-second budget, and reports the confirmed over-limit alarms, the
cumulative confirmed alarm-time, a one-way lockout instant, and every endpoint's
final state at the horizon.

The scenario-to-ledger computation is in
[internal/engine/engine.go](internal/engine/engine.go); `cmd/latmon/main.go` only
handles standard input, standard output, and the exit status.
