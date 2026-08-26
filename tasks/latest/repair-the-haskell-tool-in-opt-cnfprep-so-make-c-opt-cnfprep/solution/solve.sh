#!/bin/bash
set -euo pipefail

cp /solution/Main.hs.fixed /opt/cnfprep/src/Main.hs
make -C /opt/cnfprep clean all
