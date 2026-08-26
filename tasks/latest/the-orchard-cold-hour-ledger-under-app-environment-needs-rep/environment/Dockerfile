FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends tmux=3.3a-3 asciinema=2.2.0-1 ca-certificates=20230311+deb12u1 python3=3.11.2-1+b1 python3-pytest=7.2.1-2 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/output /app/environment/.build

ENV PATH="/app/environment/.build:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

COPY go.mod /app/environment/go.mod
COPY cmd /app/environment/cmd
COPY config /app/environment/config
COPY parse /app/environment/parse
COPY accum /app/environment/accum
COPY emit /app/environment/emit
COPY manifest /app/environment/manifest
COPY registry /app/environment/registry
COPY corrections /app/environment/corrections
COPY state /app/environment/state
COPY util /app/environment/util
COPY audit /app/environment/audit
COPY replay /app/environment/replay
COPY docs /app/environment/docs
COPY fixtures /app/environment/fixtures

RUN ln -sf /app/environment/fixtures /app/fixtures \
    && mkdir -p /app/environment/.build
