FROM docker.io/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb
ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV PYTHONPATH=/app/environment
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 ncurses-term=6.4-4 tmux=3.3a-3 patch=2.7.6-7 \
    && mkdir -p /var/tmp/tmux && chmod 1777 /var/tmp/tmux \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5
ENV PATH="/opt/verifier-venv/bin:${PATH}"
RUN ln -sf /opt/verifier-venv/bin/pytest /usr/local/bin/pytest
RUN mkdir -p /app/output /app/data/wasm /app/environment
COPY structlib /app/environment/structlib
COPY lib /app/environment/lib
COPY driver /app/environment/driver
COPY docs /app/environment/docs
COPY cfg /app/environment/cfg
COPY ops /app/environment/ops
COPY fixtures /app/environment/fixtures
COPY runtime/tmux.conf /etc/tmux.conf
COPY README.md /app/environment/README.md
COPY metadata.json /app/environment/metadata.json
