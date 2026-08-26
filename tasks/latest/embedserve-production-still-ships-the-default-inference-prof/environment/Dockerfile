# syntax=docker/dockerfile:1

FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive

ENV PATH="/root/.local/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates=20230311+deb12u1 \
        python3=3.11.2-1+b1 \
        sqlite3=3.40.1-2+deb12u2 \
        php8.2-cli=8.2.32-1~deb12u1 \
        php8.2-sqlite3=8.2.32-1~deb12u1 \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/php8.2 /usr/bin/php

COPY vendor/uv-x86_64-unknown-linux-gnu-0.9.5.tar.gz vendor/cargo-audit-x86_64-unknown-linux-gnu-v0.21.0.tgz /tmp/

RUN echo "2cf10babba653310606f8b49876cfb679928669e7ddaa1fb41fb00ce73e64f66  /tmp/uv-x86_64-unknown-linux-gnu-0.9.5.tar.gz" | sha256sum -c - \
    && echo "843cadb5350064451c23847881cfa510d18da21506554e822e4a647082b362b0  /tmp/cargo-audit-x86_64-unknown-linux-gnu-v0.21.0.tgz" | sha256sum -c - \
    && mkdir -p /root/.local/bin \
    && tar -xzf /tmp/uv-x86_64-unknown-linux-gnu-0.9.5.tar.gz -C /tmp \
    && mv /tmp/uv-x86_64-unknown-linux-gnu/uv /tmp/uv-x86_64-unknown-linux-gnu/uvx /root/.local/bin/ \
    && tar -xzf /tmp/cargo-audit-x86_64-unknown-linux-gnu-v0.21.0.tgz -C /usr/local/cargo/bin --strip-components=1 \
    && rm -rf /tmp/uv-x86_64-unknown-linux-gnu-0.9.5.tar.gz \
              /tmp/uv-x86_64-unknown-linux-gnu \
              /tmp/cargo-audit-x86_64-unknown-linux-gnu-v0.21.0.tgz \
    && uv --version \
    && cargo-audit --version \
    && uv python install 3.13 \
    && uvx -p 3.13 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 pytest --version

ENV UV_OFFLINE=1

WORKDIR /app

RUN mkdir -p /app/data /app/docs /app/out

COPY . /app/environment/

RUN chmod +x /app/environment/ci/*.sh /app/environment/scripts/run_harden_cli.php \
    && /app/environment/ci/strip_cvss40.sh \
    && python3 /app/environment/data/generate_ops_bundle.py \
    && python3 /app/environment/data/generate_inventory.py \
    && /app/environment/ci/path_check.sh

WORKDIR /app
