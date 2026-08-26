#!/bin/bash
set -euo pipefail

mkdir -p /app/task_file/output /tmp/credential-rotation-oracle
g++ -std=c++20 -O2 \
    /solution/credential_rotation_main.cpp \
    -o /tmp/credential-rotation-oracle/solver
/tmp/credential-rotation-oracle/solver \
    /app/task_file/scan_input/credential_incident.txt \
    /app/task_file/output/credential_schedule.json
/tmp/credential-rotation-oracle/solver \
    /app/task_file/scan_input/credential_incident_b.txt \
    /app/task_file/output/credential_schedule_b.json
/tmp/credential-rotation-oracle/solver \
    /app/task_file/scan_input/credential_incident_c.txt \
    /app/task_file/output/credential_schedule_c.json
