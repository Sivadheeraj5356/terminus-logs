# Vendored build tools

Pinned offline install artifacts used by `Dockerfile`. Digests are verified
with `sha256sum` before extract; builds do not curl these files.

| File | Source | SHA-256 |
|------|--------|---------|
| `uv-x86_64-unknown-linux-gnu-0.9.5.tar.gz` | astral-sh/uv release `0.9.5` | `2cf10babba653310606f8b49876cfb679928669e7ddaa1fb41fb00ce73e64f66` |
| `cargo-audit-x86_64-unknown-linux-gnu-v0.21.0.tgz` | rustsec/rustsec release `cargo-audit/v0.21.0` | `843cadb5350064451c23847881cfa510d18da21506554e822e4a647082b362b0` |
