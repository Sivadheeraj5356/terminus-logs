FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema \
    bash \
    ca-certificates \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
 && rm -rf /var/lib/apt/lists/* \
 && test -x /usr/local/go/bin/gofmt \
 && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
 && ln -sf /usr/local/go/bin/gofmt /usr/bin/gofmt

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

WORKDIR /app

COPY go.mod ./
COPY cmd/ ./cmd/
COPY internal/ ./internal/
COPY data/ ./data/
COPY deploy/ ./deploy/
COPY scripts/ ./scripts/
COPY vl/ ./vl/
COPY docs/ ./docs/

RUN go build -o /app/bin/rollbackctl ./cmd/rollbackctl \
 && chmod +x /app/deploy/scripts/apply-rollback.sh \
    /app/scripts/validate-rollback-env.sh \
    /app/scripts/rebuild-rollbackctl.sh \
    /app/vl/rbx_apply_core.sh \
    /app/vl/rbx_env_gate.sh

ENV PATH="/usr/local/go/bin:/usr/local/bin:/usr/bin:${PATH}"

RUN mkdir -p /app/state /app/output /opt/verifier-scripts \
 && cp /app/scripts/rebuild-rollbackctl.sh /opt/verifier-scripts/rebuild-rollbackctl.sh
