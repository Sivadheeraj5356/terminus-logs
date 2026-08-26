FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV PATH="/usr/local/cargo/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        build-essential=12.9 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

RUN ln -sf /usr/bin/python3 /usr/bin/python

WORKDIR /app

COPY Cargo.toml Cargo.lock ./
COPY src ./src
COPY manifest ./manifest
COPY catalog ./catalog
COPY algebra ./algebra
COPY store ./store
COPY eval ./eval
COPY replay ./replay
COPY publish ./publish
COPY rxa ./rxa
COPY rxb ./rxb
COPY rxc ./rxc
COPY rxd ./rxd

RUN cargo build --release --locked \
    && install -m 0755 target/release/lora-gate /usr/local/bin/lora-gate \
    && ln -s /usr/local/bin/lora-gate /app/lora-gate \
    && rm -rf target \
    && mkdir -p /app/output /app/state
