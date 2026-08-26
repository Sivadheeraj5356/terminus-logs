FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS builder

WORKDIR /build
ENV CARGO_TARGET_DIR=/build/target

COPY Cargo.toml Cargo.lock /build/
COPY src /build/src
COPY proc /build/proc
COPY data /build/data
COPY infer /build/infer
COPY check /build/check

RUN cargo build --release

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    build-essential=12.9 \
    ca-certificates=20230311+deb12u1 \
    coreutils=9.1-1 \
    patch=2.7.6-7 \
    tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY --from=builder /usr/local/cargo /usr/local/cargo
COPY --from=builder /usr/local/rustup /usr/local/rustup

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH="/usr/local/cargo/bin:${PATH}" \
    CARGO_TARGET_DIR=/app/target

COPY --from=builder /build/Cargo.toml /build/Cargo.lock /app/
COPY --from=builder /build/src /app/src
COPY --from=builder /build/proc /app/proc
COPY --from=builder /build/data /app/data
COPY --from=builder /build/infer /app/infer
COPY --from=builder /build/check /app/check
COPY --from=builder /build/target /app/target
COPY docs /app/docs

ENV PATH="/app/target/release:/usr/local/cargo/bin:${PATH}"
