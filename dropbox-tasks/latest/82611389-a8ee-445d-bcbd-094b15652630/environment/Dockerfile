FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        curl \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

ENV PATH="/usr/local/go/bin:/opt/verifier-venv/bin:${PATH}"
ENV GOMODCACHE=/go/pkg/mod
ENV CGO_ENABLED=0
ENV GOPROXY=off
ENV GOSUMDB=off

WORKDIR /app

COPY go.mod ./

COPY cmd/ ./cmd/
COPY internal/ ./internal/
COPY packages/ ./packages/
COPY config/ ./config/
COPY data/ ./data/
COPY docs/ ./docs/
COPY fixtures/ ./fixtures/
COPY scripts/ ./scripts/
COPY lab/ ./lab/
COPY Makefile README.md ./

RUN chmod +x /app/scripts/start-fleetd.sh /app/scripts/emit-fleet-build-audit.sh \
    && mkdir -p /app/output /app/data /app/var/fleet-stage /app/bin \
    && go build -o /app/bin/fleetd ./cmd/fleetd
