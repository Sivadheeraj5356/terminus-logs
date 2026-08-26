# Go build environment plus verifier Python stack for tests/test.sh.

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV GOTOOLCHAIN=local
ENV GO111MODULE=on
ENV CGO_ENABLED=0

COPY requirements.txt /tmp/requirements.txt

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        make=4.3-4.1 \
        python3 \
        python3-pip \
        tmux=3.3a-3 \
 && pip3 install --no-cache-dir --break-system-packages \
        -r /tmp/requirements.txt \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY go.mod go.sum /app/
RUN go mod download

COPY Makefile /app/
COPY spec /app/spec
COPY replay /app/replay
COPY engine /app/engine
COPY rules /app/rules
COPY scenarios /app/scenarios

RUN mkdir -p /app/bin /app/results
