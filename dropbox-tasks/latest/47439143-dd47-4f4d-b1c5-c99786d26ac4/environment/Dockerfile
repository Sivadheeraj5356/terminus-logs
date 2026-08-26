FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rusttoolchain

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      patch ca-certificates build-essential jq tmux asciinema \
 && rm -rf /var/lib/apt/lists/*

COPY --from=rusttoolchain /usr/local/cargo /usr/local/cargo
COPY --from=rusttoolchain /usr/local/rustup /usr/local/rustup
RUN ln -s /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
 && ln -s /usr/local/cargo/bin/rustc /usr/local/bin/rustc
ENV CARGO_HOME=/usr/local/cargo RUSTUP_HOME=/usr/local/rustup \
    PATH=/usr/local/cargo/bin:$PATH

COPY requirements.txt /tmp/requirements.txt
COPY wheels /tmp/wheels
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --no-index --find-links=/tmp/wheels --require-hashes -r /tmp/requirements.txt

# Unprivileged user for running submitted code during verification.
RUN useradd --no-create-home --shell /usr/sbin/nologin sandbox

WORKDIR /app/environment

COPY . /app/environment/

WORKDIR /app/environment
