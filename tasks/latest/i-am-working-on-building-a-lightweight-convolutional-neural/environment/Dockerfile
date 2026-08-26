FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS golang-base

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    asciinema \
    gcc \
    libc-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy Go from the canonical Go image
COPY --from=golang-base /usr/local/go /usr/local/go
RUN ln -s /usr/local/go/bin/go /usr/local/bin/go

# Install test dependencies
COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements.lock

COPY app/ /app/

# Normalize line endings to avoid CRLF windows issues on scripts/code
RUN find /app -type f -exec sed -i 's/\r$//' {} +
