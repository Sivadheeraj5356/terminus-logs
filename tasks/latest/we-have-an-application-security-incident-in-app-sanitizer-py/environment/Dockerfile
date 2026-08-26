FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

LABEL org.opencontainers.image.source="https://snorkel-ai.github.io/Terminus-EC-Training-stateful/" \
      org.opencontainers.image.revision="5" \
      org.opencontainers.image.created="2026-07-14T00:00:00Z" \
      org.opencontainers.image.version="3.3" \
      org.opencontainers.image.licenses="Proprietary" \
      org.opencontainers.image.title="input-sanitization-engine"

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.lock /tmp/requirements.lock
RUN apt-get update \
    && apt-get install -y --no-install-recommends tmux \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --require-hashes --no-deps \
        --requirement /tmp/requirements.lock \
    && rm /tmp/requirements.lock

COPY verifier-requirements.txt /tmp/verifier-requirements.txt
RUN pip download --no-cache-dir \
        --require-hashes \
        --no-deps \
        --requirement /tmp/verifier-requirements.txt \
        --dest /opt/verifier-wheels \
    && rm /tmp/verifier-requirements.txt

WORKDIR /app

COPY app/sanitizer.py /app/sanitizer.py
COPY app/policy.json /app/policy.json
COPY app/input.jsonl /app/input.jsonl
