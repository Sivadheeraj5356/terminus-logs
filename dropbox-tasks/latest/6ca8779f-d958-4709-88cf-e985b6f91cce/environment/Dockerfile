FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS builder

WORKDIR /build/skirmish

COPY skirmish/Cargo.toml skirmish/Cargo.lock ./
COPY skirmish/src ./src

RUN cargo build --release --locked

# The final stage intentionally retains the canonical Rust toolchain because the
# task and verifier rebuild modified sources before every adjudication.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --break-system-packages --no-cache-dir --require-hashes --no-deps \
        -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

ENV CARGO_NET_OFFLINE=true \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN mkdir -p /app/bin /app/environment/skirmish

COPY --from=builder /usr/local/cargo/registry /usr/local/cargo/registry
COPY --from=builder /build/skirmish/target /app/environment/skirmish/target
COPY entrypoint/skirmish /app/bin/skirmish
COPY skirmish/Cargo.toml skirmish/Cargo.lock /app/environment/skirmish/
COPY skirmish/src /app/environment/skirmish/src
COPY docs /app/environment/docs
COPY data /app/environment/data
COPY fixtures /app/environment/fixtures
COPY tools /app/environment/tools
COPY scripts /app/environment/scripts
COPY architecture.md /app/environment/architecture.md
COPY README.md /app/environment/README.md

RUN chmod +x /app/bin/skirmish

WORKDIR /app
