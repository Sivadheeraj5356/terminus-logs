# Canonical digest-pinned Go runtime image.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3 \
        python3-pip \
        sqlite3 \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --break-system-packages --no-cache-dir --require-hashes --no-deps \
        -r /tmp/requirements.lock

COPY app/go.mod /app/go.mod
COPY app/cmd/ /app/cmd/
COPY app/internal/ /app/internal/
COPY app/seeds/ /app/seeds/
COPY app/schema-notes.md /app/schema-notes.md

RUN mkdir -p /app/bin

ENV PATH="/app/bin:${PATH}"
