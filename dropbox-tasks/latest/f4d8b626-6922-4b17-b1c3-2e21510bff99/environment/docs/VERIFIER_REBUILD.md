# Release rebuild contract

Before behavioral checks run, the harness invokes rebuild-expeditctl from /opt/verifier-scripts. That step recompiles /app/src and replaces /app/target/release/expeditctl.

Implement graded pipeline behavior by editing Rust sources under /app/src. Copying a script or binary into target/release without updating those sources will not persist through rebuild.

Cargo and the project manifest under /app remain available during agent work. After source changes, cargo build --release must succeed locally the same way the harness rebuild does.
