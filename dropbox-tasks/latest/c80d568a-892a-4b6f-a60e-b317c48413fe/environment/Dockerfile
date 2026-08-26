FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS builder

WORKDIR /app/src
COPY src/ /app/src/
RUN cargo build --release --offline --locked

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        gcc \
        libc6-dev \
        python3 \
        python3-pip \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip install --break-system-packages --no-cache-dir \
        --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

COPY --from=builder /usr/local/cargo /usr/local/cargo
COPY --from=builder /usr/local/rustup /usr/local/rustup

ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV PATH="/usr/local/cargo/bin:/usr/local/bin:${PATH}"

RUN ln -s /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -s /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && cargo --version && rustc --version

COPY src/ /app/src/
COPY config/zeckendorf_policy.json /app/config/zeckendorf_policy.json
COPY --from=builder /app/src/target /app/src/target

RUN mkdir -p /app/output /app/bin

LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.licenses="proprietary"
LABEL org.opencontainers.image.title="zeckendorf-encode"

CMD ["bash"]
