FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      build-essential \
      python3 \
      python3-venv \
      tmux \
      asciinema \
 && rm -rf /var/lib/apt/lists/*

ENV CARGO_NET_OFFLINE=true

ENV PATH=/usr/local/cargo/bin:${PATH}
RUN ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
 && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

WORKDIR /app/environment

COPY Cargo.toml /app/environment/Cargo.toml
COPY Cargo.lock /app/environment/Cargo.lock
COPY src /app/environment/src
COPY docs /app/environment/docs
COPY data /app/environment/data

WORKDIR /app/environment
