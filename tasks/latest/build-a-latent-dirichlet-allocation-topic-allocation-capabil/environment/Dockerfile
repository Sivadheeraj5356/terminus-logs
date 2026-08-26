FROM --platform=linux/amd64 public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

LABEL org.opencontainers.image.licenses="MIT"

COPY requirements.lock /tmp/requirements.lock
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock \
 && rm -f /tmp/requirements.lock

ENV PATH="/usr/local/cargo/bin:/opt/verifier-venv/bin:/usr/local/bin:${PATH}"
ENV CARGO_INCREMENTAL=0

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY crates/ /app/crates/
COPY docs/ /app/docs/
COPY config/ /app/config/
COPY fixtures/ /app/fixtures/
COPY scripts/ /app/scripts/
COPY README.md /app/README.md

RUN chmod +x /app/scripts/*.sh \
 && cargo vendor \
 && mkdir -p .cargo \
 && printf '[source.crates-io]\nreplace-with = "vendored-sources"\n\n[source.vendored-sources]\ndirectory = "vendor"\n' > .cargo/config.toml \
 && cargo build --offline --release --locked -p ldactl \
 && install -m 0755 target/release/ldactl /usr/local/bin/ldactl \
 && mkdir -p /app/state /app/output /opt/lda-scaffold \
 && cp -a /app/crates /app/Cargo.toml /app/Cargo.lock /opt/lda-scaffold/

ENV CARGO_NET_OFFLINE=true
WORKDIR /app
