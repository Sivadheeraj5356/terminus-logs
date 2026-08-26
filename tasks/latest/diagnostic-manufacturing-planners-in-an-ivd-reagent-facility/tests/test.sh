#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    exit 1
fi

if [ -d /tests ]; then
    chown root:root /tests
    chmod 700 /tests
fi

if [ -d /tests/verifier-fixtures ]; then
    rm -rf /opt/verifier-fixtures
    cp -R /tests/verifier-fixtures /opt/verifier-fixtures
    chown -R root:root /opt/verifier-fixtures
    chmod -R 700 /opt/verifier-fixtures
fi

cd /app

if [ -x /usr/sbin/runuser ] && id -u agent >/dev/null 2>&1; then
    chown -R agent:agent /app/pom.xml /app/src /app/target 2>/dev/null || true
    runuser -u agent -- mvn -o -q -f /app/pom.xml package -DskipTests -Dmaven.repo.local=/opt/maven-cache/repository || {
        echo "Agent code failed to compile"
        echo 0 > /logs/verifier/reward.txt
        exit 0
    }
    chown agent:agent /app/target/blendcert.jar /app/state /app/output 2>/dev/null || true
else
    mvn -o -q -f /app/pom.xml package -DskipTests || {
        echo "Agent code failed to compile"
        echo 0 > /logs/verifier/reward.txt
        exit 0
    }
fi

/opt/verifier-venv/bin/python -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
