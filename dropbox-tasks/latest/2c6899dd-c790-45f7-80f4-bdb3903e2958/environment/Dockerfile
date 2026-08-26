FROM rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    coreutils=9.1-1 \
    tmux=3.3a-3 \
    patch=2.7.6-7 \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5 \
    pytest-randomly==3.16.0

COPY Cargo.toml Cargo.lock /app/
COPY k3 /app/k3
COPY v7 /app/v7
COPY s2 /app/s2
COPY booth /app/booth
COPY data /app/data
COPY docs /app/docs
COPY README.md /app/README.md

RUN cargo build --release --locked \
    && mkdir -p /app/output/runs

ENV PATH="/usr/local/bin:${PATH}"
ENV CARGO_TARGET_DIR=/app/target
