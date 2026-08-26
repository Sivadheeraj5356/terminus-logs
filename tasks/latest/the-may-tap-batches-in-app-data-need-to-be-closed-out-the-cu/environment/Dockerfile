FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3 \
        python3-pip \
        sqlite3 \
        tmux \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir --break-system-packages pytest==8.4.1

COPY package.json /app/package.json
COPY reconcile.js /app/reconcile.js
COPY docs/ /app/docs/
COPY data/ /app/data/
COPY contracts/ /app/contracts/

RUN mkdir -p /app/output
