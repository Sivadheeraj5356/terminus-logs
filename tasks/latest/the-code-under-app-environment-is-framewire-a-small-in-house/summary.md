# The code under /app/environment is framewire, a small in-house Go library that e

- **UUID:** `63297e27-43ef-403c-8ee1-1532b58e3bf0`
- **Slug:** `the-code-under-app-environment-is-framewire-a-small-in-house`
- **Category:** security
- **Difficulty:** hard

## Summary

The code under /app/environment is framewire, a small in-house Go library that encodes PostgreSQL frontend protocol messages onto the wire. The encoders live under /app/environment/internal/proto, the buffer helpers under /app/environment/internal/wireio, and a command line driver sits at /app/environment/cmd/framewire.

Each message is framed with a one byte type tag and a four byte big endian length prefix, and every well formed message encodes today. Several encoders and the send path can be driven with a crafted message into emitting an oversized or miscounted frame instead of refusing it, and a peer then re splits the stream and treats attacker controlled trailing bytes as a fresh message, which is how an oversized query or bind parameter smuggles a second SQL command past the driver.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
