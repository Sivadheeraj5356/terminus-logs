## Problem

Offline workspace builds against the air-gapped crate mirror fail. `cargo build --offline --locked` cannot resolve or verify the packages listed for this lane even though crate tarballs appear present under the mirror trees. A discarded sync snapshot under `/app/data/mirror-stale` still looks plausible and must not be trusted as the active registry.

## Requirements

Restore offline Cargo source replacement and the active local registry so the documented offline build succeeds for every primary package id. Stay offline (`allow_internet` is false). Hand-writing `target/` artifacts or a `vendor/` tree without going through Cargo does not pass: the verifier runs `cargo build --offline --locked` from `/app` and scores that toolchain result.

Remote/registry wiring is Cargo source replacement to a filesystem `local-registry`. The active registry root must be `/app/mirror`. Primary package ids are the comma-separated list in `/app/docs/tgt_notes.txt`; each must resolve from the active mirror, match the corresponding `/app/Cargo.lock` checksum against the on-disk `.crate` sha256, and compile into the workspace package `h9_fixture`.

A second identical offline locked build must also succeed (idempotent toolchain result).

## Build Command

From `/app`, run `/app/scripts/offline_build.sh` (equivalent to `cargo build --offline --locked`).

## Schema References

Mirror layout, `local-registry` config shape, hyphenated index paths, and checksum identity rules are documented in `/app/docs/operator_notes.md`.

## Validation Rules

When the offline build is coherent:

- `cargo build --offline --locked` exits 0
- a second identical offline locked build also exits 0
- every primary package id is present in `Cargo.lock` with a checksum equal to sha256 of `/app/mirror/<name>-<version>.crate`
- `.cargo/config.toml` points `local-registry` at `/app/mirror` (not `/app/data/mirror-stale`)
