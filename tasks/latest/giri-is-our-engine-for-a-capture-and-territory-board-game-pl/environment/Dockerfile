FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-pip \
        graphviz \
        sqlite3 \
    && pip3 install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
    && rm -rf /var/lib/apt/lists/*

ENV CARGO_NET_OFFLINE=true
WORKDIR /app

COPY Cargo.toml Cargo.lock /app/
COPY src /app/src
COPY board.spec /app/board.spec
COPY docs /app/docs
COPY games /app/games
