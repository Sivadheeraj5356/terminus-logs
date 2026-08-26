# Developer workflows

`/app/scripts/dev-build` compiles the workspace in release mode using the
checked-in lockfile and vendored sources. `/app/scripts/dev-check` builds and
runs the language smoke checks (Rust unit behavior, the Python source smoke, and
the Node source smoke) against the developer build.

Developers may set `VELLUM_DEV_CAPS` to experiment with additional capability
names in local builds, `VELLUM_NATIVE` to point the Python bindings at an
out-of-tree `libvellum.so`, and `VELLUM_CLI` to point the Node bindings at an
out-of-tree `vellum-cli`. These are developer conveniences only and must never
influence a release.

`/app/scripts/inspect-bundle <dir>` loads a release bundle and prints the
identity records and inventory digest for each surface. It is a diagnostic aid
and is not authoritative.
