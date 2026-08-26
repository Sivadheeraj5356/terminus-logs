FROM golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV GOPROXY=off
ENV GOCACHE=/tmp/go-cache

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    coreutils=9.1-1 \
    ncurses-term=6.4-4 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    && mkdir -p /var/tmp/tmux /tmp/go-cache \
    && chmod 1777 /var/tmp/tmux /tmp/go-cache \
    && rm -rf /var/lib/apt/lists/*

COPY runtime/tmux.conf /etc/tmux.conf
COPY go.mod /app/environment/
COPY types /app/environment/types
COPY cmd /app/environment/cmd
COPY internal /app/environment/internal
COPY k5 /app/environment/k5
COPY j2 /app/environment/j2
COPY n8 /app/environment/n8
COPY v3 /app/environment/v3
COPY m4 /app/environment/m4
COPY py /app/environment/py
COPY config /app/environment/config
COPY data /app/environment/data
COPY docs /app/environment/docs
COPY scripts /app/environment/scripts
COPY requirements.txt /tmp/requirements.txt

WORKDIR /app/environment

RUN go build -trimpath -o /app/bin/ctl_s8 ./cmd/ctl_s8 \
    && go build -trimpath -o /app/bin/client_t4 ./cmd/client_t4 \
    && go build -trimpath -o /app/bin/supervisord ./cmd/supervisord \
    && rm -rf /root/.cache/go-build /tmp/go-cache/*

WORKDIR /app

RUN mkdir -p /app/bin /app/output \
    && chmod +x /app/environment/scripts/build_all.sh /app/environment/scripts/bootstrap_local.sh \
    && bash /app/environment/scripts/bootstrap_local.sh

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt

ENV PATH="/usr/local/go/bin:/app/bin:/opt/verifier-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
