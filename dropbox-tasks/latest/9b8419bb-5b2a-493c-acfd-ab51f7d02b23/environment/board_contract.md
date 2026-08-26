# Board review workspace

`boardctl` loads a mission record directory and a policy JSON, consults persistent
review state, and regenerates board artifacts under the chosen output directory.
Operators rebuild with `go build -o /app/bin/boardctl ./cmd/boardctl` from
`/app/environment` and `cargo build --release --locked --manifest-path
/app/environment/z4/Cargo.toml` for the index helper under `z4/` (release binary
installed as `/app/bin/ixcore`). Follow-up reviews that leave the open commitment
id set unchanged apply stagnation_penalty 8 inside the index helper; other
successful reviews apply 0.
