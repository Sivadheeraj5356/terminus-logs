# syntax=docker/dockerfile:1.7

# ---------------------------------------------------------------------------
# Stage 1: vendor Rust crates (canonical Rust image, digest-pinned)
# ---------------------------------------------------------------------------
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS vendor

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        pkg-config \
        libssl-dev \
        build-essential \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/scaffold
COPY vault_scaffold/Cargo.toml vault_scaffold/Cargo.lock ./
RUN mkdir src \
    && printf '%s\n' 'fn main() {}' > src/main.rs \
    && mkdir -p /opt/cargo-vendor \
    && cargo fetch --locked \
    && cargo vendor --versioned-dirs /opt/cargo-vendor

# ---------------------------------------------------------------------------
# Stage 2: sanctioned Python runtime with offline Rust toolchain
# ---------------------------------------------------------------------------
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        pkg-config \
        libssl-dev \
        ca-certificates \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --require-hashes --no-deps \
    -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.lock

COPY --from=vendor /usr/local/cargo /usr/local/cargo
COPY --from=vendor /usr/local/rustup /usr/local/rustup
COPY --from=vendor /opt/cargo-vendor /opt/cargo-vendor

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && ln -sf /usr/local/cargo/bin/rustup /usr/local/bin/rustup \
    && printf '%s\n' 'export PATH="/usr/local/cargo/bin:$PATH"' > /etc/profile.d/rust-cargo.sh \
    && mkdir -p /app/bin /app/output /app/seal_authz

WORKDIR /app

COPY vault_scaffold/Cargo.toml /app/vault_scaffold/Cargo.toml
COPY vault_scaffold/Cargo.lock /app/vault_scaffold/Cargo.lock
COPY vault_scaffold/.cargo/config.toml /app/vault_scaffold/.cargo/config.toml
COPY vault_scaffold/src/main.rs /app/vault_scaffold/src/main.rs
COPY data /app/data
COPY scripts/materialize_dek.py /tmp/materialize_dek.py

RUN python3 /tmp/materialize_dek.py \
    && rm -f /tmp/materialize_dek.py

WORKDIR /app
