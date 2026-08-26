#!/bin/bash
# Container entrypoint. Runs as root at container start (the agent harness may override the
# keepalive command, but never the ENTRYPOINT). It starts the keeper as root in the background, then
# hands control to the keepalive command so the container stays alive. The tally never runs this
# script: the harness runs the tally commands as the unprivileged `agent` user via docker exec.
# The keeper owns the hidden stretches (root-only) and answers only the documented game commands;
# there is no privileged reveal path, so the only way to learn a binding is to play the game.
set -u

# Start the keeper FIRST so its game endpoint is bound immediately: it binds /run/ryebank and
# answers "warming up" until the secret is on disk. Binding before generation prevents any
# connection-refused at container start (which the harness reads as an environment failure).
RB_KEEPER_ENDPOINT=/run/ryebank/ryebank.sock \
RB_KEEPER_LEDGER=/run/ryebank/ledger.json \
RB_KEEPER_SECRET=/opt/keeper/secret.json \
  /opt/keeper/keeper >/opt/keeper/keeper.log 2>&1 &

# Generate THIS session's hidden stretches as root, concurrently with the keeper coming up. The
# generator draws from OS randomness (os.urandom via random.SystemRandom) constrained to the hard
# regime by rejection sampling on a PRECOMPUTED integer board, and writes the secret root-only 0400
# in well under a second. The keeper picks it up the instant it appears. No answer literal ships in
# the image; each session is a fresh, unpredictable draw.
RB_KEEPER_SECRET=/opt/keeper/secret.json \
  python3 /opt/keeper/generate.py >/opt/keeper/gen.log 2>&1 &

# Hand control to the keepalive command (e.g. sleep infinity), still as root.
exec "$@"
