FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

COPY requirements.lock /tmp/requirements.lock

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux asciinema git ca-certificates python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.lock

WORKDIR /app
# Copy go.mod and go.sum first for layer caching
COPY go.mod go.sum ./
RUN go mod download
# Copy source code
COPY cmd/ ./cmd/
COPY internal/ ./internal/
COPY data/ ./data/
COPY docs/ ./docs/
COPY scripts/ ./scripts/
RUN mkdir -p /app/out
