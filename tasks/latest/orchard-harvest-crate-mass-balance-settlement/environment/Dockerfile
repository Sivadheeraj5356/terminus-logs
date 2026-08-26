FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive
ENV CARGO_HOME=/usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup
ENV PATH=/usr/local/cargo/bin:/app/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    ORCHARD_APP_ROOT=/app \
    TB_APP_ROOT=/app

RUN apt-get update && apt-get install -y --no-install-recommends make=4.3-4.1 python3=3.11.2-1+b1 python-is-python3=3.11.2-1+deb12u1 openssl=3.0.17-1~deb12u2 \
    ca-certificates=20230311+deb12u1 \
    coreutils=9.1-1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    python3-pip=23.0.1+dfsg-1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-test.lock /tmp/requirements-test.lock
RUN python3 -m pip install --no-cache-dir --break-system-packages \
    --require-hashes --no-deps -r /tmp/requirements-test.lock

WORKDIR /app

COPY Cargo.toml Cargo.lock /app/
COPY hv /app/hv
COPY st /app/st
COPY fx /app/fx
COPY data /app/data
COPY docs /app/docs
COPY Makefile /app/Makefile
COPY rust-toolchain.toml /app/rust-toolchain.toml

RUN cd /app \
    && cargo fetch --locked \
    && CARGO_PROFILE_RELEASE_LTO=false CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16 \
       make APP_ROOT=/app all \
    && rm -rf /app/target

RUN mkdir -p /app/output
