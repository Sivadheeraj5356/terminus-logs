FROM --platform=linux/amd64 public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

# Agent must rebuild after edits; keep Rust toolchain in the runtime image (carve-out).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    asciinema \
    bash \
    build-essential \
    ca-certificates \
    python3 \
    python3-venv \
    tmux \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir \
    pytest==9.0.3 \
    pytest-json-ctrf==0.5.0

RUN ln -s /usr/local/cargo/bin/rustc /usr/bin/rustc || true \
 && ln -s /usr/local/cargo/bin/cargo /usr/bin/cargo || true

RUN mkdir -p /opt/verifier-scripts
COPY scripts/verifier-rebuild.sh /opt/verifier-scripts/rebuild-tool
RUN sed -i 's/\r$//' /opt/verifier-scripts/rebuild-tool \
 && chmod +x /opt/verifier-scripts/rebuild-tool

ENV PATH="/opt/verifier-venv/bin:/opt/verifier-scripts:/usr/local/cargo/bin:/usr/bin:${PATH}"
ENV CARGO_HOME=/usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_INCREMENTAL=0
WORKDIR /app

COPY Cargo.toml Cargo.lock /app/
RUN cargo fetch --locked

COPY docs/ /app/docs/
COPY data/ /app/data/
COPY cmd/ /app/cmd/
COPY src/ /app/src/

RUN cargo build --release --locked \
 && mkdir -p /app/bin /app/output /app/state \
 && cp target/release/haar-denoiser /app/bin/haar-denoiser \
 && chmod +x /app/bin/haar-denoiser \
 && chmod -R a+rwX /app/bin /app/output /app/state /app/target /app/src \
      /usr/local/cargo/registry /usr/local/cargo/git 2>/dev/null || true \
 && chmod -R a+rwX /usr/local/cargo 2>/dev/null || true
