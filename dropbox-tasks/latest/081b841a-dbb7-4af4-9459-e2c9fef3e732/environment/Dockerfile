FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

LABEL org.opencontainers.image.source="https://example.com/orchid-buildgate" \
      org.opencontainers.image.created="2026-06-19T00:00:00Z" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.licenses="MIT"

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      asciinema=2.2.0-1 \
      ca-certificates=20230311+deb12u1 \
      jq=1.6-2.1+deb12u2 \
      openssl=3.0.20-1~deb12u2 \
      python3=3.11.2-1+b1 \
      python3-venv=3.11.2-1+b1 \
      tmux=3.3a-3 \
 && rm -rf /var/lib/apt/lists/*

# Test-only deps isolated to the verifier venv, kept out of the app/system Python.
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir \
      pytest==8.4.1 \
      pytest-json-ctrf==0.3.5

WORKDIR /app

COPY vendor/ /app/vendor/
COPY policy/ /app/policy/
COPY ledger/ /app/ledger/
COPY models/ /app/models/
COPY bin/ /app/bin/
COPY docs/ /app/docs/
COPY README.md /app/README.md

# Expose the arch-specific Rego engine and the audit entry points.
RUN mkdir -p /app/out \
 && chmod +x /app/vendor/opa-x86_64 /app/vendor/opa-aarch64 \
      /app/bin/hash-artifacts /app/bin/ledger-audit /app/bin/qa-check \
 && printf '#!/bin/sh\nexec /app/vendor/opa-$(uname -m) "$@"\n' > /usr/local/bin/opa \
 && chmod +x /usr/local/bin/opa
