FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        gcc \
        libc6-dev \
        libcurl4-openssl-dev \
        make \
        curl \
        unzip \
        graphviz \
    && rm -rf /var/lib/apt/lists/*

ARG TARGETARCH
RUN set -eux; \
    case "${TARGETARCH:-amd64}" in \
        amd64) DUCKDB_ARCH=linux-amd64; DUCKDB_SHA256=72c038a8a2a6647c68ed0e0df6aa47160c03f021917019ee135f07f9c4635afa ;; \
        arm64) DUCKDB_ARCH=linux-aarch64; DUCKDB_SHA256=a0a656f1d5b07ecc7aa786c16fc54c4a2f20049c36ba3ae41f0f297bccc7e7ff ;; \
        *) DUCKDB_ARCH=linux-amd64; DUCKDB_SHA256=72c038a8a2a6647c68ed0e0df6aa47160c03f021917019ee135f07f9c4635afa ;; \
    esac; \
    curl -fsSL -o /tmp/duckdb.zip "https://github.com/duckdb/duckdb/releases/download/v1.2.1/duckdb_cli-${DUCKDB_ARCH}.zip"; \
    echo "${DUCKDB_SHA256}  /tmp/duckdb.zip" | sha256sum -c -; \
    unzip -p /tmp/duckdb.zip duckdb > /usr/local/bin/duckdb; \
    chmod +x /usr/local/bin/duckdb; \
    rm /tmp/duckdb.zip

RUN python -m pip install --no-cache-dir \
    packaging==24.2 \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5 \
    duckdb==1.2.1 \
    flask==3.1.0

COPY data /app/data
COPY scripts /app/scripts
COPY registry /app/registry
COPY src /app/src

RUN bash /app/scripts/import_fixtures.sh \
    && make -C /app/src all

WORKDIR /app
