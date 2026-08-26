FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rust-tools

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       tmux \
       asciinema \
       python3 \
       python3-pip \
       build-essential \
       pkg-config \
       ca-certificates \
       libssl3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --no-cache-dir --break-system-packages \
       --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

COPY --from=rust-tools /usr/local/cargo /usr/local/cargo
COPY --from=rust-tools /usr/local/rustup /usr/local/rustup

ENV PATH=/app/bin:/usr/local/cargo/bin:${PATH}
ENV CARGO_NET_OFFLINE=true
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo

COPY src/Cargo.toml src/Cargo.lock /app/
COPY src/.cargo/ /app/.cargo/
COPY vendor.tar.gz /tmp/vendor.tar.gz
COPY src/src/ /app/src/
COPY src/spec/ /app/spec/

RUN mkdir -p /app/bin \
    && cd /app \
    && tar -xzf /tmp/vendor.tar.gz -C /app \
    && rm /tmp/vendor.tar.gz \
    && cargo build --release --bin scenetest \
    && install -m 0755 /app/target/release/scenetest /app/bin/scenetest
