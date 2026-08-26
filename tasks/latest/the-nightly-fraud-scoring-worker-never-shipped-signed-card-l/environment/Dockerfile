# Single-stage GCC runtime: agents compile /app/risk_worker from source at task time.
FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

LABEL org.opencontainers.image.title="openssl-verified-c-risk-scoring-worker"
LABEL org.opencontainers.image.description="C fraud scoring worker with OpenSSL and SQLite"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        openssl \
        libssl-dev \
        libsqlite3-dev \
        python3 \
        python3-pip \
        tmux \
        asciinema \
        sqlite3 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app

COPY app/config/ /app/config/
COPY app/schema.sql /app/schema.sql
COPY app/seed.sql /app/seed.sql
COPY app/scripts/ /app/scripts/
COPY app/data/policy/ /app/data/policy/

RUN python3 /app/scripts/gen_ledger.py \
    && rm -rf /app/scripts

RUN mkdir -p /var/lib/ops \
    && sqlite3 /var/lib/ops/ops.db < /app/schema.sql \
    && sqlite3 /var/lib/ops/ops.db < /app/seed.sql

WORKDIR /app
