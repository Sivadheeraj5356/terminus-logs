FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux asciinema bash util-linux git ripgrep jq patch make \
    python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY repo /app/
RUN chmod +x /app/uritmpl

RUN git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && git commit -q -m "initial task state"

RUN npm ci --no-audit --no-fund \
    && make
