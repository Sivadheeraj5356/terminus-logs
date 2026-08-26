#!/usr/bin/env bash
set -u
export PYTHONDONTWRITEBYTECODE=1

chmod 1777 /logs
install -d -m 0700 -o 0 -g 0 /logs/verifier
chown 0:0 /logs/verifier
chmod 0700 /logs/verifier
rm -f -- /logs/verifier/reward.txt /logs/verifier/ctrf.json
printf '0\n' > /logs/verifier/reward.txt

run_verifier() {
    if [ "$(pwd)" != "/app" ]; then
        echo "Tidevault verifier must run from /app" >&2
        return 1
    fi

    /opt/verifier-venv/bin/python -m pytest \
        -o cache_dir=/tmp/pytest-cache \
        --ctrf /logs/verifier/ctrf.json \
        /tests/test_outputs.py -rA && \
        [ -s /logs/verifier/ctrf.json ]
}

run_verifier
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
