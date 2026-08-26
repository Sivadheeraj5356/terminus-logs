# Oracle solve — task identity systemd-socket-fd-pass-start-race token e97f91a6
#!/usr/bin/env bash
# Terminal-Bench Canary 8e9b3d2f-5f6c-7b8d-9e0f-1a2b3c4d5e6f
set -euo pipefail

PATH="/usr/local/cargo/bin:/usr/bin:${PATH}"

cd /solution
patch -d /app -p1 < oracle.patch

cd /app/environment
cargo build --release --locked

for n in 0 1 2 3; do
  /app/environment/tools/k9_invoke --scenario "$n"
done

/app/environment/tools/k9_recover
/app/environment/tools/k9_emit --out /app/output/k9_trace.json
