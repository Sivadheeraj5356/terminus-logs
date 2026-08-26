#!/bin/bash
set -euo pipefail

# All dependencies are already installed in environment/Dockerfile - there are
# no runtime installs, since allow_internet = false blocks this container too.
cp /solution/fold_solution.sml /app/src/fold.sml
/app/build.sh

# Launch from an unrelated directory: everything is resolved by absolute path.
cd /tmp
/app/run.sh /app/data/study.sqlite /app/output/report.json
