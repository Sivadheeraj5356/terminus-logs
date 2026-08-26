# Snorkel ECR final runtime (upload form: Yes)
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

LABEL org.opencontainers.image.base.name="public.ecr.aws/docker/library/golang:1.24-bookworm"

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    asciinema \
    ca-certificates \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir \
    httpx==0.28.1 \
    pytest==9.0.3 \
    pytest-json-ctrf==0.5.0

ENV PATH="/opt/verifier-venv/bin:/usr/local/go/bin:${PATH}"
ENV CGO_ENABLED=0

WORKDIR /app

COPY go.mod ./
COPY cmd/ cmd/
COPY internal/ internal/
COPY docs/ docs/
COPY scripts/ scripts/
COPY README.md ./

RUN mkdir -p /app/bin /app/hint-scratch /app/data/worlds /opt/verifier-fixtures/worlds \
 && go mod vendor \
 && chmod +x /app/scripts/*.sh \
 && python3 /app/scripts/gen-fixtures.py \
 && rm -f /app/scripts/gen-fixtures.py \
 && /app/scripts/build.sh

RUN chmod a-w /opt/verifier-fixtures/worlds/catacombs/world.json \
 && chmod a-w /opt/verifier-fixtures/worlds/catacombs/chronicle.md
