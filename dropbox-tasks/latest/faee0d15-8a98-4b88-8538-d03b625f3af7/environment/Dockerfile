FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb AS datagen

COPY tools/gen_data.py /tools/gen_data.py
RUN python3 /tools/gen_data.py

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

LABEL org.opencontainers.image.source="local/auroral-lattice-telemetry-assembler" \
      org.opencontainers.image.revision="0" \
      org.opencontainers.image.created="1970-01-01T00:00:00Z" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.licenses="MIT"

ENV DEBIAN_FRONTEND=noninteractive \
    GOPROXY=off \
    GOFLAGS=-mod=mod \
    CGO_ENABLED=0

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
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.lock

WORKDIR /app
COPY go.mod /app/go.mod
COPY cmd/ /app/cmd/
COPY docs/ /app/docs/
COPY probe/ /app/probe/
COPY --from=datagen /app/calibration/ /app/calibration/
COPY --from=datagen /app/telemetry/ /app/telemetry/
RUN chmod 0755 /app/probe/driftprobe \
    && mkdir -p /app/output \
    && go build -o /app/assembler ./cmd/fusion \
    && go clean -cache
