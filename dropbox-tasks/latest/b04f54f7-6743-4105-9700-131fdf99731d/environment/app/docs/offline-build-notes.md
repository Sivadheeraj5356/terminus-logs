All Rust crates are local workspace crates; Cargo must run locked and offline. Cargo is installed at `/usr/local/cargo/bin/cargo`. A sparse caller environment may omit that directory, so `/app/scripts/release.sh` must prepend `/usr/local/cargo/bin` before invoking Cargo.

Do not fetch packages, regenerate the lockfile, or call network package managers from the release path. The build uses the checked-in workspace, the checked-in `Cargo.lock`, and the Rust toolchain already present in the image.
