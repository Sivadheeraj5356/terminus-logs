FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

LABEL org.opencontainers.image.revision="local" \
      org.opencontainers.image.created="2026-07-14T00:00:00Z" \
      org.opencontainers.image.version="2.0" \
      org.opencontainers.image.licenses="MIT"

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

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

COPY requirements.lock /tmp/requirements.lock
# The lockfile installs pytest and pytest-json-ctrf for the verifier.
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.lock

COPY main.js /app/main.js
COPY task_file/ /app/task_file/
RUN rm -rf /app/task_file/output && mkdir -p /app/task_file/output
