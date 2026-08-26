FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PATH="/usr/local/cargo/bin:${PATH}"
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends python3=3.11.2-1+b1 python-is-python3=3.11.2-1+deb12u1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    curl=7.88.1-10+deb12u14 \
    patch=2.7.6-7 \
    && curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh \
    && . /root/.local/bin/env \
    && uvx -p /usr/bin/python3 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 pytest --version \
    && rm -rf /var/lib/apt/lists/*

ENV UV_CACHE_DIR=/root/.cache/uv

COPY Cargo.toml /app/environment/Cargo.toml
COPY Cargo.lock /app/environment/Cargo.lock
COPY main.rs types.rs probe.rs calib.rs weight.rs folio.rs seal.rs state.rs cache.rs pipeline.rs emit.rs workflow.rs /app/environment/
COPY probe /app/environment/probe
COPY calib /app/environment/calib
COPY weight /app/environment/weight
COPY folio /app/environment/folio
COPY seal /app/environment/seal
COPY state /app/environment/state
COPY cache /app/environment/cache
COPY workflow /app/environment/workflow
COPY pipeline /app/environment/pipeline
COPY emit /app/environment/emit
COPY cmd /app/environment/cmd
COPY docs /app/environment/docs
COPY fixtures /app/environment/fixtures
COPY scripts /app/environment/scripts
COPY README.md /app/environment/README.md

RUN chmod +x /app/environment/scripts/build.sh \
    && mkdir -p /app/output /app/environment/bin \
    && cd /app/environment && cargo fetch --locked \
    && cd /app/environment && cargo build --locked \
    && install -m 0755 target/debug/piezo-audit /app/environment/bin/piezo-audit

ENV PATH="/app/environment/bin:/app/environment/scripts:${PATH}"
