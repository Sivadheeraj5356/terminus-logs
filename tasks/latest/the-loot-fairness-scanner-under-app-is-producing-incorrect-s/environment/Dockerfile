FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

LABEL org.opencontainers.image.title="loot-distribution-fairness-validator" \
    org.opencontainers.image.description="Harbor Terminal-Bench task for repairing a Go loot fairness scanner" \
    org.opencontainers.image.vendor="snorkel" \
    org.opencontainers.image.version="1.0.0"

ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local \
    GO111MODULE=on \
    CGO_ENABLED=0 \
    PATH="/usr/local/go/bin:/opt/verifier-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    GOCACHE=/app/out/.gocache \
    GOTMPDIR=/app/out/.gotmp \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.lock /tmp/requirements.lock

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        make=4.3-4.1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        python3-venv=3.11.2-1+b1 \
        tmux=3.3a-3 \
    && python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm -rf /var/lib/apt/lists/* /root/.cache /tmp/requirements.lock \
    && /opt/verifier-venv/bin/python -c "import pytest"

WORKDIR /app

COPY go.mod Makefile /app/
COPY dropvault/ /app/dropvault/
COPY rollbench/ /app/rollbench/
COPY faircore/ /app/faircore/

RUN mkdir -p /app/out /app/out/.gocache /app/out/.gotmp \
    && find /app/dropvault -type f -exec chmod a-w {} + \
    && chmod a-w /app/go.mod /app/Makefile \
    && chmod -R a+rwX /app/faircore /app/out
