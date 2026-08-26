FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        lsof \
        procps \
        python-is-python3 \
        python3 \
        python3-pip \
        strace \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --break-system-packages --no-cache-dir --require-hashes \
        -r /tmp/requirements.lock

COPY app/package.json app/package-lock.json ./
ENV NPM_CONFIG_REGISTRY=https://registry.npmjs.org/
RUN npm ci --ignore-scripts --no-audit --no-fund

COPY app/ /app/

ENV NODE_ENV=development
EXPOSE 3000
