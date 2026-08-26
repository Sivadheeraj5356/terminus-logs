FROM golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV PATH="/usr/local/go/bin:${PATH}"
ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends python3=3.11.2-1+b1 python3-venv=3.11.2-1+b1 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    ncurses-term=6.4-4 \
    patch=2.7.6-7 \
    tmux=3.3a-3 \
    && mkdir -p /var/tmp/tmux /app/bin /app/output /app/state \
    && chmod 1777 /var/tmp/tmux \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

COPY runtime/tmux.conf /etc/tmux.conf
COPY go.mod go.sum /app/environment/
COPY internal /app/environment/internal
COPY k3 /app/environment/k3
COPY f2 /app/environment/f2
COPY j8 /app/environment/j8
COPY r6 /app/environment/r6
COPY m7 /app/environment/m7
COPY p4 /app/environment/p4
COPY s2 /app/environment/s2
COPY q9 /app/environment/q9
COPY cmd /app/environment/cmd
COPY docs /app/environment/docs
COPY fixtures /app/environment/fixtures
COPY decoys_k3 /app/environment/decoys_k3
COPY decoys_f2 /app/environment/decoys_f2
COPY decoys_j8 /app/environment/decoys_j8
COPY tools /app/environment/tools
COPY ci /app/ci

WORKDIR /app/environment
RUN go build -o /app/bin/pull_gate ./q9/pull_gate \
    && go build -o /app/bin/sync_probe ./cmd/probe_stage \
    && go build -o /app/bin/meta_walk ./cmd/meta_walk \
    && go build -o /app/bin/collect_stage ./cmd/collect_stage \
    && chmod +x /app/ci/rebuild.sh

WORKDIR /app
