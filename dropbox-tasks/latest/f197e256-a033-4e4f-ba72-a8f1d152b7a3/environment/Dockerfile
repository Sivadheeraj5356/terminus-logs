# Canonical base: python:3.13-slim-bookworm from the Snorkel-approved ECR mirror,
# pinned by sha256 digest. Covers Python 3.10/3.11/3.12/3.13 majors + patch + slim/non-slim
# per the 2026-06-16 canonical base image list.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

# OS packages: jq for JSON piping, curl to install OPA at build time (build phase has
# network by design; runtime honors allow_internet=false), ca-certificates for HTTPS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        jq \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# OPA static binary (Open Policy Agent v0.68.0). Version pinned; the build phase has
# network by design so we fetch the official static binary. Runtime honors allow_internet=false.
ARG OPA_VERSION=0.68.0
RUN set -eux; \
    ARCH="$(dpkg --print-architecture)"; \
    case "$ARCH" in \
      amd64) OPA_URL="https://openpolicyagent.org/downloads/v${OPA_VERSION}/opa_linux_amd64_static";; \
      arm64) OPA_URL="https://openpolicyagent.org/downloads/v${OPA_VERSION}/opa_linux_arm64_static";; \
      *) echo "Unsupported arch: $ARCH" >&2; exit 1;; \
    esac; \
    curl -fsSL "$OPA_URL" -o /usr/local/bin/opa; \
    chmod +x /usr/local/bin/opa; \
    /usr/local/bin/opa version

# Python packages: DuckDB for the inventory DB, pytest + ctrf for the verifier.
# Installed from a fully hashed lockfile so every wheel is verified; --no-deps
# because the lockfile already resolves the full transitive closure.
COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock

WORKDIR /app

# Copy the application skeleton (postmortem, DB, fixtures, harness, README).
COPY app/ /app/

# Build the DuckDB inventory from the seed CSVs so the container ships ready to query.
RUN cd /app && python /app/harness/build_inventory.py

# Confirm harness sanity: the golden plans exist and the postmortem passes the size gate.
RUN test -s /app/postmortem/postmortem.md \
    && python -c "import os,sys; s=os.path.getsize('/app/postmortem/postmortem.md'); print('postmortem_bytes=',s); sys.exit(0 if s>=280000 else 1)" \
    && test -s /app/golden/plan_ws001.json \
    && test -s /app/inventory/workstations.duckdb
