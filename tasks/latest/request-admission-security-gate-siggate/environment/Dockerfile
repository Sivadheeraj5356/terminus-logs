# Canonical Go runtime (agent must rebuild /app/bin/siggate after edits).
FROM --platform=linux/amd64 public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS builder

WORKDIR /build
ENV CGO_ENABLED=0

COPY go.mod ./
COPY cmd/ ./cmd/
COPY internal/ ./internal/

RUN go build -trimpath -o /build/siggate ./cmd/siggate

FROM --platform=linux/amd64 public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app
ENV CGO_ENABLED=0
ENV PATH="/usr/local/go/bin:/opt/verifier-venv/bin:${PATH}"

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    asciinema \
    ca-certificates \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock \
 && rm /tmp/requirements.lock

COPY go.mod ./
COPY cmd/ ./cmd/
COPY internal/ ./internal/
COPY docs/ ./docs/
COPY data/ ./data/
COPY fixtures/ ./fixtures/
COPY README.md ./

COPY --from=builder /build/siggate /app/bin/siggate

RUN mkdir -p /app/bin /app/output \
 && chmod +x /app/bin/siggate
