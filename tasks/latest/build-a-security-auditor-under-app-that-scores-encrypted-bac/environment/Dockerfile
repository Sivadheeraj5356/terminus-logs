# Agent must rebuild /app/bin/ebta after implementing vault and audit packages; Go toolchain stays in the final image.

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV GOTOOLCHAIN=local
ENV GO111MODULE=on
ENV CGO_ENABLED=0

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        make \
        python3 \
        python3-pip \
        tmux \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN ln -sf /usr/bin/python3 /usr/bin/python \
 && python3 -m pip install --no-cache-dir --break-system-packages \
        --require-hashes --no-deps \
        -r /tmp/requirements.lock \
 && rm -f /tmp/requirements.lock

WORKDIR /app

COPY go.mod go.sum /app/
RUN go mod download

COPY Makefile /app/
COPY contracts /app/contracts
COPY rules /app/rules
COPY schema /app/schema
COPY orchestrate /app/orchestrate
COPY emit /app/emit
COPY bootstrap /app/bootstrap
COPY vault /app/vault
COPY audit /app/audit
COPY archives /app/archives

RUN mkdir -p /app/bin /app/verdicts
