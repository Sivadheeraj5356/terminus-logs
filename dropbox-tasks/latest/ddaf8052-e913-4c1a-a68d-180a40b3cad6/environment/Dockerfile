FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

COPY wheels/ /tmp/wheels/
COPY requirements.lock /tmp/requirements.lock

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3 \
        python3-pip \
        tmux \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir --break-system-packages \
        --no-index \
        --find-links=/tmp/wheels \
        --require-hashes -r /tmp/requirements.lock \
    && rm -rf /tmp/wheels /tmp/requirements.lock

WORKDIR /app

COPY app/Cargo.toml app/Cargo.lock /app/
COPY app/src/ /app/src/
COPY app/docs/ /app/docs/

RUN cargo build --locked \
    && cargo test --locked
