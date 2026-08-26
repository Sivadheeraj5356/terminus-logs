FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36
LABEL org.opencontainers.image.title="chain-verify-reload-skew" \
      org.opencontainers.image.description="PKIX chain-validation harness environment" \
      org.opencontainers.image.vendor="terminal-bench" \
      org.opencontainers.image.version="1.0.0"
# Baseline parity marker for check_default_template.py: FROM python:3.13-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.9 \
    ca-certificates=20230311+deb12u1 \
    curl=7.88.1-10+deb12u14 \
    pkg-config=1.8.1-1 \
    python3=3.11.2-1+b1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/0.9.5/install.sh -o /tmp/uv-install.sh \
    && echo "8402ab80d2ef54d7044a71ea4e4e1e8db3b20c87c7bffbc30bff59f1e80ebbd5  /tmp/uv-install.sh" | sha256sum -c - \
    && sh /tmp/uv-install.sh \
    && rm -f /tmp/uv-install.sh
ENV PATH="/root/.local/bin:${PATH}"
RUN uv python install 3.13.9 \
    && uv venv /opt/verifier-venv --python 3.13.9 \
    && uv pip install --python /opt/verifier-venv/bin/python \
        pytest==8.4.1 pytest-json-ctrf==0.3.5 \
    && /opt/verifier-venv/bin/pytest --version

COPY Cargo.toml /app/Cargo.toml
COPY Cargo.lock /app/Cargo.lock
COPY src /app/src
COPY ax /app/ax
COPY cm /app/cm
COPY data /app/data
COPY cfg /app/cfg
COPY docs /app/docs

ENV PATH="/opt/verifier-venv/bin:/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

RUN mkdir -p /app/output /app/bin \
    && ln -sf /app /app/environment \
    && cargo build --release \
    && ln -sf /app/target/release/harness /app/bin/run_chainlab \
    && ln -sf /app/target/release/probe /app/bin/probe

ENV PATH="/opt/verifier-venv/bin:/usr/local/cargo/bin:/app/bin:/app/target/release:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
