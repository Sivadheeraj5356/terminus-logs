FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS builder

WORKDIR /app
ENV GOMODCACHE=/opt/gomodcache

COPY . /app/environment

RUN mkdir -p /app/bin /app/output /opt/gomodcache /app/environment/var/work \
    && cd /app/environment && go mod tidy && go mod download \
    && make all

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    patch=2.7.6-7 \
    make=4.3-4.1 \
    ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5 \
    jsonschema==4.23.0

WORKDIR /app

ENV GOMODCACHE=/opt/gomodcache
ENV PATH=/opt/verifier/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

COPY --from=builder /usr/local/go /usr/local/go
COPY --from=builder /opt/gomodcache /opt/gomodcache
COPY --from=builder /app/environment /app/environment

RUN mkdir -p /app/environment/var/work /app/output
