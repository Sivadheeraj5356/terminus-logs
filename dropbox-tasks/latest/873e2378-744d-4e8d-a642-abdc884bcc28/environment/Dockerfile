# Faddeeva line-shape engine task (Node).
#
# Ships a short spec and a sample request batch under /app. The agent writes
# /app/faddeeva.js to evaluate the Faddeeva function w(z) over request batches.
# Everything runs offline: Node is the working language, and Python is present
# only so the verifier's pytest can drive the program and grade it.
#
# Canonical Debian base, digest-pinned.
FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

# Node for the task, tmux + asciinema for the agent runtime, and a Python 3 the
# verifier runs on. Installed at build time (build has network) so the task runs
# fully offline afterwards. Debian ships the interpreter as `nodejs`; add a
# `node` on PATH so the documented command works.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        nodejs \
        python3 \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/nodejs /usr/local/bin/node

# The verifier only needs pytest to run the program and compare numbers. No
# numerical libraries are installed for Python, so the math cannot be shifted out
# of Node. Pinned and baked in now; nothing is fetched later.
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5
ENV PATH="/opt/venv/bin:${PATH}"

# The value definition, request schema, and accuracy target, plus a visible
# sample batch to run against.
COPY spec.md /app/spec.md
COPY requests.jsonl /app/requests.jsonl

WORKDIR /app
