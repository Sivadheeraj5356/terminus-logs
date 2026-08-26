# force-rebuild 2026-07-16-v52-cache-bust
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3=3.40.* \
    python3-pip \
    tmux=3.* \
    asciinema=2.* \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --break-system-packages --require-hashes --no-deps -r /tmp/requirements.lock

WORKDIR /app

COPY go.mod go.sum ./

RUN GOPROXY=https://proxy.golang.org,direct go mod download

COPY source/ /app/

ENV GOPROXY=off

COPY docs/ /docs/
COPY data/ /data/
