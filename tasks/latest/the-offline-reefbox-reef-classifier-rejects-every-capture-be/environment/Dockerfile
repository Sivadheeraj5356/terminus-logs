FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

LABEL org.opencontainers.image.title="reefbox-calibration-manifest"
LABEL org.opencontainers.image.description="Reverse-engineer the ReefBox PNG calibration format and emit a verified inference manifest with Terraform + jq + yq."
LABEL org.opencontainers.image.licenses="Apache-2.0"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    TF_IN_AUTOMATION=1

# System tools: jq for the pipeline, curl/unzip to fetch pinned binaries,
# tmux + asciinema for the agent harness, ca-certificates for TLS at build time.
RUN apt-get update && apt-get install -y --no-install-recommends \
        jq \
        ca-certificates \
        curl \
        unzip \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

# Terraform (checksum-pinned). Only the built-in terraform_data resource is used,
# so `init`/`apply` need no provider downloads and run fully offline.
RUN curl -fsSL -o /tmp/terraform.zip https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_linux_amd64.zip \
    && echo "186e0145f5e5f2eb97cbd785bc78f21bae4ef15119349f6ad4fa535b83b10df8  /tmp/terraform.zip" | sha256sum -c - \
    && unzip -q /tmp/terraform.zip -d /usr/local/bin \
    && rm /tmp/terraform.zip \
    && terraform version

# yq (checksum-pinned).
RUN curl -fsSL -o /usr/local/bin/yq https://github.com/mikefarah/yq/releases/download/v4.44.6/yq_linux_amd64 \
    && echo "0c2b24e645b57d8e7c0566d18643a6d4f5580feeea3878127354a46f2a1e4598  /usr/local/bin/yq" | sha256sum -c - \
    && chmod +x /usr/local/bin/yq \
    && yq --version

# Python verifier dependencies (hash-pinned; installed here, not in test.sh).
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock

WORKDIR /app
COPY app/ /app/

# Pre-initialize Terraform so `terraform apply` runs offline at agent/verify time.
RUN terraform -chdir=/app init -input=false
