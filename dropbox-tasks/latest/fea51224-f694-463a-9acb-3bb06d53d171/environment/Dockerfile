FROM golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS builder

WORKDIR /build
COPY go.mod ./
COPY cmd ./cmd
COPY bind ./bind
COPY catalog ./catalog
COPY range ./range
COPY relay ./relay
COPY ledger ./ledger
COPY internal ./internal
RUN go build -o /build/volutil ./cmd/volutil \
    && go build -o /build/listctl ./cmd/listctl

# canonical per docs/CANONICAL_BASE_IMAGES.md
FROM debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV REPLAY_ROOT=/app/environment
ENV PATH=/usr/local/go/bin:/usr/bin:/bin

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    ncurses-term=6.4-4 \
    openssl=3.0.17-1~deb12u2 \
    patch=2.7.6-7 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    && mkdir -p /var/tmp/tmux /app/bin /app/output \
    && chmod 1777 /var/tmp/tmux \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/go /usr/local/go

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

COPY runtime/tmux.conf /etc/tmux.conf
COPY go.mod /app/environment/
COPY cmd /app/environment/cmd
COPY bind /app/environment/bind
COPY catalog /app/environment/catalog
COPY range /app/environment/range
COPY relay /app/environment/relay
COPY ledger /app/environment/ledger
COPY config /app/environment/config
COPY data /app/environment/data
COPY docs /app/environment/docs
COPY fixtures /app/environment/fixtures
COPY internal /app/environment/internal
COPY scripts /app/environment/scripts

COPY --from=builder /build/volutil /build/listctl /app/bin/

RUN find /app/environment -name '*.sh' -exec sed -i 's/\r$//' {} + \
    && find /app/environment -name '*.go' -exec sed -i 's/\r$//' {} + \
    && chmod +x /app/environment/scripts/*.sh /app/environment/internal/signal/probe.sh
