#!/bin/bash
set -euo pipefail

cd /app
patch -p1 < /solution/fix.patch
make dist/isoreg.built
