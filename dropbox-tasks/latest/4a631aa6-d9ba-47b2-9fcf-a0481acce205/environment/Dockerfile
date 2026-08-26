FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC
ENV PATH=/usr/local/go/bin:/go/bin:${PATH}
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv ca-certificates tmux asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY go.mod /app/
COPY cmd/ /app/cmd/
COPY internal/ /app/internal/
COPY docs/ /app/docs/
COPY config/ /app/config/
COPY data/ /app/data/

RUN mkdir -p /app/output

ENV GOFLAGS=-mod=mod
ENV GOPROXY=off
ENV GOTOOLCHAIN=local
