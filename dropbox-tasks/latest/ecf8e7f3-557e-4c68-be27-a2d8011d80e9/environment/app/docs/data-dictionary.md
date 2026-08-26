# Data dictionary

release_matrix.csv: lane,retention_hops
lanes/<lane>.json: may include decoys not listed in the matrix
deps.csv: lane,coordinate,provide,version,source_url,source_hash,patch_url
  — repaired rows use file:// pnpm-store URLs, `sha256:` digests, and empty patch_url
pins.csv: wrap,version,sha256
mirrors.csv: basename
xor.csv: lane,group,provide
bans.csv: coordinate
forbidden-hosts.csv: host
artifacts.csv / edges.csv: lane-scoped graph inputs
workspace inventory: ordered by sorted `/app/crates/*/Cargo.toml` path (directory may differ from package name; `aa-graph` → `pnpmfix-graph`)
LICENSES.txt: sorted basename concat of `/app/licenses/*`; each file raw contents + one extra `\n`
