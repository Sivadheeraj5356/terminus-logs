FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383 AS node-toolchain

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        bash \
        ca-certificates \
        tmux \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

COPY --from=node-toolchain /usr/local/bin/node /usr/local/bin/node

WORKDIR /app

COPY package.json /app/package.json
COPY pnpm-workspace.yaml /app/pnpm-workspace.yaml
COPY pnpm-lock.yaml /app/pnpm-lock.yaml
COPY .npmrc /app/.npmrc
COPY README.md /app/README.md
COPY docs /app/docs
COPY config /app/config
COPY patches /app/patches
COPY state /app/state
COPY generated /app/generated
COPY offline-store /app/offline-store
COPY apps /app/apps
COPY packages /app/packages
COPY scripts /app/scripts
COPY --chmod=755 tools /app/tools

RUN ln -sf /app/tools/pnpm /usr/local/bin/pnpm \
    && mkdir -p /app/reports /app/offline-store/quarantine /logs/agent /logs/verifier \
    && chmod 1777 /tmp
