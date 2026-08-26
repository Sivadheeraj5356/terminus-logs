FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        python3-venv=3.11.2-1+b1 \
        python-is-python3=3.11.2-1+deb12u1 \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        jq=1.6-2.1+deb12u2 \
        ca-certificates=20230311+deb12u1 \
        procps=2:4.0.2-3 \
        patch=2.7.6-7 \
        build-essential=12.9 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages pytest==8.3.4 pytest-json-ctrf==0.3.5

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir pytest==8.3.4 pytest-json-ctrf==0.3.5

ENV PATH="/opt/verifier-venv/bin:/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

COPY Cargo.toml Cargo.lock ./
COPY pkg ./pkg
COPY config ./config
COPY docs ./docs
COPY fixtures ./fixtures
COPY scripts ./scripts

RUN mkdir -p /app/bin /app/state \
    && chmod +x /app/scripts/*.sh

RUN cargo build --release --workspace --locked \
    && install -m 0755 target/release/nxctl /app/bin/nxctl \
    && install -m 0755 target/release/nxd /app/bin/nxd \
    && ln -sfn /app /app/environment

ENV CARGO_NET_OFFLINE=true
ENV RUST_BACKTRACE=1
ENV NX_CONFIG=/app/config/base.toml
ENV NX_DROPIN_DIR=/app/config/conf.d
ENV NX_OVERRIDES=/app/state/runtime-overrides.json
ENV NX_BACKEND=/app/state/backend.json
ENV NX_MANIFEST=/app/state/ownership-manifest.json
ENV NX_AUDIT=/app/state/audit.jsonl

RUN useradd --create-home --uid 1000 agent \
    && mkdir -p /logs/verifier /logs/agent \
    && chmod 777 /logs/verifier /logs/agent \
    && chown -R agent:agent /app /home/agent
