FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt

COPY acl /app/environment/acl
COPY backups /app/environment/backups
COPY configs /app/environment/configs
COPY data /app/environment/data
COPY deployment /app/environment/deployment
COPY docs /app/environment/docs
COPY interfaces /app/environment/interfaces
COPY inventory /app/environment/inventory
COPY legacy /app/environment/legacy
COPY qos /app/environment/qos
COPY routers /app/environment/routers
COPY schemas /app/environment/schemas
COPY scripts /app/environment/scripts
COPY services /app/environment/services
COPY switches /app/environment/switches
COPY templates /app/environment/templates
COPY trunks /app/environment/trunks
COPY vlans /app/environment/vlans
COPY vrfs /app/environment/vrfs

# Authoring generators are excluded via .dockerignore; chmod runtime scripts only.
RUN chmod +x /app/environment/scripts/*.sh \
    /app/environment/scripts/lib/*.sh \
    /app/environment/services/hooks/*.sh \
    && mkdir -p /app/output

ENV ENV_ROOT=/app/environment
ENV OUTPUT_ROOT=/app/output
ENV PYTHONDONTWRITEBYTECODE=1
