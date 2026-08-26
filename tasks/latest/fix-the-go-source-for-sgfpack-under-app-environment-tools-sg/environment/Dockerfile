FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS go-toolchain

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

COPY --from=go-toolchain /usr/local/go /usr/local/go

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        coreutils \
        tmux \
        asciinema \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

ENV PATH="/usr/local/go/bin:${PATH}" \
    GOPROXY=off \
    GOTOOLCHAIN=local

WORKDIR /app
COPY workspace /app/workspace
COPY tools/sgfpack /app/environment/tools/sgfpack
RUN mkdir -p /app/output /app/bin \
    && cd /app/environment/tools/sgfpack \
    && go build -o /app/bin/sgfpack . \
    && ln -sf /app/bin/sgfpack /usr/local/bin/sgfpack
