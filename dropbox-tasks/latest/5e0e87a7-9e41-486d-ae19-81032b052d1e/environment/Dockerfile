FROM public.ecr.aws/docker/library/ubuntu:24.04@sha256:0d39fcc8335d6d74d5502f6df2d30119ff4790ebbb60b364818d5112d9e3e932

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    golang-go=2:1.22~2build1 \
    tmux=3.4-1ubuntu0.1 \
    asciinema=2.4.0-1 \
    python3=3.12.3-0ubuntu2.1 \
    python3-venv=3.12.3-0ubuntu2.1 \
    ca-certificates=20260601~24.04.1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock

RUN python3 -m venv /opt/verifier-venv && \
    /opt/verifier-venv/bin/pip install --no-cache-dir \
    --require-hashes \
    -r /tmp/requirements.lock

WORKDIR /app

COPY task_file/go.mod /app/go.mod
COPY task_file/main.go /app/main.go
COPY task_file/containment/bundle.json /app/containment/bundle.json
COPY task_file/containment/QUARANTINE_POLICY.md /app/containment/QUARANTINE_POLICY.md
