FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3 \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# App dependencies installed offline from committed lockfile
COPY src/package.json src/package-lock.json /app/
RUN cd /app && npm ci --ignore-scripts

# TypeScript source and project config
COPY src/tsconfig.json /app/
COPY src/src/ /app/src/

# Legacy configs, trace captures, and operations documentation
COPY legacy/ /app/legacy/
COPY traces/ /app/traces/
COPY docs/ /app/docs/

# Output directory the agent writes generated artifacts into
RUN mkdir -p /app/output

# Test-only deps isolated in a venv; kept out of the app/system Python
COPY verifier-requirements.lock /tmp/verifier-requirements.lock
RUN python3 -m venv --system-site-packages /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --require-hashes --no-deps --no-cache-dir \
        -r /tmp/verifier-requirements.lock

WORKDIR /app
