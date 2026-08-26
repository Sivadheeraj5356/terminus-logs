FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        rustc \
        curl \
        gcc \
        libc6-dev \
        less \
        nano \
        procps \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# Verifier dependencies are baked into a dedicated venv so tests/test.sh can run
# without installing anything at verifier runtime.
RUN python -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.2 \
        pytest-json-ctrf==0.5.0

COPY task_file/scan_input /app/task_file/scan_input
COPY task_file/model.py /app/task_file/model.py
COPY guide.md /app/task_file/guide.md
RUN rm -rf /app/task_file/output && mkdir -p /app/task_file/output
