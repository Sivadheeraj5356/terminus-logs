FROM public.ecr.aws/docker/library/ruby:3.3-slim-bookworm@sha256:e76733e94b3a5893e4a141024ef3a583dc10781dc24becebf74f9c9f9a33e3df

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    patch=2.7.6-7 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        pytest-randomly==3.16.0
ENV PATH=/opt/verifier/bin:${PATH}

COPY . /app/environment/

RUN mv /app/environment/tools/k9_verify /app/environment/tools/k9v \
    && printf '%s\n' '#!/usr/bin/env bash' 'exec ruby /app/environment/tools/k9v/main.rb "$@"' \
       > /app/environment/tools/k9_verify \
    && chmod +x /app/environment/tools/k9_verify \
    && chmod +x /app/environment/scripts/build_lab.sh \
    && chmod +x /app/environment/scripts/run_grid.sh \
    && chmod +x /app/environment/migrations/rst9.sh \
    && bash /app/environment/scripts/build_lab.sh \
    && mkdir -p /app/output /app/output/stage /app/output/traces /logs/verifier

WORKDIR /app
