#!/bin/bash
set -euo pipefail

cd /app/environment

for f in uleb.c sectab.c dyeworksdef.c unit.c tree.c form.c str.c lot.c alloc.c; do
    cp "/solution/fixed/src/$f" "src/$f"
done

make clean
make

echo "oracle: solve.sh complete"
