FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      asciinema \
      ca-certificates \
      tmux \
      lua5.4 \
      liblua5.4-dev \
      gcc \
      curl \
      wget \
      unzip \
      make \
      python3-venv \
 && rm -rf /var/lib/apt/lists/*

# Install DuckDB
ARG DUCKDB_SHA256=41b4110fbdee527b27e765b225097ca235dd154af96612445072edc0e748392e
RUN curl -L https://github.com/duckdb/duckdb/releases/download/v1.0.0/duckdb_cli-linux-amd64.zip -o duckdb.zip \
 && echo "${DUCKDB_SHA256}  duckdb.zip" | sha256sum -c - \
 && unzip duckdb.zip -d /usr/local/bin \
 && rm duckdb.zip \
 && chmod +x /usr/local/bin/duckdb

# Test-only deps isolated in a venv (the test runner), kept out of the app/system Python.
COPY verifier-requirements.lock /tmp/verifier-requirements.lock
RUN python3 -m venv --system-site-packages /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --require-hashes --no-deps --no-cache-dir \
      -r /tmp/verifier-requirements.lock

WORKDIR /app
COPY Makefile main.lua trace_ext.c verify.sql mock_server.py iris.csv /app/
COPY docs/ /app/docs/
