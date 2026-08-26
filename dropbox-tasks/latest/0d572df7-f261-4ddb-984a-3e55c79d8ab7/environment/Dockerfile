FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        less \
        nano \
        procps \
        python3 \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes \
        -r /tmp/requirements.lock

COPY task_file/input/ /app/input/
COPY task_file/docs/ /app/docs/
RUN mkdir -p /app/bin /app/output
