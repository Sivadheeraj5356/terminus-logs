FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock

RUN python -m pip install --require-hashes --no-deps --no-cache-dir -r /tmp/requirements.lock

WORKDIR /app

COPY app/ /app/xwing-data/

RUN useradd --create-home --uid 1000 --shell /bin/bash analyst \
    && mkdir -p /app/out \
    && chown analyst:analyst /app/out \
    && chmod -R a-w /app/xwing-data

# Harbor bootstraps mounted directories as root before starting the configured
# non-root agent and verifier users from task.toml.
WORKDIR /app/xwing-data
