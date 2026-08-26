# Toolchain paths

Rebuild and replay scripts may invoke compiled-language toolchains. If a command
is not on the default shell `PATH`, use the full path or export `PATH` in the
image Dockerfile.

Common install locations in Edition 2 debugging images:

- Go: `/usr/local/go/bin/go`
- Rust: `/usr/local/cargo/bin/cargo` and `/usr/local/cargo/bin/rustc`

When `go build`, `cargo build`, or `make` is required to regenerate verifier
output, confirm the toolchain is reachable before declaring the task complete.
