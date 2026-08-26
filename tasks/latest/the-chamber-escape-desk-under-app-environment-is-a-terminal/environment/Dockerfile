FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        iproute2=6.1.0-3 \
        lsof=4.95.0-1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        socat=1.7.4.4-2 \
        strace=6.1-0.1 \
        tmux=3.3a-3 \
        procps=2:4.0.2-3 \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY Cargo.toml Cargo.lock /app/environment/
COPY app_k /app/environment/app_k
COPY k7m /app/environment/k7m
COPY p3r /app/environment/p3r
COPY w4n /app/environment/w4n
COPY r9m /app/environment/r9m
COPY svc /app/environment/svc
COPY vault /app/environment/vault
COPY schemas /app/environment/schemas
COPY docs /app/environment/docs
COPY config /app/environment/config
COPY scripts /app/environment/scripts
COPY README.md /app/environment/

RUN chmod +x \
        /app/environment/svc/*.sh \
        /app/environment/scripts/*.sh \
    && mkdir -p /app/bin /app/output /app/.cargo-target /app/docs \
    && ln -sf /app/environment/docs/manifest_contract.md /app/docs/manifest_contract.md \
    && ln -sf /app/environment/docs/api_notes.md /app/docs/api_notes.md \
    && ln -sf /app/environment/docs/escape_pipeline.md /app/docs/escape_pipeline.md \
    && cd /app/environment \
    && CARGO_TARGET_DIR=/app/.cargo-target cargo build --release --locked -p desk_k \
    && cp /app/.cargo-target/release/desk_k /app/bin/desk_k

WORKDIR /app
