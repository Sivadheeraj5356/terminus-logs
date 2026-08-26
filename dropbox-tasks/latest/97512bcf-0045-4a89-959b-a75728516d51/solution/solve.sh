#!/bin/bash
set -euo pipefail

cd /app
cp /solution/correct/eos.c /app/src/eos.c
cp /solution/correct/sorption.c /app/src/sorption.c
cp /solution/correct/condense.c /app/src/condense.c
cp /solution/correct/calibrate.c /app/src/calibrate.c
cp /solution/correct/chamber.c /app/src/chamber.c
cp /solution/correct/cli.c /app/src/cli.c
cp /solution/correct/species.json /app/config/species.json
cp /solution/correct/chamber.toml /app/config/chamber.toml
make -C /app clean all
test -x /app/bin/cryovac
/app/bin/cryovac \
  --profile /app/data/profiles/n2_he_cooldown.json \
  --calibration /app/data/calibration/sorption_cal.ndjson \
  --out /app/vacuum_simulation.json \
  --volume 0.012
