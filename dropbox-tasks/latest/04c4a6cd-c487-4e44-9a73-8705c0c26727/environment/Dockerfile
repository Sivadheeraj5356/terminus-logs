FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        pkg-config \
        python3 \
        python3-pip \
        sqlite3 \
        tmux \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app
COPY app/Cargo.toml /app/Cargo.toml
COPY app/Cargo.lock /app/Cargo.lock
COPY app/src/ /app/src/
RUN cargo fetch --locked
COPY app/docs/ /app/docs/
COPY app/data/ /app/data/
