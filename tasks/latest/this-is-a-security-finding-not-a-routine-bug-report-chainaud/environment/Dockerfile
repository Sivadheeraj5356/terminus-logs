FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

COPY requirements.lock /tmp/requirements.lock

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-pip \
        curl \
        sqlite3 \
    && pip3 install --break-system-packages --no-cache-dir \
        --require-hashes -r /tmp/requirements.lock \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY go.mod go.sum ./
COPY vendor/ ./vendor/
COPY cmd/ ./cmd/
COPY internal/ ./internal/

# Single-stage on purpose, not an oversight: the fix lives in internal/audit,
# and whoever fixes it has to rebuild with the same `go build -mod=vendor`
# toolchain against /app afterward, offline. A slim runtime-only final stage
# would strip out the compiler that step depends on.
RUN go build -mod=vendor -o /usr/local/bin/chainaudit ./cmd/chainaudit \
    && go build -mod=vendor -o /usr/local/bin/mockkms ./cmd/mockkms

COPY data/ ./data/
COPY CHAINAUDIT-SPEC.md ./
COPY README.md ./
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]
