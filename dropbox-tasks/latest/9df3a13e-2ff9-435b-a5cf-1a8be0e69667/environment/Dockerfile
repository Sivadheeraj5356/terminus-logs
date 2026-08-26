FROM --platform=linux/amd64 public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    asciinema \
    ca-certificates \
    patch \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
 && rm -rf /var/lib/apt/lists/*

COPY requirements-verifier.txt /tmp/requirements-verifier.txt
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements-verifier.txt

COPY scripts/verifier-rebuild.sh /opt/verifier-scripts/rebuild-waxlane-allot
RUN chmod +x /opt/verifier-scripts/rebuild-waxlane-allot

ENV PATH="/usr/local/go/bin:/usr/local/bin:/opt/verifier-venv/bin:/opt/verifier-scripts:${PATH}"
ENV CGO_ENABLED=0

WORKDIR /app

COPY go.mod ./
COPY cmd/ cmd/
COPY pkg/ pkg/
COPY docs/ docs/
COPY data/ data/
COPY config/ config/
COPY state/ state/
COPY scripts/ scripts/
COPY README.md ./

RUN go build -mod=readonly -o /app/bin/waxlane-allot ./cmd/waxlane-allot \
 && mkdir -p /app/output /app/bin /app/state
