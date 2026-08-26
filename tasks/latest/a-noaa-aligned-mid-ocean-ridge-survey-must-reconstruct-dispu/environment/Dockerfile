FROM --platform=linux/amd64 public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive
ENV CARGO_INCREMENTAL=0

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
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

ENV PATH="/opt/verifier-venv/bin:/usr/local/cargo/bin:${PATH}"

WORKDIR /app

COPY Cargo.toml Cargo.lock ./
COPY src ./src
COPY scripts ./scripts
COPY docs ./docs
COPY data/policies ./data/policies
COPY data/dives ./data/dives
COPY data/corpus ./data/corpus

RUN python3 /app/scripts/bootstrap_task.py

RUN mkdir -p /app/state /opt/verifier-scripts \
 && chmod +x /app/scripts/verifier-rebuild.sh \
 && ln -sf /app/scripts/verifier-rebuild.sh /opt/verifier-scripts/rebuild-expeditctl

ENV PATH="/opt/verifier-scripts:${PATH}"

RUN cargo build --release --locked
