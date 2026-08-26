# Go toolchain stage: agents compile delegationintegrity after editing cmd/internal (canonical list has no Go SDK on debian-slim alone).
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS go-toolchain

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

LABEL org.opencontainers.image.title="entitlement-lineage-corruption"
LABEL org.opencontainers.image.description="Security authorization task: detect privilege escalation and entitlement leakage in IGA delegation federation"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.source="https://github.com/snorkel-ai/terminus/harbor_tasks/entitlement-lineage-corruption"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.created="1970-01-01T00:00:00Z"

ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/usr/local/go/bin:/go/bin:/usr/local/bin:/usr/bin:/bin" \
    GOTOOLCHAIN=local \
    GO111MODULE=on \
    CGO_ENABLED=0 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    SOURCE_DATE_EPOCH=0

COPY requirements.lock /tmp/requirements.lock
COPY verifier-wheels/ /opt/verifier-wheels/

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        bash \
        ca-certificates \
        make \
        python3 \
        python3-pip \
        tmux \
    && pip3 install --break-system-packages --no-cache-dir --no-index \
        --find-links=/opt/verifier-wheels \
        --require-hashes \
        -r /tmp/requirements.lock \
    && rm -rf /var/lib/apt/lists/* /root/.cache /tmp/requirements.lock

COPY --from=go-toolchain /usr/local/go /usr/local/go
COPY --from=go-toolchain /go /go

WORKDIR /app

COPY go.mod go.sum Makefile /app/
RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && go version

COPY provenance_charters/ /app/provenance_charters/
COPY delegation_federation_slices/ /app/delegation_federation_slices/
COPY cmd/ /app/cmd/
COPY internal/ /app/internal/

RUN mkdir -p /app/build
