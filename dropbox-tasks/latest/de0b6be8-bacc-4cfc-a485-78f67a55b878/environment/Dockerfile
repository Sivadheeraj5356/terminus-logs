FROM --platform=linux/amd64 public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV CARGO_INCREMENTAL=0
ENV PATH="/usr/local/cargo/bin:/opt/verifier-venv/bin:/usr/local/bin:/usr/bin:/bin"
ENV TMUX_TMPDIR=/app/.tmux
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN apt-get update \
 && apt-get install -y --no-install-recommends asciinema ca-certificates coreutils gcc python3 python3-venv tmux \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
COPY docs ./docs
COPY fixtures ./fixtures
COPY scripts/verifier-rebuild.sh ./scripts/verifier-rebuild.sh
RUN chmod +x /app/scripts/verifier-rebuild.sh \
 && mkdir -p /app/state /app/output /app/.tmux /opt/verifier-fixtures \
 && chmod 1777 /app/.tmux \
 && cargo build --release --locked \
 && install -m 0755 target/release/threatcomp /usr/local/bin/threatcomp
