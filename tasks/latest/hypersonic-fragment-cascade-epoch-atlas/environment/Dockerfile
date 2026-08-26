FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    asciinema \
    ca-certificates \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir \
    pytest==9.0.3 \
    pytest-json-ctrf==0.5.0

COPY package.json package-lock.json tsconfig.json /app/
RUN npm ci

COPY src /app/src
COPY docs /app/docs
COPY tooling /app/tooling
COPY catalogs /app/catalogs
COPY OVERVIEW.md /app/OVERVIEW.md

RUN python3 /app/tooling/gen_fixtures.py \
 && mkdir -p /opt/verifier-fixtures/flare-trap /opt/verifier-fixtures/chain-reaction \
 && cp -r /app/opt-fixtures/flare-trap/. /opt/verifier-fixtures/flare-trap/ \
 && cp -r /app/opt-fixtures/chain-reaction/. /opt/verifier-fixtures/chain-reaction/ \
 && rm -rf /app/opt-fixtures \
 && chmod +x /app/tooling/build.sh \
 && bash /app/tooling/build.sh

ENV PATH="/app/bin:/opt/verifier-venv/bin:${PATH}"
