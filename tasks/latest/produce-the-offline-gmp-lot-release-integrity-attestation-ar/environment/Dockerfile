FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3-venv \
        strace \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

ENV PATH="/opt/verifier-venv/bin:/app/bin:${PATH}"

COPY bin/ /app/bin/
COPY src/ /app/src/
COPY docs/ /app/docs/
COPY metadata/ /app/environment/metadata/
COPY verifier-fixtures/ /opt/verifier-fixtures/

RUN chmod +x /app/bin/gmp-lot-integrity-attestor \
    && mkdir -p /app/output /app/state
