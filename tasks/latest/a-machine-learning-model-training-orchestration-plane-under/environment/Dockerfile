FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV PATH="/usr/local/go/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        bash \
        ca-certificates \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY cmd ./cmd
COPY internal ./internal
COPY scripts ./scripts
COPY configs ./configs
COPY docs ./docs
COPY testdata ./testdata
COPY Makefile ./Makefile
COPY README.md ./README.md

RUN mkdir -p /app/state/checkpoints /app/output /app/cache \
    && chmod +x /app/scripts/*.sh \
    && go build -o /usr/local/bin/runtime ./cmd/runtime \
    && cp /usr/local/bin/runtime /tmp/runtime

ENV RUNTIME_ROOT=/app
ENV RUNTIME_BIN=/tmp/runtime
ENV PATH="/usr/local/go/bin:/usr/local/bin:/tmp:${PATH}"
