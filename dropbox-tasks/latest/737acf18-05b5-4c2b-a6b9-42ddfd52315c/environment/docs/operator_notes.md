# Offline cargo mirror notes

Active offline registry root is `/app/mirror` (Cargo `local-registry` layout:
`*.crate` files beside an `index/` tree in crates.io index form).

Workspace root is `/app` (`Cargo.toml`, `Cargo.lock`, `src/`).

Source replacement belongs in `/app/.cargo/config.toml` (seeded from `/app/cargo-config.toml` at image build):

```toml
[source.crates-io]
replace-with = "offline-mirror"

[source.offline-mirror]
local-registry = "/app/mirror"
```

Documented offline build:

```bash
/app/scripts/offline_build.sh
```

which runs `cargo build --offline --locked` in `/app`.

Primary package ids (must resolve and compile offline) are listed in
`/app/docs/tgt_notes.txt`. A second tree under `/app/data/mirror-stale` is a
discarded sync snapshot and must not be the active `local-registry`.

Lockfile checksums in `/app/Cargo.lock` must match the sha256 digests of the
corresponding `/app/mirror/*.crate` files. Sparse-style index paths for
hyphenated crate names use the crates.io layout (for example `cfg-if` lives at
`index/cf/g-/cfg-if`).
