# Escape pipeline overview

The run_escape.sh entrypoint performs four stages in order:

1. Compile desk_k from the Rust workspace under /app/environment with a release build.
2. Stop any prior chamberd listener via stop_escape.sh so a fresh topology service can bind.
3. Launch chamberd on an ephemeral TCP port and record its pid in /tmp/chamberd.pid.
4. Execute desk_k with runner.toml to query live topology, walk the vault graph from start to exit, and write /app/output/route_manifest.json.

The desk_k binary must discover the listener port and open graph path from live process evidence rather than static vault hints. Manifest api_evidence must match the listener identified by the pid file after stop_escape.sh runs.
