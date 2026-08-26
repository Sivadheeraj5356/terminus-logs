#!/bin/bash
cd /app
make
./build/chess960_perft
cat /app/output.json
