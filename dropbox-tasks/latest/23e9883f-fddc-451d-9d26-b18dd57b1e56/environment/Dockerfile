FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS go-toolchain

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

COPY --from=go-toolchain /usr/local/go /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOPATH=/go

COPY requirements.lock /tmp/requirements.lock

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir --require-hashes --no-deps \
        -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.lock

WORKDIR /app

COPY go.mod /app/go.mod
COPY cmd /app/cmd
COPY internal /app/internal
COPY docs /app/docs
COPY data /app/data
COPY scripts /app/scripts

RUN chmod +x /app/scripts/*.sh \
    && /app/scripts/build_engine.sh /app

WORKDIR /app
