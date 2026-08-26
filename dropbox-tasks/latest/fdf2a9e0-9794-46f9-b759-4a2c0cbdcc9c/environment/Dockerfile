FROM public.ecr.aws/docker/library/ruby:3.3-slim-bookworm@sha256:e76733e94b3a5893e4a141024ef3a583dc10781dc24becebf74f9c9f9a33e3df

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3 \
        python3-pip \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --break-system-packages \
        --require-hashes --no-deps -r /tmp/requirements.lock

WORKDIR /app
COPY app/ /app/

RUN mkdir -p /app/bin
