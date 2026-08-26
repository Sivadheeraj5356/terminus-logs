# Canonical base for a Go task is the ECR golang image. python3 is installed on
# top only to run the pytest verifier.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tmux asciinema ca-certificates git python3 python3-pip \
 && rm -rf /var/lib/apt/lists/* \
 && ln -sf /usr/bin/python3 /usr/local/bin/python \
 && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
 && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt

# pytest for the verifier, fully hash-locked
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --break-system-packages \
    --require-hashes -r /tmp/requirements.lock

ENV GOPATH="/root/go" \
    GOCACHE="/root/.cache/go-build" \
    GOMODCACHE="/root/go/pkg/mod"

WORKDIR /app

COPY go.mod ./

COPY cmd/ ./cmd/
COPY internal/ ./internal/
COPY configs/ ./configs/
COPY docs/ ./docs/
COPY testdata/ ./testdata/
COPY scripts/ ./scripts/
COPY README.md Makefile .golangci.yml ./
