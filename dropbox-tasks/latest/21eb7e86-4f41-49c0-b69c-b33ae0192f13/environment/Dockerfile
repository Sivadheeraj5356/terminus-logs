FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    redis-server=5:7.0.15-1~deb12u7 \
    redis-tools=5:7.0.15-1~deb12u7 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    curl=7.88.1-10+deb12u15 \
    ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.txt
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt
ENV PATH=/opt/verifier/bin:${PATH}

COPY bastion_cli/package.json bastion_cli/package-lock.json /app/bastion_cli/
WORKDIR /app/bastion_cli
RUN npm ci --omit=dev

COPY bastion_cli/src /app/bastion_cli/src

WORKDIR /app

COPY staging /app/staging
COPY redis_fixtures /app/redis_fixtures
COPY contracts /app/contracts
COPY docs /app/docs
COPY scripts /app/scripts
COPY README.md /app/README.md

RUN chmod +x /app/scripts/start_bastion.sh /app/scripts/bastion-run \
    && find /app/docs -type f -exec chmod 444 {} +

ENV REDIS_URL=redis://127.0.0.1:6379 \
    NODE_ENV=production

WORKDIR /app
