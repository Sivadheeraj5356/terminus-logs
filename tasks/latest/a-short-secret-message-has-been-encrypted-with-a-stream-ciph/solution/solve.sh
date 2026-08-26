#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

cp "$HERE/files/main.rs" /app/src/main.rs
make -C /app

printf 'width=48\nkeystream_high_bytes=1\noutputs=45922310947941,53228946506189,3768930122949,58918461746632,111369640371733,30111167430872,183946915986436,56617359577157,138335622570381,108179008431661\nciphertext=0e262c0bcef400757bb27316380b5a20bc304ad15a56e36efa7009f46e76f530055646493432f5f930e7c9220c03317e4a7f61cc4c1475f0\n' > /tmp/lcg_smoke.txt
out="$(/app/lcgrecover /tmp/lcg_smoke.txt)"
if [ "$out" != "FLAG{SIYY3ZA4vSy-rkPUJJ5XNnPuCv5lVoQXKyMMvayZjb4YZZBoE9}" ]; then
    echo "oracle smoke failed: got '$out'" >&2
    exit 1
fi
