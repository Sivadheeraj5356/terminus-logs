# Multi-stage: pinned golang image supplies the toolchain only (COPY source).
# Final runtime base is canonical Python 3.13 slim bookworm; Go is layered on top
# because it is not on the canonical runtime list.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS go-toolchain

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

COPY --from=go-toolchain /usr/local/go /usr/local/go

ENV GOPATH=/go \
    GOCACHE=/tmp/gocache \
    GO111MODULE=on \
    GOFLAGS=-mod=mod \
    GOPROXY=off \
    GOTOOLCHAIN=local \
    CGO_ENABLED=0 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/verifier-venv/bin:/usr/local/go/bin:/usr/local/bin:${PATH}"

COPY verifier-requirements.pins /tmp/requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends asciinema=2.2.0-1 bash=5.2.15-2+b13 make=4.3-4.1 patch=2.7.6-7 tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv
RUN /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt
RUN rm -f /tmp/requirements.txt \
    && printf '%s\n' '#!/bin/sh' 'exec /opt/verifier-venv/bin/python -m pytest "$@"' > /usr/local/bin/pytest \
    && chmod +x /usr/local/bin/pytest \
    && ln -sf /usr/local/go/bin/go /usr/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/bin/gofmt \
    && mkdir -p /app/bin /app/out /tmp/gocache /go \
    && chmod 0777 /tmp/gocache /go /app/bin /app/out

WORKDIR /app/environment

COPY . /app/environment
RUN mkdir -p /app/environment/var/fitstore /app/environment/var/run \
    && chmod 0777 /app/environment/var /app/environment/var/fitstore /app/environment/var/run
RUN go build -trimpath -o /app/bin/plangen ./cmd/plangen
