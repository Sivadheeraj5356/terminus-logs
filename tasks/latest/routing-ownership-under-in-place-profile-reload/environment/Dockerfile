FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOMODCACHE=/go/pkg/mod
ENV GOPATH=/go

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ncurses-term=6.4-4 \
    bash=5.2.15-2+b13 \
    ca-certificates=20230311+deb12u1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    patch=2.7.6-7 \
    && mkdir -p /var/tmp/tmux \
    && chmod 1777 /var/tmp/tmux \
    && rm -rf /var/lib/apt/lists/*

COPY runtime/tmux.conf /etc/tmux.conf

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY go.mod /app/environment/
WORKDIR /app/environment
RUN go mod download

COPY cmd /app/environment/cmd
COPY reg /app/environment/reg
COPY lse /app/environment/lse
COPY pub /app/environment/pub
COPY wal /app/environment/wal
COPY qtn /app/environment/qtn
COPY rcv /app/environment/rcv
COPY shim /app/environment/shim
COPY emit /app/environment/emit
COPY engine /app/environment/engine
COPY data/topology_w3 /app/data/topology_w3
COPY var/grant_feed.jsonl /app/var/grant_feed.jsonl
COPY scripts /app/environment/scripts
COPY docs /app/environment/docs
COPY Makefile /app/environment/Makefile
COPY README.md /app/environment/README.md
COPY runtime /app/environment/runtime

RUN go build -o /app/bin/linkctl ./cmd/linkctl \
    && chmod +x /app/environment/scripts/*.sh \
    && mkdir -p /app/bin /app/scripts /app/output /app/var/state /logs/verifier /logs/agent \
    && cp /app/environment/scripts/run_link_ops.sh /app/scripts/run_link_ops.sh \
    && chmod +x /app/scripts/run_link_ops.sh

WORKDIR /app

RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -uo pipefail' \
    'mkdir -p /app/output /app/var/state /logs/verifier /logs/agent' \
    'exec "$@"' > /entrypoint.sh \
    && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sleep", "infinity"]
