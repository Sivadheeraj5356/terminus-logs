#!/bin/sh
# Replay one recorded event stream through the adjudicator.
set -e
cd "$(dirname "$0")/.."
node bin/windowjudge.js < "${1:?usage: scripts/replay.sh testdata/stream-01.json}"
