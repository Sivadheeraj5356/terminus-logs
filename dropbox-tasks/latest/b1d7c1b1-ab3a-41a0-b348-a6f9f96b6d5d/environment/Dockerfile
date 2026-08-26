FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip tmux asciinema \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --break-system-packages --require-hashes -r /tmp/requirements.lock

COPY license/ /app/license/
COPY bin/ /app/bin/
COPY data/ /app/data/
COPY docs/ /app/docs/
