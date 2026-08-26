FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3=3.11.2-1+b1 python3-venv=3.11.2-1+b1 make=4.3-4.1 gcc=4:12.2.0-3 libc6-dev=2.36-9+deb12u13 ca-certificates=20230311+deb12u1 tmux=3.3a-3 asciinema=2.2.0-1 strace=6.1-0.1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --require-hashes --no-deps -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

COPY app/ /app/

ENV PATH="/opt/venv/bin:/usr/local/go/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    TZ=UTC \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    CGO_ENABLED=0 \
    GOTOOLCHAIN=local \
    GOFLAGS=-mod=readonly \
    GOPROXY=off \
    GOSUMDB=off \
    GOCACHE=/tmp/go-build-cache \
    GOPATH=/tmp/go \
    PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p /tmp/go-build-cache /tmp/go \
    && chmod 1777 /tmp/go-build-cache /tmp/go \
    && command -v go \
    && go version \
    && go env GOTOOLCHAIN GOFLAGS GOPROXY GOSUMDB \
    && make clean install
