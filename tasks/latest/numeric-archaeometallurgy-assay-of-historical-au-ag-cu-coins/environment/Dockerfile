FROM --platform=linux/amd64 public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV CARGO_INCREMENTAL=0
ENV PATH="/usr/local/cargo/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        bash \
        build-essential \
        ca-certificates \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==9.0.3 \
        pytest-json-ctrf==0.5.0

RUN ln -sf /usr/local/cargo/bin/cargo /usr/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/bin/rustc

WORKDIR /app

COPY Cargo.toml Cargo.lock /app/
COPY src/ /app/src/
RUN cargo fetch --locked

COPY docs/ /app/docs/
COPY data/ /app/data/
COPY scripts/ /app/scripts/
RUN chmod +x /app/scripts/rebuild-assay-ledger.sh \
    && mkdir -p /app/state /app/output /app/bin \
    && cargo build --release --locked \
    && install -m 0755 /app/target/release/assay-ledger /app/bin/assay-ledger
