# Canonical Terminal-Bench Rust runtime base (digest-pinned).
# Single-stage is intentional: the agent and verifier must rebuild from /app at runtime.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV CARGO_HOME="/usr/local/cargo"
ENV RUSTUP_HOME="/usr/local/rustup"
ENV PATH="/usr/local/cargo/bin:/usr/local/rustup/bin:/root/.cargo/bin:/usr/local/bin:/usr/bin:/bin"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-pip \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && command -v cargo \
    && cargo --version \
    && command -v rustc \
    && rustc --version

RUN printf '%s\n' \
    'export PATH=/usr/local/cargo/bin:/usr/local/rustup/bin:/usr/local/bin:/usr/bin:/bin' \
    > /etc/profile.d/rust-path.sh

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5 \
    cryptography==44.0.2 \
    ruff==0.11.12

WORKDIR /app

COPY app/Cargo.toml app/Cargo.lock /app/
COPY app/ /app/

RUN test -f /app/.cargo/config.toml \
    && test -f /app/Cargo.toml \
    && test -f /app/Cargo.lock \
    && test -d /app/vendor

RUN python3 -c "from pathlib import Path; import sys; raw=Path('/app/.cargo/config.toml').read_bytes(); sys.exit(1 if raw.startswith(bytes([0xEF,0xBB,0xBF])) else 0)"

RUN CARGO_NET_OFFLINE=true \
    cargo metadata --locked --offline --format-version 1 --no-deps

RUN CARGO_NET_OFFLINE=true \
    cargo build --release --locked --offline \
    && rm -rf /app/target \
    && mkdir -p /logs/verifier /logs/agent /app/output

CMD ["sleep", "infinity"]
