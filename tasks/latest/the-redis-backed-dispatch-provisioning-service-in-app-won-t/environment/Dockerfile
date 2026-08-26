FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

# System dependencies: the Redis engine + CLI for the dispatch keyspace, Python
# for the verifier, and the tmux/asciinema tooling the agent harness requires.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3 \
        python3-pip \
        redis-server \
        redis-tools \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# Verifier-only Python dependencies, baked so tests run with no network access.
RUN pip3 install --no-cache-dir --break-system-packages \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        redis==5.0.8

WORKDIR /app

# Install Node dependencies first so this layer is cached across source edits.
COPY app/package.json /app/package.json
RUN npm install --no-audit --no-fund \
    && npm cache clean --force

# Application source (the complete dispatch service) and its configuration.
COPY app/src/ /app/src/
COPY app/scripts/ /app/scripts/
COPY app/data/ /app/data/
COPY app/test/ /app/test/
COPY app/config/ /app/config/

# Build the dispatch configuration archive from visible source files so the
# override bundle ships as a real tarball the service unpacks at runtime.
COPY app/config-src/ /app/config-src/
RUN tar --sort=name --mtime='2024-01-01 00:00:00Z' --owner=0 --group=0 --numeric-owner \
        -czf /app/dispatch-config.tar.gz -C /app/config-src . \
    && rm -rf /app/config-src

ENV NODE_PATH=/app/node_modules
ENV DISPATCH_WORKDIR=/app/work
