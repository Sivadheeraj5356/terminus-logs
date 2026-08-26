# TypeScript library task graded by a Python pytest verifier.
# Submission cache-bust: 2026-07-21-portfall-rules-tuned.
# Canonical Node 22 slim base, digest-pinned per platform static checks.
FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

# Python verifier runtime plus agent session tooling. The base image is
# digest-pinned, so Debian package resolution is stable for this task image.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3 \
        python3-pytest \
        tmux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# npm manifest first, then install the TypeScript toolchain for offline runtime.
COPY package.json package-lock.json tsconfig.json ./
RUN npm ci

# Baseline fixtures the agent sees at run start.
COPY src/ ./src/
COPY portfall/ ./portfall/
COPY transcripts/ ./transcripts/
COPY golden/ ./golden/
