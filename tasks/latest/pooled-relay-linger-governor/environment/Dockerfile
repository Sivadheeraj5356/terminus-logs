# Justification: rust:1.85-slim is the canonical Terminal-Bench builder image for Rust
# 1.85 compilation; this stage compiles the locked Cargo workspace offline. The final
# runtime image stays on the canonical Debian bookworm-slim base.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rust-builder

WORKDIR /build
COPY . .
RUN cargo build --release --locked

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.9 \
    gcc=4:12.2.0-3 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    sqlite3=3.40.1-2+deb12u2 \
    ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5
ENV PATH=/opt/verifier/bin:/app/bin:$PATH

COPY --from=rust-builder /build/target /app/environment/target
COPY --from=rust-builder /build/target/release/relayctl /app/bin/relayctl
COPY --from=rust-builder /build/target/release/relayctl /app/bin/relayctl-nop
COPY --from=rust-builder /usr/local/cargo /usr/local/cargo
COPY --from=rust-builder /usr/local/rustup /usr/local/rustup
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV PATH="/usr/local/cargo/bin:${PATH}"
RUN rustup default stable

COPY . /app/environment
RUN mkdir -p /output /var/data \
    && rm -rf /app/config /app/docs /app/fixtures \
    && ln -sfn /app/environment/config /app/config \
    && ln -sfn /app/environment/docs /app/docs \
    && ln -sfn /app/environment/fixtures /app/fixtures
