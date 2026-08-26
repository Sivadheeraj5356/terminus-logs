#!/bin/bash
# Oracle solution: recover every hidden sheaf binding by REAL PLAY, using ONLY the documented tally
# commands (read / name / bind / next). It holds no stretches and reads no keeper file: it names
# handfuls, reasons about the bound counts under the one-garbled-reply model (keeping every binding
# that disagrees with at most one reply), narrows the survivors, and binds the stretches it deduces.
# It runs as the agent user at grading time and talks to the keeper only over the Unix endpoint.
set -e

export RB_KEEPER_ENDPOINT="${RB_KEEPER_ENDPOINT:-/run/ryebank/ryebank.sock}"

python3 "$(dirname "$0")/oracle_solve.py"
echo "solve complete"
