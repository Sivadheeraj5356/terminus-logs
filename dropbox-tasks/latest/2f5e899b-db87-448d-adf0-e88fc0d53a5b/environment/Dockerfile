# Ubuntu is used because this task requires redis-server and PHP CLI packages
# installed through apt, which are not provided by the standard t-bench base image.
FROM public.ecr.aws/docker/library/ubuntu:24.04@sha256:0d39fcc8335d6d74d5502f6df2d30119ff4790ebbb60b364818d5112d9e3e932

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

RUN apt-get update \
     && apt-get install -y --no-install-recommends \
     asciinema \
     ca-certificates \
     php-cli \
     php-redis \
     python3 \
     python3-pip \
     redis-server \
     redis-tools \
     sqlite3 \
     tmux \
     && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --break-system-packages --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock \
     && rm /tmp/requirements.lock

COPY app/ /app/

RUN mkdir -p /app/output /app/runtime /var/lib/redis-meter /var/log/redis-meter \
     && chmod 0700 /app/secrets /var/lib/redis-meter /var/log/redis-meter \
     && chmod 0600 /app/secrets/redis-credentials.ini \
     && chmod 0755 /app/bin/import-fixtures.php
