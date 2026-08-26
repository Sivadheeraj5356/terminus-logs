FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        curl \
        ffmpeg \
        git \
        gnupg \
        patch \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==9.0.3 \
        pytest-json-ctrf==0.5.0 \
        jsonschema==4.23.0

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY cmd/ /app/cmd/
COPY decoy/ /app/decoy/
COPY docs/ /app/docs/
COPY fixtures/ /app/fixtures/
COPY hooks/ /app/hooks/
COPY internal/ /app/internal/
COPY legacy/ /app/legacy/
COPY policyapi/ /app/policyapi/
COPY scripts/ /app/scripts/
COPY tools/ /app/tools/

# Agent must rebuild Go binaries at verify time (rebuild-reelseal.sh); keep toolchain.
RUN chmod +x /app/scripts/*.sh /app/hooks/pre-commit \
    && bash /app/scripts/generate-media.sh /app/fixtures/media-cache/bbb-sample.mp4 \
    && bash /app/scripts/setup-gpg.sh /app/fixtures/gnupg \
    && mkdir -p /app/state /app/output /app/bin /opt/verifier-fixtures \
    && cp -r /app/fixtures/verifier-hidden/. /opt/verifier-fixtures/ \
    && go mod vendor \
    && go build -o /app/bin/reelseal ./cmd/reelseal \
    && go build -o /app/bin/reelseal-policyapi ./policyapi

ENV PATH="/usr/local/go/bin:/opt/verifier-venv/bin:/app/bin:/app/scripts:${PATH}"
ENV GNUPGHOME=/app/fixtures/gnupg
ENV REELSEAL_API=http://127.0.0.1:8742
ENV REELSEAL_VERIFIER_FIXTURES=/opt/verifier-fixtures
ENV GOPROXY=off
ENV GOFLAGS=-mod=vendor

CMD ["bash", "-c", "sleep infinity"]
