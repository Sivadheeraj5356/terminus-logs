FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema \
    ca-certificates \
    git \
    lua5.1 \
    python3 \
    python3-venv \
    sqlite3 \
    tmux \
    && rm -rf /var/lib/apt/lists/*

COPY verifier-requirements.lock /tmp/verifier-requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/verifier-requirements.lock

WORKDIR /app

COPY scripts/ /app/scripts/
RUN chmod +x /app/scripts/build-sklearn-mirror.sh \
    && bash /app/scripts/build-sklearn-mirror.sh

COPY bin/ /app/bin/
COPY config/ /app/config/
COPY compose/ /app/compose/
COPY data/ /app/data/
COPY fixtures/ /app/fixtures/
COPY docs/ /app/docs/
COPY archives/ /app/archives/
COPY registry/ /app/registry/
COPY src/ /app/src/

RUN chmod +x /app/bin/atlas-promote \
    && sqlite3 /app/data/eval.db < /app/data/init.sql \
    && rm /app/data/init.sql \
    && mkdir -p /app/output /logs/verifier
