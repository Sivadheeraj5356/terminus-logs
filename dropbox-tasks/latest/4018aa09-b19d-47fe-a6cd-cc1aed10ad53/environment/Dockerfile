FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV TMUX_TMPDIR=/tmp/.harbor-tmux \
    TERM=xterm-256color \
    SHELL=/bin/bash

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    curl=7.88.1-10+deb12u15 \
    tmux=3.3a-3 \
    && mkdir -p /tmp/.harbor-tmux \
    && chmod 1777 /tmp/.harbor-tmux \
    && curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:${PATH}"

RUN uv python install 3.13 \
    && uvx -p 3.13 \
       -w pytest==8.4.1 \
       -w pytest-json-ctrf==0.3.5 \
       pytest --version \
    && uv tool install --python 3.13 \
       --with pytest-json-ctrf==0.3.5 \
       pytest==8.4.1 \
    && pytest --version

WORKDIR /app
COPY . /app/environment
RUN chmod +x /app/environment/run.sh
