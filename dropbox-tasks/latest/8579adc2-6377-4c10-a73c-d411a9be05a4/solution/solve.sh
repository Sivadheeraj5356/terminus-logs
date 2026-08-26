#!/bin/bash
set -euo pipefail

cd /app/environment

for f in stream session; do
    patch -p1 < "/solution/patches/$f.cc.patch"
done

cp /solution/security_notes.md security_notes.md

make clean
make

echo "oracle: solve.sh complete"
