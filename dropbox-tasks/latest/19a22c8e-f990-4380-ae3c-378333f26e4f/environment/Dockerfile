# Canonical Terminal-Bench Node.js base, digest-pinned for reproducibility.
FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

ENV DEBIAN_FRONTEND=noninteractive
COPY requirements.lock /tmp/requirements.lock
RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        git \
        ripgrep \
        patch \
        make \
        unzip \
        curl \
        ca-certificates \
        python3 \
        python3-venv \
    && python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock \
    && rm -rf /var/lib/apt/lists/*

# Expose the verifier's Python (venv with pytest) as python3 via a wrapper
# script so the test harness can call `python3 -m pytest` unchanged. The base
# image ships a system python3, so overriding it with a wrapper (not a symlink)
# keeps the venv interpreter authoritative for the verifier.
RUN printf '#!/bin/sh\nexec /opt/verifier-venv/bin/python "$@"\n' > /usr/local/bin/python3 \
    && chmod 0755 /usr/local/bin/python3
ENV VERIFIER_PYTHON=/opt/verifier-venv/bin/python

WORKDIR /app
COPY repo/ /app/

# Expose the isoreg launcher on PATH so the verifier invokes one command.
RUN install -m 0755 /app/isoreg /usr/local/bin/isoreg

# Warm the build so the agent's post-edit rebuild is incremental. The warm
# build type-checks the placeholder; the verifier rebuilds from source, so the
# fixed solution is graded on solve and the placeholder on the no-op run.
RUN make dist/isoreg.built && rm -f /app/dist/isoreg.built

# Make /app a git repo so agent edit tooling (git apply / git diff) works.
RUN git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && printf '/dist\n/node_modules\n' > /app/.gitignore \
    && git add -A \
    && git commit -q -m "initial task state"
