#!/bin/bash
# Hard old-space ceiling for memory-budget workloads (strictly below 15 MiB budget).
exec node --max-old-space-size=14 /app/run_entry.js "$@"
