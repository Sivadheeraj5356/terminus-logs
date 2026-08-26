Toolchain notes for the mass-transfer lab.

Go module ot7 lives under /app/environment. Rust crate ot7-core lives under /app/environment/ot7-core. Rebuild with /app/environment/scripts/rebuild.sh. Binaries land in /app/environment/build/: otctl-run, otctl-probe, otctl-audit, otctl-inspect, and ot7-core (stdin/stdout JSON kernel).

The verifier keeps a snapshot of bundled instances at /var/lib/verifier/instances-vault and may restore from it between checks.

Do not add third-party optimal-transport libraries. Use only the Go standard library and the pinned Rust crates already declared in Cargo.toml.
