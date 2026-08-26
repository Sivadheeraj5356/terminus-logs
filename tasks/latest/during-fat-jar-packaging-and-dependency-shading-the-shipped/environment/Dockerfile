# Package relocation consistency validator runtime.
# Agent must rebuild /app/bin/reloccheck after reloclogic edits, so the
# Go toolchain and make remain in the final stage by design (not a prebuilt artifact task).
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

LABEL org.opencontainers.image.title="package-relocation-consistency-validator"
LABEL org.opencontainers.image.description="Build and dependency packaging validator for Maven-shade style jar relocation consistency"
LABEL org.opencontainers.image.licenses="MIT"

ENV DEBIAN_FRONTEND=noninteractive
ENV GOTOOLCHAIN=local
ENV GO111MODULE=on
ENV CGO_ENABLED=0
ENV PATH=/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV SOURCE_DATE_EPOCH=0

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates=20230311+deb12u1 \
        make=4.3-4.1 \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        python3 \
        python3-pip \
 && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
 && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && command -v tmux >/dev/null \
 && command -v asciinema >/dev/null

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --break-system-packages \
        --require-hashes --no-deps -r /tmp/requirements.lock

WORKDIR /app

COPY go.mod /app/
COPY Makefile RELOCATION_SPEC.md REPORT_LAYOUT.md /app/
COPY relocbin /app/relocbin
COPY reloclogic /app/reloclogic
COPY reloc-canon /app/reloc-canon
COPY reloc-batches /app/reloc-batches

RUN mkdir -p /app/bin /app/artifacts
