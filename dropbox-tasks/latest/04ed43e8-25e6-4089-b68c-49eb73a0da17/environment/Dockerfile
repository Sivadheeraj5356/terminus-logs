# Canonical digest-pinned Ubuntu 24.04 runtime base (platform ECR public mirror).
FROM public.ecr.aws/docker/library/ubuntu:24.04@sha256:0d39fcc8335d6d74d5502f6df2d30119ff4790ebbb60b364818d5112d9e3e932

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV GOMAXPROCS=1
ENV CGO_ENABLED=0

RUN apt-get update && apt-get install -y --no-install-recommends golang-go=2:1.22~2build1 \
    ca-certificates=20240203 \
    python3=3.12.3-0ubuntu2.1 \
    python3-venv=3.12.3-0ubuntu2.1 \
    tmux=3.4-1ubuntu0.1 \
    asciinema=2.4.0-1 \
    ncurses-term=6.4+20240113-1ubuntu2 \
    bash=5.2.21-2ubuntu4 \
 && mkdir -p /var/tmp/tmux \
 && chmod 1777 /var/tmp/tmux \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY runtime/tmux.conf /etc/tmux.conf
COPY . /app/environment

WORKDIR /app/environment

RUN go build -o /app/bin/state-audit ./driver/ \
 && chmod +x scripts/*.sh \
 && mkdir -p /app/data/workspace /app/output

WORKDIR /app
