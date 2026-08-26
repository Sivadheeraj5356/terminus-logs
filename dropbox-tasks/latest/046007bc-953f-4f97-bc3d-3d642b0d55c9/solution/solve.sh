#!/bin/bash
set -euo pipefail

cd /app/environment

for f in varint.c super.c regtab.c vol.c inode.c link.c xattr.c; do
    cp "/solution/fixed/src/$f" "src/$f"
done

make clean
make

echo "oracle: solve.sh complete"
