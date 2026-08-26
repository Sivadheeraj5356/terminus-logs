# Topology service notes

The local topology sidecar speaks plain HTTP/1.1 on a loopback TCP port chosen at process start. The bind address is not written to a published config file.

Known routes:

- `GET /v1/topology` — JSON document with `start`, `exit`, and `rooms` adjacency maps
- `GET /v1/health` — liveness probe (`{"ok":true}`)

The service process title is `chamberd`. Startup tooling may leave an open-syscall trace beside the pid file for operators investigating which vault object was loaded.

The escape entrypoint stops any prior listener recorded in the pid file before binding a new port. Manifest api_evidence must describe the listener identified by that pid file, not an older chamberd instance that may still be shutting down from a previous run.
