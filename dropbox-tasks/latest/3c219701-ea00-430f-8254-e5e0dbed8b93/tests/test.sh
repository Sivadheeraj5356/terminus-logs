#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
touch /app/tariff/src/main.rs
rm -f /app/tariff/target/release/tariff
cd /app/tariff && CARGO_NET_OFFLINE=true cargo build --offline --locked --release || rm -f /app/tariff/target/release/tariff
python3 -m pytest -o cache_dir=/tmp/pytest_cache --ctrf /logs/verifier/ctrf.json /tests/test_m1.py /tests/test_m2.py /tests/test_m3.py /tests/test_m4.py /tests/test_m5.py -rA
rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
