# Toolchain paths

Rebuild and replay scripts may invoke compiled-language toolchains. If a command
is not on the default shell `PATH`, use the full path or export `PATH` in the
image Dockerfile.

Typical Go toolchain paths in this image:

- `/usr/local/go/bin/go`

When `go build` is required to regenerate verifier output, confirm the
toolchain is reachable before declaring the task complete.
