#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/cargo/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"
cd /app
SOL=/solution/files
[ -d "$SOL" ] || SOL=/task/solution/files
install -m 0644 "$SOL/adjudication/intervals.rs" /app/src/adjudication/intervals.rs
install -m 0644 "$SOL/adjudication/reliability.rs" /app/src/adjudication/reliability.rs
install -m 0644 "$SOL/adjudication/aliases.rs" /app/src/adjudication/aliases.rs
install -m 0644 "$SOL/composition/graph.rs" /app/src/composition/graph.rs
install -m 0644 "$SOL/composition/mod.rs" /app/src/composition/mod.rs
install -m 0644 "$SOL/briefing/mod.rs" /app/src/briefing/mod.rs
cargo build --release --locked
install -m 0755 target/release/threatcomp /usr/local/bin/threatcomp
